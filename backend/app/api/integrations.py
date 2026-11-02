"""
Phase 9 — Enterprise VCS Integration Router (GitHub & GitLab).
Provides unified, provider-neutral repository discovery, authentication validation,
and secure ingestion dispatch without credential persistence or token leakage.
"""

from typing import Dict, Any, Optional, List, Tuple
import urllib.request
import urllib.error
import urllib.parse
import json
import logging
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth import get_current_user_optional, AuthenticatedPrincipal
from app.services.acquisition.git_provider import acquire_github_repository
from app.services.acquisition import is_safe_clone_url

logger = logging.getLogger("twincore.integrations")
router = APIRouter(prefix="/integrations", tags=["Enterprise VCS Integrations"])


# ====================================================================
# Request & Response Schemas
# ====================================================================

class ProviderStatusResponse(BaseModel):
    provider: str
    connected: bool
    configured: bool
    account_name: Optional[str] = None
    rate_limit_remaining: Optional[int] = None
    rate_limit_reset: Optional[str] = None
    scope: Optional[str] = None
    setup_requirement: Optional[str] = None


class DiscoverReposRequest(BaseModel):
    provider: str = Field(..., description="'github' or 'gitlab'")
    token: str = Field(..., description="Personal Access Token or OAuth Token")
    base_url: Optional[str] = Field(None, description="Self-hosted instance URL (GitLab CE/EE)")
    page: int = Field(1, ge=1)
    per_page: int = Field(30, ge=1, le=100)
    query: Optional[str] = Field(None, description="Search filter by name")


class DiscoverBranchesRequest(BaseModel):
    provider: str = Field(..., description="'github' or 'gitlab'")
    token: Optional[str] = Field(None)
    base_url: Optional[str] = Field(None)
    owner: str = Field(...)
    repo: str = Field(...)


class ConnectRepoRequest(BaseModel):
    provider: str = Field(..., description="'github' or 'gitlab'")
    token: Optional[str] = Field(None, description="Token used only for acquisition; never stored")
    base_url: Optional[str] = Field(None)
    clone_url: str = Field(..., description="HTTPS clone URL")
    branch: Optional[str] = Field(None)
    name: Optional[str] = Field(None)


# ====================================================================
# Provider API Dispatchers
# ====================================================================

def _call_gitlab_api(
    endpoint: str,
    token: Optional[str] = None,
    base_url: Optional[str] = None,
) -> Tuple[int, Any, Dict[str, str]]:
    """Calls GitLab API v4 with secure timeouts and token headers."""
    host = (base_url or "https://gitlab.com").rstrip("/")
    url = f"{host}/api/v4{endpoint}"
    
    headers = {
        "Accept": "application/json",
        "User-Agent": "TwinCore-DigitalTwin-Platform/1.0",
    }
    if token and token.strip():
        # GitLab accepts Bearer or PRIVATE-TOKEN
        headers["PRIVATE-TOKEN"] = token.strip()

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            status_code = resp.status
            body = resp.read().decode("utf-8")
            return status_code, json.loads(body), dict(resp.headers)
    except urllib.error.HTTPError as e:
        status_code = e.code
        body = e.read().decode("utf-8")
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = {"message": body}
        return status_code, parsed, dict(e.headers)
    except Exception as e:
        logger.error("GitLab API communication error: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Unable to reach GitLab API at {host}: {str(e)}"
        )


def _call_github_api(endpoint: str, token: Optional[str] = None) -> Tuple[int, Any, Dict[str, str]]:
    """Calls GitHub REST API v3."""
    from app.api.github import _call_github_api as gh_call
    return gh_call(endpoint=endpoint, token=token)


# ====================================================================
# Endpoints
# ====================================================================

