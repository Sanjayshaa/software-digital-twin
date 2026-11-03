"""
Phase 2 — GitHub Webhooks & Pull Request CI Analysis Router.
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status, Header, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import settings
from app.core.auth import resolve_authorized_repo, get_current_user_optional, AuthenticatedPrincipal
from app.models.entities import Repository, PullRequestRecord, PullRequestStatus
from app.services.pr_impact.models import PREventPayload, CIStatusPolicy
from app.services.pr_impact.security import (
    verify_github_signature,
    check_and_record_delivery,
    MAX_WEBHOOK_PAYLOAD_BYTES,
)
from app.services.pr_impact.service import PRImpactService

logger = logging.getLogger("twincore.webhooks")
router = APIRouter(tags=["GitHub Pull Request & CI Integration"])


class PRManualAnalyzeRequest(BaseModel):
    pull_request_number: int = Field(..., ge=1)
    base_commit_sha: str = Field(...)
    head_commit_sha: str = Field(...)
    base_branch: Optional[str] = Field("main")
    head_branch: Optional[str] = Field("feature")
    title: Optional[str] = Field(None)
    test_execution_results: Optional[Dict[str, Any]] = Field(None)
    policy: Optional[CIStatusPolicy] = Field(None)


@router.post("/webhooks/github", status_code=status.HTTP_200_OK)
async def github_webhook_endpoint(
    request: Request,
    x_github_event: Optional[str] = Header(None, alias="X-GitHub-Event"),
    x_hub_signature_256: Optional[str] = Header(None, alias="X-Hub-Signature-256"),
    x_github_delivery: Optional[str] = Header(None, alias="X-GitHub-Delivery"),
    db: Session = Depends(get_db),
):
    """
    Receives and processes GitHub Pull Request webhooks with HMAC-SHA256 signature verification,
    payload size limiting, and deduplication against replay attacks.
    """
    # 1. Payload size check
    body_bytes = await request.body()
    if len(body_bytes) > MAX_WEBHOOK_PAYLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Webhook payload exceeds maximum size ({len(body_bytes)} > {MAX_WEBHOOK_PAYLOAD_BYTES} bytes).",
        )

    # 2. Signature verification
    webhook_secret = os.environ.get("GITHUB_WEBHOOK_SECRET") or getattr(settings, "GITHUB_WEBHOOK_SECRET", None) or "twincore_dev_secret"
    if not verify_github_signature(body_bytes, x_hub_signature_256, webhook_secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing GitHub webhook signature.",
        )

    # 3. Deduplication check
    if not check_and_record_delivery(x_github_delivery):
        return {"status": "IGNORED", "reason": f"Duplicate webhook delivery {x_github_delivery}."}

    # 4. Filter for pull_request events
    if x_github_event != "pull_request":
        return {"status": "IGNORED", "reason": f"Event '{x_github_event}' is not handled."}

    try:
        data = json.loads(body_bytes.decode("utf-8"))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Malformed JSON payload.")

    action = data.get("action")
    if action not in ("opened", "synchronize", "reopened", "closed"):
        return {"status": "IGNORED", "reason": f"Pull request action '{action}' is not handled."}

    pr_data = data.get("pull_request", {})
    repo_data = data.get("repository", {})
    external_repo = repo_data.get("full_name") or repo_data.get("name")

    payload = PREventPayload(
        provider="github",
        external_repository=external_repo,
        pull_request_number=pr_data.get("number") or data.get("number", 1),
        title=pr_data.get("title"),
        base_branch=pr_data.get("base", {}).get("ref", "main"),
        base_commit_sha=pr_data.get("base", {}).get("sha", ""),
        head_branch=pr_data.get("head", {}).get("ref", "feature"),
        head_commit_sha=pr_data.get("head", {}).get("sha", ""),
        event_type=action,
        sender=data.get("sender", {}).get("login"),
        delivery_id=x_github_delivery,
    )

    pr_service = PRImpactService()
    try:
        report = pr_service.process_pull_request_event(db, payload)
        return {
            "status": "PROCESSED",
            "pull_request_number": report.pull_request_number,
            "ci_recommendation": report.ci_recommendation,
            "analysis_status": report.status,
            "summary": report.summary,
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Error processing GitHub PR webhook: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="PR analysis processing failed.")


@router.post("/repositories/{repository_id}/pull-requests/analyze", response_model=Dict[str, Any])
def analyze_pull_request_manual(
    repository_id: str,
    req: PRManualAnalyzeRequest,
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """
    Direct endpoint for CI pipelines and CLI invocation to trigger pull request analysis
    with optional test execution telemetry.
    """
    repo = resolve_authorized_repo(db=db, repository_id=repository_id, principal=principal)
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Repository '{repository_id}' not found.")

    payload = PREventPayload(
        provider="generic",
        repository_id=repo.id,
        external_repository=repo.name,
        pull_request_number=req.pull_request_number,
        title=req.title,
        base_branch=req.base_branch or repo.default_branch or "main",
        base_commit_sha=req.base_commit_sha,
        head_branch=req.head_branch or "feature",
        head_commit_sha=req.head_commit_sha,
        event_type="synchronize",
    )

    pr_service = PRImpactService(policy=req.policy)
    try:
        report = pr_service.process_pull_request_event(
            db=db,
            payload=payload,
            test_execution_results=req.test_execution_results,
        )
        return report.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Manual PR analysis failed: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"PR analysis failed: {str(e)}")


@router.get("/repositories/{repository_id}/pull-requests", response_model=List[Dict[str, Any]])
def list_pull_request_records(
    repository_id: str,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """
    Returns recent Pull Request analysis history for the repository dashboard.
    """
    repo = resolve_authorized_repo(db=db, repository_id=repository_id, principal=principal)
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Repository '{repository_id}' not found.")

    records = (
        db.query(PullRequestRecord)
        .filter_by(repository_id=repo.id)
        .order_by(PullRequestRecord.received_at.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "id": r.id,
            "pull_request_number": r.pull_request_number,
            "title": r.title,
            "base_branch": r.base_branch,
            "head_branch": r.head_branch,
            "base_commit_sha": r.base_commit_sha,
            "head_commit_sha": r.head_commit_sha,
            "status": r.status,
            "ci_recommendation": r.ci_recommendation,
            "summary": r.summary,
            "received_at": r.received_at.isoformat() if r.received_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            "error_message": r.error_message,
        }
        for r in records
    ]


@router.get("/repositories/{repository_id}/pull-requests/{pr_number}/report")
def get_pull_request_report(
    repository_id: str,
    pr_number: int,
    format: str = Query("json", description="'json' or 'markdown'"),
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """
    Returns the latest analysis report for a given Pull Request number.
    """
    repo = resolve_authorized_repo(db=db, repository_id=repository_id, principal=principal)
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Repository '{repository_id}' not found.")

    record = (
        db.query(PullRequestRecord)
        .filter_by(repository_id=repo.id, pull_request_number=pr_number)
        .order_by(PullRequestRecord.received_at.desc())
        .first()
    )
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No analysis report found for Pull Request #{pr_number}.",
        )

    if format.lower() == "markdown":
        return Response(content=record.report_markdown or "No markdown summary available.", media_type="text/markdown")

    return {
        "id": record.id,
        "pull_request_number": record.pull_request_number,
        "title": record.title,
        "status": record.status,
        "ci_recommendation": record.ci_recommendation,
        "base_commit_sha": record.base_commit_sha,
        "head_commit_sha": record.head_commit_sha,
        "summary": record.summary,
        "report_markdown": record.report_markdown,
        "received_at": record.received_at.isoformat() if record.received_at else None,
        "completed_at": record.completed_at.isoformat() if record.completed_at else None,
    }
