"""
Phase 8.6.3 — GitHub Zero-Friction Discovery & Repository Integration Router.
Provides deterministic discovery of user repositories, default branches, and validation.
Tokens are strictly in-memory per-request, never persisted to database or written to logs.
"""

from typing import Dict, Any, Optional, List
import urllib.request
import urllib.error
import json
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth import get_current_user_optional, AuthenticatedPrincipal

logger = logging.getLogger("twincore.github")
router = APIRouter(prefix="/github", tags=["GitHub Zero-Friction Integration"])


class GitHubTokenRequest(BaseModel):
    github_token: str = Field(..., description="GitHub Personal Access Token or App Installation Token")
    page: int = Field(1, ge=1, description="Page number for pagination")
    per_page: int = Field(30, ge=1, le=100, description="Items per page")
    query: Optional[str] = Field(None, description="Search filter for repository name")


class GitHubBranchesRequest(BaseModel):
    github_token: Optional[str] = Field(None, description="GitHub Token (if repository is private)")
    owner: str = Field(..., description="Repository Owner or Organization")
    repo: str = Field(..., description="Repository Name")


class GitHubValidateRequest(BaseModel):
    github_token: Optional[str] = Field(None)
    owner: str = Field(...)
    repo: str = Field(...)
    branch: Optional[str] = Field(None)


def _call_github_api(endpoint: str, token: Optional[str] = None) -> tuple[int, Any, Dict[str, str]]:
    url = f"https://api.github.com{endpoint}"
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "TwinCore-DigitalTwin-Platform/1.0",
    }
    if token and token.strip():
        headers["Authorization"] = f"Bearer {token.strip()}"

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            status_code = resp.status
            body = resp.read().decode("utf-8")
            resp_headers = dict(resp.headers)
            return status_code, json.loads(body), resp_headers
    except urllib.error.HTTPError as e:
        status_code = e.code
        body = e.read().decode("utf-8")
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = {"message": body}
        return status_code, parsed, dict(e.headers)
    except Exception as e:
        logger.error("GitHub API communication error: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Unable to reach GitHub API: {str(e)}"
        )


@router.post("/discover", response_model=Dict[str, Any])
def discover_user_repositories(
    payload: GitHubTokenRequest,
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """
    Discovers accessible repositories for the provided token without requiring
    the user to manually type URLs. Supports pagination and in-memory filtering.
    """
    token = payload.github_token.strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="GitHub token is required for discovery.")

    endpoint = f"/user/repos?sort=updated&direction=desc&page={payload.page}&per_page={payload.per_page}&affiliation=owner,collaborator,organization_member"
    status_code, data, headers = _call_github_api(endpoint, token=token)

    if status_code == 401:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired GitHub Personal Access Token."
        )
    elif status_code == 403:
        rate_reset = headers.get("x-ratelimit-reset", "")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"GitHub API rate limit exceeded. Reset timestamp: {rate_reset}"
        )
    elif status_code != 200:
        msg = data.get("message", "Failed to retrieve repositories from GitHub.")
        raise HTTPException(status_code=status_code, detail=msg)

    raw_repos = data if isinstance(data, list) else []
    query = (payload.query or "").lower().strip()

    filtered = []
    for r in raw_repos:
        name = r.get("name", "")
        full_name = r.get("full_name", "")
        if query and query not in name.lower() and query not in full_name.lower():
            continue

        filtered.append({
            "id": r.get("id"),
            "name": name,
            "full_name": full_name,
            "owner": r.get("owner", {}).get("login", ""),
            "clone_url": r.get("clone_url", ""),
            "html_url": r.get("html_url", ""),
            "private": r.get("private", False),
            "default_branch": r.get("default_branch", "main"),
            "language": r.get("language"),
            "description": r.get("description"),
            "updated_at": r.get("updated_at"),
            "stars": r.get("stargazers_count", 0),
            "fork": r.get("fork", False),
        })

    has_next_page = False
    link_header = headers.get("link", headers.get("Link", ""))
    if 'rel="next"' in link_header:
        has_next_page = True

    return {
        "status": "SUCCESS",
        "page": payload.page,
        "per_page": payload.per_page,
        "has_next_page": has_next_page,
        "total_returned": len(filtered),
        "total_count": len(filtered),
        "repositories": filtered,
    }


@router.post("/branches", response_model=Dict[str, Any])
def list_repository_branches(
    payload: GitHubBranchesRequest,
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """
    Discovers all accessible branches for a given repository to support automatic default branch
    detection and optional switching without manual typing.
    """
    owner = payload.owner.strip()
    repo = payload.repo.strip()
    if not owner or not repo:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Owner and repository name are required.")

    # 1. Fetch Repo metadata for authoritative default branch
    repo_endpoint = f"/repos/{owner}/{repo}"
    status_code, repo_data, headers = _call_github_api(repo_endpoint, token=payload.github_token)

    if status_code == 404:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Repository '{owner}/{repo}' not found or token lacks access.")
    elif status_code == 401:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired GitHub Token.")
    elif status_code != 200:
        raise HTTPException(status_code=status_code, detail=repo_data.get("message", "GitHub API error."))

    default_branch = repo_data.get("default_branch", "main")

    # 2. Fetch branch list (up to 50)
    branches_endpoint = f"/repos/{owner}/{repo}/branches?per_page=50"
    b_status, b_data, _ = _call_github_api(branches_endpoint, token=payload.github_token)

    branches = []
    if b_status == 200 and isinstance(b_data, list):
        for b in b_data:
            branches.append({
                "name": b.get("name"),
                "is_default": (b.get("name") == default_branch),
                "commit_sha": b.get("commit", {}).get("sha", "")[:8],
            })

    if not any(b["name"] == default_branch for b in branches):
        branches.insert(0, {"name": default_branch, "is_default": True, "commit_sha": ""})

    return {
        "status": "SUCCESS",
        "owner": owner,
        "repo": repo,
        "default_branch": default_branch,
        "branches": branches,
    }


@router.post("/validate", response_model=Dict[str, Any])
def validate_repository_access(
    payload: GitHubValidateRequest,
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """
    Pre-flight validation verifying repository existence, permissions, and specified branch
    before initiating workspace acquisition and cloning.
    """
    owner = payload.owner.strip()
    repo = payload.repo.strip()
    repo_endpoint = f"/repos/{owner}/{repo}"
    status_code, repo_data, _ = _call_github_api(repo_endpoint, token=payload.github_token)

    if status_code != 200:
        return {
            "valid": False,
            "error": "Repository not found or access denied.",
            "status_code": status_code,
        }

    default_branch = repo_data.get("default_branch", "main")
    target_branch = payload.branch or default_branch

    # Validate target branch exists
    branch_endpoint = f"/repos/{owner}/{repo}/branches/{target_branch}"
    b_status, b_data, _ = _call_github_api(branch_endpoint, token=payload.github_token)

    if b_status != 200:
        return {
            "valid": False,
            "error": f"Branch '{target_branch}' does not exist on '{owner}/{repo}'.",
            "default_branch": default_branch,
        }

    return {
        "valid": True,
        "owner": owner,
        "repo": repo,
        "default_branch": default_branch,
        "selected_branch": target_branch,
        "private": repo_data.get("private", False),
        "clone_url": repo_data.get("clone_url"),
        "commit_sha": b_data.get("commit", {}).get("sha"),
    }
