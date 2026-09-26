import uuid
from datetime import datetime
from typing import List
from app.services.discovery.scanner import FileInventory
from app.services.discovery.models import AnalysisPlanResult
from app.services.analysis.runtime.context import AnalysisContext
from app.services.analysis.runtime.result import (
    AnalysisRunResult,
    ExtractedArtifact,
    ExtractedRelationship,
    ExtractedEvidence,
)
from app.services.analysis.runtime.dispatcher import analyzer_dispatcher


class AnalyzerRunner:
    """Executes the selected structural analyzers and coordinates artifact aggregation."""

    def run(
        self,
        context: AnalysisContext,
        plan: AnalysisPlanResult,
        inventory: FileInventory,
    ) -> AnalysisRunResult:
        run_id = context.run_id or str(uuid.uuid4())
        started_at = datetime.utcnow()

        selected_analyzers = analyzer_dispatcher.select_analyzers_for_plan(plan, inventory)

        all_artifacts: List[ExtractedArtifact] = []
        all_relationships: List[ExtractedRelationship] = []
        all_evidence: List[ExtractedEvidence] = []
        all_warnings: List[str] = []
        all_errors: List[str] = []
        executed_analyzer_names: List[str] = []

        # Dedup map for artifacts by ID to guarantee idempotency in memory
        artifact_id_map = {}
        relationship_id_map = {}

        for analyzer in selected_analyzers:
            executed_analyzer_names.append(analyzer.name)
            try:
                arts, rels, evs, warns = analyzer.analyze_repository(context, inventory)

                # Merge artifacts with stable deduplication
                for art in arts:
                    if art.id not in artifact_id_map:
                        artifact_id_map[art.id] = art
                        all_artifacts.append(art)

                # Merge relationships with stable deduplication
                for rel in rels:
                    if rel.id not in relationship_id_map:
                        relationship_id_map[rel.id] = rel
                        all_relationships.append(rel)

                all_evidence.extend(evs)
                all_warnings.extend(warns)

            except Exception as exc:
                all_errors.append(f"Analyzer '{analyzer.name}' encountered failure: {str(exc)}")

        completed_at = datetime.utcnow()
        status = "COMPLETED"
        if all_errors:
            status = "PARTIAL" if all_artifacts else "FAILED"
        elif all_warnings:
            status = "COMPLETED"

        summary = {
            "total_artifacts": len(all_artifacts),
            "total_relationships": len(all_relationships),
            "total_evidence_records": len(all_evidence),
            "warnings_count": len(all_warnings),
            "errors_count": len(all_errors),
            "analyzers_executed": executed_analyzer_names,
            "duration_seconds": round((completed_at - started_at).total_seconds(), 3),
        }

        return AnalysisRunResult(
            run_id=run_id,
            repository_id=context.repository_id,
            snapshot_id=context.snapshot_id,
            status=status,
            started_at=started_at,
            completed_at=completed_at,
            analyzer_names=executed_analyzer_names,
            files_scanned=inventory.total_files,
            artifacts=all_artifacts,
            relationships=all_relationships,
            evidence_items=all_evidence,
            warnings=all_warnings,
            errors=all_errors,
            summary=summary,
        )


analyzer_runner = AnalyzerRunner()
