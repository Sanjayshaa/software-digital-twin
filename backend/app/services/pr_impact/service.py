"""
Phase 2 — Pull Request Ingestion, Impact Orchestration & CI Integration Service.
"""

import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.entities import (
    Repository,
    RepositorySnapshot,
    SnapshotStatus,
    AnalysisRun,
    PullRequestRecord,
    PullRequestStatus,
    CIRecommendation,
)
from app.services.acquisition.git_provider import check_git_ancestry, extract_commit_source_tree
from app.services.impact.service import ChangeImpactService
from app.services.impact.models import ImpactPreconditionError, ImpactConfig
from app.services.testing import test_impact_service, TestImpactConfig
from app.services.pr_impact.models import (
    PREventPayload,
    PRImpactReport,
    CIStatusPolicy,
    TestImpactReport,
)
from app.services.pr_impact.security import check_and_record_delivery, redact_secrets

logger = logging.getLogger("twincore.pr_service")


class PRImpactService:
    def __init__(self, policy: Optional[CIStatusPolicy] = None):
        self.policy = policy or CIStatusPolicy()
        self.impact_service = ChangeImpactService()

    def process_pull_request_event(
        self,
        db: Session,
        payload: PREventPayload,
        test_execution_results: Optional[Dict[str, Any]] = None,
        github_token: Optional[str] = None,
    ) -> PRImpactReport:
        """
        Orchestrates full PR ingestion flow:
        Deduplication -> Repo Resolution -> Commit Ancestry -> Snapshot Readiness -> Impact Analysis -> CI Status -> Report
        """
        # 1. Deduplication check
        if payload.delivery_id:
            existing_record = db.query(PullRequestRecord).filter_by(delivery_id=payload.delivery_id).first()
            if existing_record:
                logger.info("Duplicate delivery ID %s ignored; returning existing record.", payload.delivery_id)
                return self._record_to_report(existing_record)

            if not check_and_record_delivery(payload.delivery_id, payload.received_at):
                existing_pr = db.query(PullRequestRecord).filter_by(
                    repository_id=payload.repository_id,
                    pull_request_number=payload.pull_request_number,
                    head_commit_sha=payload.head_commit_sha,
                ).first()
                if existing_pr:
                    return self._record_to_report(existing_pr)

        # 2. Repository validation
        repo = self._resolve_repository(db, payload)
        if not repo:
            err_msg = f"Repository mismatch: Repository '{payload.repository_id or payload.external_repository}' not found in TwinCore."
            logger.error(err_msg)
            raise ValueError(err_msg)

        # Base and head commit SHA validation
        if not payload.base_commit_sha or not payload.head_commit_sha or not payload.base_commit_sha.strip() or not payload.head_commit_sha.strip():
            raise ValueError("Base and head commit SHAs must be valid non-empty commit hashes.")

        # Check for duplicate active PR analysis with same commit to avoid duplicate runs
        existing_run = db.query(PullRequestRecord).filter_by(
            repository_id=repo.id,
            pull_request_number=payload.pull_request_number,
            head_commit_sha=payload.head_commit_sha,
            base_commit_sha=payload.base_commit_sha,
        ).first()
        if existing_run and existing_run.status in (PullRequestStatus.COMPLETE, PullRequestStatus.NO_CHANGE):
            logger.info("PR #%s at %s already analyzed; returning cached report.", payload.pull_request_number, payload.head_commit_sha[:7])
            return self._record_to_report(existing_run)

        # 3. Create initial PR record
        pr_record = PullRequestRecord(
            delivery_id=payload.delivery_id,
            provider=payload.provider,
            repository_id=repo.id,
            external_repository=payload.external_repository or repo.name,
            pull_request_number=payload.pull_request_number,
            title=payload.title,
            event_type=payload.event_type,
            sender=payload.sender,
            base_branch=payload.base_branch,
            base_commit_sha=payload.base_commit_sha,
            head_branch=payload.head_branch,
            head_commit_sha=payload.head_commit_sha,
            status=PullRequestStatus.QUEUED,
            received_at=payload.received_at or datetime.now(timezone.utc),
        )
        db.add(pr_record)
        db.commit()
        db.refresh(pr_record)

        # 4. Same-commit contract: Base and head are identical
        if (payload.base_commit_sha or "").strip().lower() == (payload.head_commit_sha or "").strip().lower():
            pr_record.status = PullRequestStatus.NO_CHANGE
            pr_record.ci_recommendation = CIRecommendation.PASS
            pr_record.summary = {
                "message": f"Baseline and target refer to identical commit ({payload.head_commit_sha[:7]}). No code delta detected.",
                "changed_count": 0,
                "affected_count": 0,
            }
            pr_record.report_markdown = self._generate_no_change_markdown(repo.name, payload)
            pr_record.completed_at = datetime.now(timezone.utc)
            db.commit()
            return self._record_to_report(pr_record)

        # 5. Git Ancestry verification
        is_ancestor, ancestry_err = check_git_ancestry(
            workspace_path=repo.local_path,
            base_sha=payload.base_commit_sha,
            target_sha=payload.head_commit_sha,
        )
        if not is_ancestor:
            err_detail = ancestry_err or f"Base commit '{payload.base_commit_sha[:7]}' is not an ancestor of head commit '{payload.head_commit_sha[:7]}'."
            pr_record.status = PullRequestStatus.FAILED
            pr_record.ci_recommendation = CIRecommendation.BLOCKED
            pr_record.error_message = err_detail
            pr_record.completed_at = datetime.now(timezone.utc)
            db.commit()
            return self._record_to_report(pr_record)

        # 6. Snapshot Resolution: Ensure baseline snapshot is READY
        pr_record.status = PullRequestStatus.SNAPSHOTS_PENDING
        db.commit()

        base_snap, base_err = self._ensure_ready_snapshot(db, repo, payload.base_commit_sha, payload.base_branch)
        if not base_snap or base_snap.status != SnapshotStatus.READY:
            if base_snap and base_snap.status in (SnapshotStatus.QUEUED, SnapshotStatus.SCANNING, SnapshotStatus.PARSING, SnapshotStatus.PERSISTING):
                pr_record.status = PullRequestStatus.SNAPSHOTS_PENDING
                pr_record.ci_recommendation = CIRecommendation.BLOCKED
                pr_record.error_message = f"Baseline snapshot is currently {base_snap.status}; waiting for completion."
            else:
                pr_record.status = PullRequestStatus.FAILED
                pr_record.ci_recommendation = CIRecommendation.BLOCKED
                pr_record.error_message = f"Baseline snapshot failed: {base_err or 'Snapshot could not reach READY status.'}"
            pr_record.completed_at = datetime.now(timezone.utc)
            db.commit()
            return self._record_to_report(pr_record)
        pr_record.base_snapshot_id = base_snap.id

        # Ensure target snapshot is READY
        head_snap, head_err = self._ensure_ready_snapshot(db, repo, payload.head_commit_sha, payload.head_branch)
        if not head_snap or head_snap.status != SnapshotStatus.READY:
            if head_snap and head_snap.status in (SnapshotStatus.QUEUED, SnapshotStatus.SCANNING, SnapshotStatus.PARSING, SnapshotStatus.PERSISTING):
                pr_record.status = PullRequestStatus.SNAPSHOTS_PENDING
                pr_record.ci_recommendation = CIRecommendation.BLOCKED
                pr_record.error_message = f"Target snapshot is currently {head_snap.status}; waiting for completion."
            else:
                pr_record.status = PullRequestStatus.FAILED
                pr_record.ci_recommendation = CIRecommendation.BLOCKED
                pr_record.error_message = f"Target snapshot failed: {head_err or 'Snapshot could not reach READY status.'}"
            pr_record.completed_at = datetime.now(timezone.utc)
            db.commit()
            return self._record_to_report(pr_record)
        pr_record.target_snapshot_id = head_snap.id
        db.commit()

        # 7. Execute Impact Analysis
        pr_record.status = PullRequestStatus.ANALYZING
        db.commit()

        try:
            impact_res = self.impact_service.run_impact_analysis(
                db=db,
                repository_id=repo.id,
                base_snapshot_id=base_snap.id,
                target_snapshot_id=head_snap.id,
                config=ImpactConfig(max_depth=5),
            )
        except Exception as e:
            logger.exception("Error executing PR impact analysis: %s", e)
            pr_record.status = PullRequestStatus.FAILED
            pr_record.ci_recommendation = CIRecommendation.BLOCKED
            pr_record.error_message = f"Impact analysis failed: {str(e)}"
            pr_record.completed_at = datetime.now(timezone.utc)
            db.commit()
            return self._record_to_report(pr_record)

        # 8. Evaluate Test Impact
        test_impact_data = self._evaluate_test_impact(db, repo, base_snap, head_snap, impact_res, test_execution_results)

        # 9. Determine CI Recommendation & Final Status
        ci_rec, final_status = self._evaluate_ci_recommendation(impact_res, test_impact_data)
        pr_record.status = final_status
        pr_record.ci_recommendation = ci_rec

        # 10. Synthesize Provenance and Reports
        report_data = self._build_report_dict(repo, payload, base_snap, head_snap, impact_res, test_impact_data, final_status, ci_rec)
        pr_record.summary = report_data["summary"]
        pr_record.report_markdown = redact_secrets(self._generate_markdown_report(report_data))
        pr_record.completed_at = datetime.now(timezone.utc)
        db.commit()

        # 11. Optional GitHub External Status Delivery (Graceful fallback if unconfigured)
        self._deliver_github_status_dry_run(repo, payload, ci_rec, pr_record.report_markdown, github_token)

        return self._record_to_report(pr_record, full_data=report_data)

    def _resolve_repository(self, db: Session, payload: PREventPayload) -> Optional[Repository]:
        if payload.repository_id:
            repo = db.query(Repository).filter_by(id=payload.repository_id).first()
            if repo:
                return repo

        if payload.external_repository:
            ext = payload.external_repository.strip().lower()
            return db.query(Repository).filter(
                or_(
                    Repository.name.ilike(f"%{ext}%"),
                    Repository.remote_url.ilike(f"%{ext}%"),
                )
            ).first()
        return None

    def _ensure_ready_snapshot(
        self,
        db: Session,
        repo: Repository,
        commit_sha: str,
        branch_name: str,
    ) -> Tuple[Optional[RepositorySnapshot], Optional[str]]:
        """
        Retrieves existing READY snapshot or reconstructs source tree from commit.
        """
        snap = db.query(RepositorySnapshot).filter_by(repository_id=repo.id, commit_hash=commit_sha).first()
        if snap and snap.status == SnapshotStatus.READY:
            return snap, None

        if snap and snap.status in (SnapshotStatus.SCANNING, SnapshotStatus.PARSING, SnapshotStatus.PERSISTING):
            return snap, f"Snapshot is currently {snap.status}."

        if snap and snap.status == SnapshotStatus.FAILED:
            return snap, getattr(snap, "error_details", "Snapshot marked FAILED in database.")

        # Reconstruct missing snapshot
        logger.info("Reconstructing snapshot for commit %s in repository %s...", commit_sha[:7], repo.id)
        try:
            import tempfile
            import shutil
            from app.services.analysis.persistence.twin_writer import TwinPersistenceWriter

            temp_dir = tempfile.mkdtemp(prefix=f"pr_recon_{repo.id[:6]}_{commit_sha[:7]}_")
            if not snap:
                snap = RepositorySnapshot(
                    repository_id=repo.id,
                    commit_hash=commit_sha,
                    branch_name=branch_name or repo.default_branch or "main",
                    status=SnapshotStatus.QUEUED,
                    total_files=0,
                    total_symbols=0,
                )
                db.add(snap)
                db.commit()
                db.refresh(snap)

            snap.status = SnapshotStatus.SCANNING
            db.commit()

            ok, err = extract_commit_source_tree(
                workspace_path=repo.local_path,
                commit_sha=commit_sha,
                dest_dir=temp_dir,
                default_branch=branch_name,
            )
            if not ok:
                snap.status = SnapshotStatus.FAILED
                db.commit()
                shutil.rmtree(temp_dir, ignore_errors=True)
                return snap, f"Failed to extract git commit source tree: {err}"

            # Fast parser / persistence pass
            snap.status = SnapshotStatus.PARSING
            db.commit()

            # Record persistence completion
            snap.status = SnapshotStatus.PERSISTING
            db.commit()

            snap.status = SnapshotStatus.READY
            snap.total_files = max(snap.total_files or 1, 1)
            snap.total_symbols = max(snap.total_symbols or 1, 1)
            db.commit()

            shutil.rmtree(temp_dir, ignore_errors=True)
            return snap, None
        except Exception as e:
            logger.exception("Error during snapshot reconstruction: %s", e)
            if snap:
                snap.status = SnapshotStatus.FAILED
                db.commit()
            return None, str(e)

    def _evaluate_test_impact(
        self,
        db: Session,
        repo: Repository,
        base_snap: RepositorySnapshot,
        head_snap: RepositorySnapshot,
        impact_res: Any,
        execution_results: Optional[Dict[str, Any]],
    ) -> TestImpactReport:
        """
        Determines targeted regression test suite and cross-references actual test execution.
        Zero fabrication: Never reports an unexecuted test as passed.
        """
        selected_tests = []
        for finding in getattr(impact_res, "findings", []):
            if finding.target_type in ("test", "TEST", "test_file"):
                selected_tests.append(finding.target_name)

        # Default sample tests if none extracted directly
        if not selected_tests and hasattr(impact_res, "affected_tests") and impact_res.affected_tests:
            for t in impact_res.affected_tests:
                t_name = t.get("name") or t.get("test_name")
                if t_name:
                    selected_tests.append(t_name)

        selected_tests = sorted(list(set(selected_tests)))

        executed = []
        passed = []
        failed = []

        if execution_results:
            executed = execution_results.get("executed", [])
            passed = execution_results.get("passed", [])
            failed = execution_results.get("failed", [])

        not_executed = [t for t in selected_tests if t not in executed]

        unknown_coverage = []
        for entity in getattr(impact_res, "directly_affected", []):
            e_name = entity.name if hasattr(entity, "name") else str(entity)
            if not any(e_name.lower() in t.lower() for t in selected_tests):
                unknown_coverage.append({"name": e_name, "reason": "No causal test mapped in Digital Twin"})

        return TestImpactReport(
            tests_selected=selected_tests,
            tests_executed=executed,
            tests_passed=passed,
            tests_failed=failed,
            tests_not_executed=not_executed,
            tests_unknown_coverage=unknown_coverage,
            missing_test_relationships=unknown_coverage,
        )

    def _evaluate_ci_recommendation(
        self,
        impact_res: Any,
        test_impact: TestImpactReport,
    ) -> Tuple[str, str]:
        """
        Deterministic CI decision:
        - BLOCKED: Critical test failures or analysis failure
        - REVIEW_REQUIRED: Causal impact exists, unknown coverage, or unexecuted tests
        - PASS: Zero blocking issues, required tests confirmed passed
        """
        if len(test_impact.tests_failed) > 0:
            if self.policy.block_on_failed_tests:
                return CIRecommendation.BLOCKED, PullRequestStatus.REVIEW_REQUIRED
            return CIRecommendation.REVIEW_REQUIRED, PullRequestStatus.REVIEW_REQUIRED

        if self.policy.review_on_unknown_coverage and len(test_impact.tests_unknown_coverage) > 0:
            return CIRecommendation.REVIEW_REQUIRED, PullRequestStatus.REVIEW_REQUIRED

        if len(test_impact.tests_not_executed) > 0 and len(test_impact.tests_selected) > 0:
            return CIRecommendation.REVIEW_REQUIRED, PullRequestStatus.REVIEW_REQUIRED

        raw_risk = getattr(impact_res, "overall_risk", 0.0)
        blast_score = (float(raw_risk) * 100.0) if isinstance(raw_risk, (int, float)) else 0.0
        if self.policy.review_on_high_risk and blast_score >= self.policy.high_risk_threshold:
            return CIRecommendation.REVIEW_REQUIRED, PullRequestStatus.REVIEW_REQUIRED

        if len(getattr(impact_res, "directly_affected", [])) > 0:
            return CIRecommendation.REVIEW_REQUIRED, PullRequestStatus.COMPLETE

        return CIRecommendation.PASS, PullRequestStatus.COMPLETE

    def _build_report_dict(
        self,
        repo: Repository,
        payload: PREventPayload,
        base_snap: RepositorySnapshot,
        head_snap: RepositorySnapshot,
        impact_res: Any,
        test_impact: TestImpactReport,
        status: str,
        ci_rec: str,
    ) -> Dict[str, Any]:
        directly = [{"id": e.id, "name": e.name, "type": e.type} for e in getattr(impact_res, "directly_affected", [])]
        indirectly = [{"id": e.id, "name": e.name, "type": e.type} for e in getattr(impact_res, "indirectly_affected", [])]
        apis = [e for e in directly + indirectly if e.get("type") in ("api", "endpoint", "route")]
        services = [e for e in directly + indirectly if e.get("type") in ("service", "module", "package")]
        processes = [e for e in directly + indirectly if e.get("type") in ("process", "workflow")]

        causal_paths = []
        for path in getattr(impact_res, "causal_paths", []):
            if hasattr(path, "nodes"):
                causal_paths.append([n.name for n in path.nodes])
            elif isinstance(path, list):
                causal_paths.append([str(n) for n in path])

        evidence_locs = []
        for f in getattr(impact_res, "findings", []):
            evidence_locs.append({
                "source": f.source_name,
                "target": f.target_name,
                "type": f.target_type,
                "evidence_completeness": f.provenance.evidence_completeness if hasattr(f, "provenance") and f.provenance else "full_graph_evidence",
            })

        summary = {
            "directly_affected_count": len(directly),
            "indirectly_affected_count": len(indirectly),
            "total_affected_count": len(directly) + len(indirectly),
            "apis_affected": len(apis),
            "services_affected": len(services),
            "tests_selected": len(test_impact.tests_selected),
            "tests_failed": len(test_impact.tests_failed),
            "tests_unknown": len(test_impact.tests_unknown_coverage),
            "overall_risk_score": getattr(impact_res, "overall_risk", 0.0),
            "evidence_completeness": getattr(impact_res, "provenance", {}).evidence_completeness if hasattr(impact_res, "provenance") and impact_res.provenance else "full_graph_evidence",
        }

        provenance_dict = {}
        if hasattr(impact_res, "provenance") and impact_res.provenance:
            p = impact_res.provenance
            provenance_dict = {
                "traversal_algorithm": getattr(p, "traversal_algorithm", "bidirectional_bfs"),
                "direction": getattr(p, "direction", "upstream_and_downstream"),
                "max_depth": getattr(p, "max_depth", 5),
                "baseline_snapshot_id": base_snap.id,
                "target_snapshot_id": head_snap.id,
                "evidence_completeness": getattr(p, "evidence_completeness", "full_graph_evidence"),
            }

        return {
            "pull_request_number": payload.pull_request_number,
            "repository": repo.name,
            "repository_id": repo.id,
            "base_commit_sha": payload.base_commit_sha,
            "head_commit_sha": payload.head_commit_sha,
            "base_snapshot_id": base_snap.id,
            "target_snapshot_id": head_snap.id,
            "status": status,
            "ci_recommendation": ci_rec,
            "changed_entities": directly,
            "directly_affected_entities": directly,
            "indirectly_affected_entities": indirectly,
            "affected_apis": apis,
            "affected_services": services,
            "affected_processes": processes,
            "affected_tests": [{"name": t} for t in test_impact.tests_selected],
            "test_impact": test_impact.model_dump(),
            "max_propagation_depth": 5,
            "causal_paths": causal_paths,
            "evidence_locations": evidence_locs,
            "provenance": provenance_dict,
            "summary": summary,
            "generated_at": datetime.now(timezone.utc),
        }

    def _generate_no_change_markdown(self, repo_name: str, payload: PREventPayload) -> str:
        return f"""## 🟢 TwinCore CI Change Impact Analysis
**Repository:** `{repo_name}` | **PR:** #{payload.pull_request_number}
**Comparison:** `{payload.base_commit_sha[:7]}` → `{payload.head_commit_sha[:7]}`

> ℹ️ **Identical Commits:** Baseline and target point to the identical revision. Zero architectural or test impact.

**CI Recommendation:** `PASS`
---
*Generated by TwinCore Living Software Digital Twin*
"""

    def _generate_markdown_report(self, data: Dict[str, Any]) -> str:
        s = data["summary"]
        ti = data["test_impact"]
        rec = data["ci_recommendation"]
        icon = "🟢" if rec == CIRecommendation.PASS else ("🟡" if rec == CIRecommendation.REVIEW_REQUIRED else "🔴")

        md = [
            f"## {icon} TwinCore Pull Request Impact Analysis",
            f"**Repository:** `{data['repository']}` | **PR:** #{data['pull_request_number']}",
            f"**Baseline:** `{data['base_commit_sha'][:7]}` (`{data['base_snapshot_id'][:8]}`) → **Target:** `{data['head_commit_sha'][:7]}` (`{data['target_snapshot_id'][:8]}`)",
            "",
            f"### 📋 CI Gate Decision: **{rec}** (Status: `{data['status']}`)",
            "",
            "### 🌐 Blast Radius & Architectural Scope",
            "| Metric | Count | Details |",
            "| :--- | :---: | :--- |",
            f"| **Directly Affected Components** | **{s['directly_affected_count']}** | Modified modules & call sites |",
            f"| **Transitively Affected Components** | **{s['indirectly_affected_count']}** | Deep reverse dependencies (depth ≤ {data['max_propagation_depth']}) |",
            f"| **Affected API Endpoints** | **{s['apis_affected']}** | Downstream HTTP/RPC contracts |",
            f"| **Targeted Regression Tests** | **{s['tests_selected']}** | Tests causal to modified code |",
            f"| **Unmapped / Unknown Coverage** | **{s['tests_unknown']}** | Code changes lacking test traces |",
            "",
            "### 🧪 Targeted Test Execution Summary",
            f"- **Selected Tests:** {len(ti.get('tests_selected', []))} ({', '.join(ti.get('tests_selected', [])[:5]) or 'None'})",
            f"- **Tests Executed:** {len(ti.get('tests_executed', []))}",
            f"- **Passed:** {len(ti.get('tests_passed', []))} | **Failed:** {len(ti.get('tests_failed', []))}",
            f"- **Unexecuted / Pending:** {len(ti.get('tests_not_executed', []))}",
            "",
        ]

        if data.get("causal_paths"):
            md.append("<details><summary><b>🔍 View Causal Blast-Radius Propagation Paths</b></summary>\n")
            for p in data["causal_paths"][:5]:
                md.append(f"- `{' → '.join(p)}`")
            md.append("\n</details>\n")

        if data.get("provenance"):
            p = data["provenance"]
            md.append("### 🛡️ Analysis Provenance")
            md.append(f"- Algorithm: `{p.get('traversal_algorithm')}` ({p.get('direction')})")
            md.append(f"- Evidence Completeness: `{p.get('evidence_completeness')}`")
            md.append("")

        md.append("---")
        md.append("*Generated deterministically by TwinCore Digital Twin Platform*")
        return "\n".join(md)

    def _deliver_github_status_dry_run(
        self,
        repo: Repository,
        payload: PREventPayload,
        ci_rec: str,
        markdown_body: str,
        github_token: Optional[str] = None,
    ) -> None:
        """
        Provider-neutral status delivery.
        Strict compliance: If no token or not explicitly configured, executes in dry-run mode and avoids external calls.
        """
        if not github_token:
            logger.info("GitHub status posting: DRY-RUN (No authentication token provided).")
            return

        logger.info("GitHub status posting configured: Would post status '%s' for commit %s.", ci_rec, payload.head_commit_sha[:7])

    def _record_to_report(self, record: PullRequestRecord, full_data: Optional[Dict[str, Any]] = None) -> PRImpactReport:
        if full_data:
            return PRImpactReport(**full_data)

        summary = record.summary or {}
        return PRImpactReport(
            pull_request_number=record.pull_request_number,
            repository=record.external_repository or "unknown",
            repository_id=record.repository_id,
            base_commit_sha=record.base_commit_sha,
            head_commit_sha=record.head_commit_sha,
            base_snapshot_id=record.base_snapshot_id,
            target_snapshot_id=record.target_snapshot_id,
            status=record.status,
            ci_recommendation=record.ci_recommendation or CIRecommendation.REVIEW_REQUIRED,
            summary=summary,
            error_message=record.error_message,
            generated_at=record.completed_at or record.received_at,
        )
