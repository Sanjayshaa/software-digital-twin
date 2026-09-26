import os
from typing import Optional, List
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.entities import (
    ArchitectureReportEntity,
    ArchitectureDriftEntity,
    RepositorySnapshot,
)
from app.services.architecture.models import (
    ArchitectureConformanceReport,
    ArchitectureDrift,
    DriftCategory,
    DriftSeverity,
    DriftStatus,
    SnapshotComparisonResult,
)
from app.services.architecture.detector import architecture_drift_detector
from app.services.architecture.comparator import snapshot_drift_comparator


class ArchitectureService:
    """
    Coordinates baseline validation, concrete AST drift detection,
    database persistence, and snapshot comparisons.
    """

    def __init__(self):
        # Default baseline path in docs/
        self.default_baseline_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "docs", "architecture-baseline.yaml")
        )

    def evaluate_repository(
        self,
        repository_path: str,
        baseline_path: Optional[str] = None,
        snapshot_id: Optional[str] = None,
        repository_id: Optional[str] = None,
    ) -> ArchitectureConformanceReport:
        """Evaluates architecture drift for a target repository against baseline."""
        target_baseline = baseline_path or self.default_baseline_path
        if not os.path.exists(target_baseline):
            raise FileNotFoundError(f"Architecture baseline file not found at: {target_baseline}")

        spec = architecture_drift_detector.load_baseline(target_baseline)
        report = architecture_drift_detector.detect_drift(
            repository_path=repository_path,
            snapshot_id=snapshot_id,
            baseline=spec,
        )
        report.repository_id = repository_id
        return report

    def persist_report(
        self,
        db: Session,
        report: ArchitectureConformanceReport,
        repository_id: str,
        snapshot_id: Optional[str] = None,
    ) -> ArchitectureReportEntity:
        """Persists the conformance report and all detected drifts into PostgreSQL."""
        entity = ArchitectureReportEntity(
            repository_id=repository_id,
            snapshot_id=snapshot_id or report.snapshot_id,
            baseline_version=report.baseline_version,
            expected_boundaries=report.expected_boundaries,
            validated_boundaries=report.validated_boundaries,
            violations_count=report.violations,
            circular_count=report.circular_dependencies,
            unexpected_count=report.unexpected_dependencies,
            conformance_percentage=report.conformance_percentage,
            summary=report.summary,
            created_at=datetime.utcnow(),
        )
        db.add(entity)
        db.flush()

        for d in report.drifts:
            drift_entity = ArchitectureDriftEntity(
                id=d.drift_id,
                report_id=entity.id,
                repository_id=repository_id,
                snapshot_id=snapshot_id or report.snapshot_id,
                category=str(getattr(d.category, "value", d.category)),
                severity=str(getattr(d.severity, "value", d.severity)),
                source=d.source,
                target=d.target,
                relationship_type=d.relationship or d.relationship_type or "import",
                expected_rule=d.expected_rule,
                actual_evidence=d.actual_evidence,
                file_path=d.file or d.file_path or "",
                line_number=d.line or d.line_number or 1,
                confidence=d.confidence,
                status=str(getattr(d.status, "value", d.status)),
                created_at=datetime.utcnow(),
            )
            db.add(drift_entity)

        db.commit()
        db.refresh(entity)
        return entity

    def get_latest_report(
        self,
        db: Session,
        repository_id: str,
    ) -> Optional[ArchitectureConformanceReport]:
        """Fetches the most recent architecture conformance report for a repository."""
        entity = (
            db.query(ArchitectureReportEntity)
            .filter_by(repository_id=repository_id)
            .order_by(ArchitectureReportEntity.created_at.desc())
            .first()
        )
        if not entity:
            return None

        drifts = []
        for d in entity.drifts:
            drifts.append(
                ArchitectureDrift(
                    drift_id=d.id,
                    category=DriftCategory(d.category),
                    severity=DriftSeverity(d.severity),
                    source=d.source,
                    target=d.target,
                    relationship=d.relationship_type,
                    expected_rule=d.expected_rule,
                    actual_evidence=d.actual_evidence,
                    file=d.file_path,
                    line=d.line_number,
                    snapshot=d.snapshot_id,
                    confidence=d.confidence,
                    status=DriftStatus(d.status),
                )
            )

        return ArchitectureConformanceReport(
            report_id=entity.id,
            repository_id=entity.repository_id,
            snapshot_id=entity.snapshot_id,
            expected_boundaries=entity.expected_boundaries,
            validated_boundaries=entity.validated_boundaries,
            violations=entity.violations_count,
            circular_dependencies=entity.circular_count,
            unexpected_dependencies=entity.unexpected_count,
            conformance_percentage=entity.conformance_percentage,
            drifts=drifts,
            baseline_version=entity.baseline_version,
            summary=entity.summary or "",
            evaluated_at=entity.created_at.isoformat(),
        )

    def compare_snapshots(
        self,
        db: Session,
        snapshot_a_id: str,
        snapshot_b_id: str,
    ) -> SnapshotComparisonResult:
        """Compares architecture drift reports between two snapshots in PostgreSQL."""
        rep_a_entity = (
            db.query(ArchitectureReportEntity)
            .filter_by(snapshot_id=snapshot_a_id)
            .order_by(ArchitectureReportEntity.created_at.desc())
            .first()
        )
        rep_b_entity = (
            db.query(ArchitectureReportEntity)
            .filter_by(snapshot_id=snapshot_b_id)
            .order_by(ArchitectureReportEntity.created_at.desc())
            .first()
        )

        if not rep_a_entity:
            raise ValueError(f"No architecture conformance report found for snapshot '{snapshot_a_id}'")
        if not rep_b_entity:
            raise ValueError(f"No architecture conformance report found for snapshot '{snapshot_b_id}'")

        def entity_to_report(ent: ArchitectureReportEntity) -> ArchitectureConformanceReport:
            drifts = [
                ArchitectureDrift(
                    drift_id=d.id,
                    category=DriftCategory(d.category),
                    severity=DriftSeverity(d.severity),
                    source=d.source,
                    target=d.target,
                    relationship=d.relationship_type,
                    expected_rule=d.expected_rule,
                    actual_evidence=d.actual_evidence,
                    file=d.file_path,
                    line=d.line_number,
                    snapshot=d.snapshot_id,
                    confidence=d.confidence,
                    status=DriftStatus(d.status),
                )
                for d in ent.drifts
            ]
            return ArchitectureConformanceReport(
                report_id=ent.id,
                repository_id=ent.repository_id,
                snapshot_id=ent.snapshot_id,
                expected_boundaries=ent.expected_boundaries,
                validated_boundaries=ent.validated_boundaries,
                violations=ent.violations_count,
                circular_dependencies=ent.circular_count,
                unexpected_dependencies=ent.unexpected_count,
                conformance_percentage=ent.conformance_percentage,
                drifts=drifts,
                baseline_version=ent.baseline_version,
                summary=ent.summary or "",
                evaluated_at=ent.created_at.isoformat(),
            )

        rep_a = entity_to_report(rep_a_entity)
        rep_b = entity_to_report(rep_b_entity)

        return snapshot_drift_comparator.compare_reports(rep_a, rep_b)


architecture_service = ArchitectureService()
