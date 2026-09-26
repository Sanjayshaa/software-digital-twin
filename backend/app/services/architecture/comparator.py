from typing import List, Dict, Tuple
from app.services.architecture.models import (
    ArchitectureConformanceReport,
    ArchitectureDrift,
    DriftStatus,
    SnapshotComparisonResult,
)


class SnapshotDriftComparator:
    """
    Compares architectural conformance and drift between two snapshots (A -> B).
    Identifies newly introduced violations, resolved violations, and net conformance trajectory.
    """

    def compare_reports(
        self,
        report_a: ArchitectureConformanceReport,
        report_b: ArchitectureConformanceReport,
    ) -> SnapshotComparisonResult:
        snap_a_id = report_a.snapshot_id or "snapshot_A"
        snap_b_id = report_b.snapshot_id or "snapshot_B"

        # Key drifts by unique architectural signature (category, source, target, file)
        def drift_key(d: ArchitectureDrift) -> Tuple[str, str, str, str]:
            cat_str = str(getattr(d.category, "value", d.category))
            return (cat_str, d.source, d.target, d.file or d.file_path)

        drifts_a = {drift_key(d): d for d in report_a.drifts}
        drifts_b = {drift_key(d): d for d in report_b.drifts}

        new_drifts: List[ArchitectureDrift] = []
        resolved_drifts: List[ArchitectureDrift] = []
        unaltered_drifts: List[ArchitectureDrift] = []

        # Find new drifts in B
        for k, d in drifts_b.items():
            if k not in drifts_a:
                new_d = d.model_copy()
                new_d.status = DriftStatus.DETECTED
                new_drifts.append(new_d)
            else:
                unaltered_drifts.append(d)

        # Find resolved drifts from A that are absent in B
        for k, d in drifts_a.items():
            if k not in drifts_b:
                resolved_d = d.model_copy()
                resolved_d.status = DriftStatus.RESOLVED
                resolved_drifts.append(resolved_d)

        delta = round(report_b.conformance_percentage - report_a.conformance_percentage, 2)

        summary = (
            f"Comparison {snap_a_id} -> {snap_b_id}: "
            f"{len(new_drifts)} new architectural drifts, "
            f"{len(resolved_drifts)} resolved drifts, "
            f"{len(unaltered_drifts)} unchanged. "
            f"Conformance changed from {report_a.conformance_percentage}% to {report_b.conformance_percentage}% "
            f"(delta: {'+' if delta >= 0 else ''}{delta}%)."
        )

        return SnapshotComparisonResult(
            snapshot_a=snap_a_id,
            snapshot_b=snap_b_id,
            new_drifts=new_drifts,
            resolved_drifts=resolved_drifts,
            unaltered_drifts=unaltered_drifts,
            conformance_a=report_a.conformance_percentage,
            conformance_b=report_b.conformance_percentage,
            conformance_delta=delta,
            summary=summary,
        )


snapshot_drift_comparator = SnapshotDriftComparator()