@router.get("/status", response_model=Dict[str, Any])
def get_integrations_status(
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """
    Returns the real connection and configuration status for VCS providers and local MCP.
    Never fabricates a successful connection when credentials are not configured.
    """
    import os
    gh_configured = bool(os.environ.get("GITHUB_CLIENT_ID") or os.environ.get("GITHUB_TOKEN"))
    gl_configured = bool(os.environ.get("GITLAB_CLIENT_ID") or os.environ.get("GITLAB_TOKEN"))

    return {
        "status": "SUCCESS",
        "providers": {
            "github": {
                "name": "GitHub",
                "configured": gh_configured,
                "supported_auth": ["personal_access_token", "oauth_app"],
                "setup_requirement": None if gh_configured else "Provide a GitHub Personal Access Token (PAT) with 'repo' scope or configure GITHUB_TOKEN.",
                "secure_storage": "In-memory per session; secrets never persisted to database.",
            },
            "gitlab": {
                "name": "GitLab",
                "configured": gl_configured,
                "supported_auth": ["personal_access_token", "oauth_app"],
                "setup_requirement": None if gl_configured else "Provide a GitLab Personal Access Token with 'read_api' & 'read_repository' scopes.",
                "secure_storage": "In-memory per session; secrets never persisted to database.",
            },
            "local_workspace": {
                "name": "Local Workspace & CLI",
                "configured": True,
                "capabilities": ["direct_ast_analysis", "working_tree_diff", "what_if_simulation"],
            },
            "mcp_server": {
                "name": "TwinCore Local MCP Service",
                "configured": True,
                "transport": "stdio / json-rpc",
                "command": "python -m cli.mcp_server",
                "capabilities": ["get_workspace", "analyze_working_tree", "preview_patch", "run_impact_analysis"],
            }
        }
    }


@router.post("/discover-repositories", response_model=Dict[str, Any])
def discover_repositories(
    payload: DiscoverReposRequest,
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """
    Unified discovery endpoint supporting both GitHub and GitLab.
    Returns normalized repository metadata.
    """
    prov = payload.provider.lower().strip()
    token = payload.token.strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{payload.provider.capitalize()} access token is required."
        )

    if prov == "github":
        endpoint = f"/user/repos?sort=updated&direction=desc&page={payload.page}&per_page={payload.per_page}&affiliation=owner,collaborator,organization_member"
        status_code, data, headers = _call_github_api(endpoint, token=token)
        if status_code == 401:
            raise HTTPException(status_code=401, detail="Invalid or expired GitHub Personal Access Token.")
        elif status_code == 403:
            raise HTTPException(status_code=429, detail="GitHub API rate limit exceeded.")
        elif status_code != 200:
            raise HTTPException(status_code=status_code, detail=data.get("message", "GitHub API error."))

        raw_repos = data if isinstance(data, list) else []
        query = (payload.query or "").lower().strip()
        normalized = []
        for r in raw_repos:
            name = r.get("name", "")
            full_name = r.get("full_name", "")
            if query and query not in name.lower() and query not in full_name.lower():
                continue
            normalized.append({
                "id": str(r.get("id")),
                "provider": "github",
                "name": name,
                "full_name": full_name,
                "owner": r.get("owner", {}).get("login", ""),
                "clone_url": r.get("clone_url", ""),
                "html_url": r.get("html_url", ""),
                "private": r.get("private", False),
                "default_branch": r.get("default_branch", "main"),
                "language": r.get("language") or "unknown",
                "description": r.get("description"),
                "updated_at": r.get("updated_at"),
            })

        has_next = 'rel="next"' in headers.get("link", headers.get("Link", ""))
        return {
            "status": "SUCCESS",
            "provider": "github",
            "page": payload.page,
            "has_next_page": has_next,
            "total_accessible": len(normalized),
            "repositories": normalized,
        }

    elif prov == "gitlab":
        encoded_query = f"&search={urllib.parse.quote(payload.query)}" if payload.query else ""
        endpoint = f"/projects?membership=true&order_by=updated_at&sort=desc&page={payload.page}&per_page={payload.per_page}{encoded_query}"
        status_code, data, headers = _call_gitlab_api(endpoint, token=token, base_url=payload.base_url)
        if status_code == 401:
            raise HTTPException(status_code=401, detail="Invalid or expired GitLab Personal Access Token.")
        elif status_code != 200:
            raise HTTPException(status_code=status_code, detail=data.get("message", "GitLab API error."))

        raw_projects = data if isinstance(data, list) else []
        normalized = []
        for p in raw_projects:
            name = p.get("name", "")
            path_with_namespace = p.get("path_with_namespace", "")
            normalized.append({
                "id": str(p.get("id")),
                "provider": "gitlab",
                "name": name,
                "full_name": path_with_namespace,
                "owner": p.get("namespace", {}).get("path", "") if isinstance(p.get("namespace"), dict) else "",
                "clone_url": p.get("http_url_to_repo", ""),
                "html_url": p.get("web_url", ""),
                "private": p.get("visibility") == "private",
                "default_branch": p.get("default_branch", "main"),
                "language": "unknown",
                "description": p.get("description"),
                "updated_at": p.get("last_activity_at"),
            })

        has_next = bool(headers.get("x-next-page"))
        return {
            "status": "SUCCESS",
            "provider": "gitlab",
            "page": payload.page,
            "has_next_page": has_next,
            "total_accessible": len(normalized),
            "repositories": normalized,
        }

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported provider '{payload.provider}'. Supported providers: 'github', 'gitlab'."
        )


@router.post("/discover-branches", response_model=Dict[str, Any])
def discover_branches(
    payload: DiscoverBranchesRequest,
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """
    Returns available branches and default branch for either GitHub or GitLab repository.
    """
    prov = payload.provider.lower().strip()
    owner = payload.owner.strip()
    repo = payload.repo.strip()

    if prov == "github":
        endpoint = f"/repos/{owner}/{repo}/branches?per_page=100"
        status_code, data, _ = _call_github_api(endpoint, token=payload.token)
        if status_code == 404:
            raise HTTPException(status_code=404, detail="GitHub repository not found or unauthorized.")
        elif status_code != 200:
            raise HTTPException(status_code=status_code, detail="Failed to fetch branches from GitHub.")

        branches = [b.get("name") for b in data if isinstance(b, dict) and b.get("name")]
        return {
            "status": "SUCCESS",
            "provider": "github",
            "owner": owner,
            "repo": repo,
            "branches": branches,
            "total": len(branches),
        }

    elif prov == "gitlab":
        project_id = urllib.parse.quote(f"{owner}/{repo}", safe="")
        endpoint = f"/projects/{project_id}/repository/branches?per_page=100"
        status_code, data, _ = _call_gitlab_api(endpoint, token=payload.token, base_url=payload.base_url)
        if status_code == 404:
            raise HTTPException(status_code=404, detail="GitLab project not found or unauthorized.")
        elif status_code != 200:
            raise HTTPException(status_code=status_code, detail="Failed to fetch branches from GitLab.")

        branches = [b.get("name") for b in data if isinstance(b, dict) and b.get("name")]
        return {
            "status": "SUCCESS",
            "provider": "gitlab",
            "owner": owner,
            "repo": repo,
            "branches": branches,
            "total": len(branches),
        }

    else:
        raise HTTPException(status_code=400, detail="Invalid provider.")

