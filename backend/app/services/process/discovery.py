import time
import uuid
from typing import List, Dict, Any, Optional, Set
from sqlalchemy.orm import Session

from app.models.entities import (
    StructuralArtifact,
    ArtifactRelationship,
    ProcessDefinition,
    ProcessStep,
    ProcessTransition,
)
from app.services.process.models import (
    ProcessEvidenceStatus,
    ProcessTransitionType,
    ProcessStepModel,
    ProcessTransitionModel,
    ProcessModel,
    ProcessDiscoveryResult,
)


def _generate_deterministic_id(seed: str) -> str:
    namespace = uuid.UUID("a3b8c9d0-1234-5678-9abc-def012345678")
    return str(uuid.uuid5(namespace, seed))


class ProcessDiscoveryEngine:
    """
    Deterministic Process Discovery & Inference Engine.
    Discovers business and API execution workflows by traversing AST structural
    artifacts and typed invocation relationships.
    """

    def discover_and_persist(
        self,
        db: Session,
        project_id: str,
        repository_id: str,
        snapshot_id: str,
    ) -> ProcessDiscoveryResult:
        start_time = time.perf_counter()

        # Check if processes already persisted for this snapshot
        existing_defs = (
            db.query(ProcessDefinition)
            .filter_by(repository_id=repository_id, snapshot_id=snapshot_id)
            .all()
        )
        if existing_defs:
            # Already discovered and persisted
            processes = [self._entity_to_model(p) for p in existing_defs]
            total_steps = sum(p.steps_count for p in processes)
            total_transitions = sum(p.transitions_count for p in processes)
            elapsed = (time.perf_counter() - start_time) * 1000.0
            return ProcessDiscoveryResult(
                repository_id=repository_id,
                snapshot_id=snapshot_id,
                total_processes=len(processes),
                total_steps=total_steps,
                total_transitions=total_transitions,
                processes=processes,
                execution_time_ms=round(elapsed, 2),
            )

        # 1. Fetch artifacts and relationships
        artifacts = (
            db.query(StructuralArtifact)
            .filter_by(snapshot_id=snapshot_id)
            .all()
        )
        relationships = (
            db.query(ArtifactRelationship)
            .filter_by(snapshot_id=snapshot_id)
            .all()
        )

        art_map = {a.id: a for a in artifacts}
        rel_map: Dict[str, List[ArtifactRelationship]] = {}
        for r in relationships:
            rel_map.setdefault(r.source_artifact_id, []).append(r)

        # 2. Identify Entrypoints
        entry_points = self._identify_entry_points(artifacts)

        created_processes: List[ProcessDefinition] = []

        for entry in entry_points:
            proc_id = _generate_deterministic_id(f"proc_{repository_id}_{snapshot_id}_{entry.id}")
            proc_name = f"Process: {entry.name}"
            description = f"Inferred execution workflow initiated by entrypoint {entry.qualified_name or entry.name}"

            proc_def = ProcessDefinition(
                id=proc_id,
                project_id=project_id,
                repository_id=repository_id,
                snapshot_id=snapshot_id,
                name=proc_name,
                description=description,
                process_type="api_workflow" if entry.artifact_type == "API_ENDPOINT" else "service_workflow",
                metadata_payload={
                    "evidence_status": ProcessEvidenceStatus.INFERRED.value,
                    "confidence": 0.85,
                    "detection_method": "STATIC_AST_ENTRYPOINT_TRACING",
                    "entrypoint_artifact_id": entry.id,
                },
            )
            db.add(proc_def)

            # Traverse downstream chain (max depth 4, cycle guarded)
            visited_art_ids: Set[str] = set()
            steps_data: List[ProcessStep] = []
            transitions_data: List[ProcessTransition] = []

            queue = [(entry, 0, None)]  # (artifact, depth, parent_step_id)
            visited_art_ids.add(entry.id)
            step_order = 0

            step_id_map: Dict[str, str] = {}  # art_id -> step_id

            while queue and step_order < 15:
                curr_art, depth, parent_step_id = queue.pop(0)

                step_id = _generate_deterministic_id(f"step_{proc_id}_{curr_art.id}_{step_order}")
                step_id_map[curr_art.id] = step_id

                step_type = self._determine_step_type(curr_art, step_order)
                source_file, line_num = self._extract_source_location(curr_art)

                step_entity = ProcessStep(
                    id=step_id,
                    process_id=proc_id,
                    step_order=step_order,
                    name=curr_art.name,
                    component_artifact_id=curr_art.id,
                    step_type=step_type,
                    metadata_payload={
                        "evidence_status": ProcessEvidenceStatus.INFERRED.value,
                        "confidence": 0.85 if depth == 0 else max(0.60, 0.85 - (depth * 0.05)),
                        "detection_method": "STATIC_AST_CALL_CHAIN",
                        "operation": curr_art.artifact_type,
                        "source_file": source_file,
                        "line_number": line_num,
                    },
                )
                db.add(step_entity)
                steps_data.append(step_entity)

                if parent_step_id is not None:
                    trans_id = _generate_deterministic_id(f"trans_{proc_id}_{parent_step_id}_{step_id}")
                    trans_entity = ProcessTransition(
                        id=trans_id,
                        process_id=proc_id,
                        from_step_id=parent_step_id,
                        to_step_id=step_id,
                        transition_condition=None,
                        metadata_payload={
                            "transition_type": ProcessTransitionType.CALLS.value,
                            "confidence": 0.85,
                            "evidence_status": ProcessEvidenceStatus.INFERRED.value,
                        },
                    )
                    db.add(trans_entity)
                    transitions_data.append(trans_entity)

                step_order += 1

                if depth < 4:
                    out_rels = rel_map.get(curr_art.id, [])
                    for r in out_rels:
                        if r.relationship_type in ("CALLS", "DEPENDS_ON", "EXPOSES", "CONSUMES", "PERSISTS_TO"):
                            tgt_art = art_map.get(r.target_artifact_id)
                            if tgt_art and tgt_art.id not in visited_art_ids:
                                visited_art_ids.add(tgt_art.id)
                                queue.append((tgt_art, depth + 1, step_id))

            created_processes.append(proc_def)

        db.commit()

        processes = [self._entity_to_model(p) for p in created_processes]
        total_steps = sum(p.steps_count for p in processes)
        total_transitions = sum(p.transitions_count for p in processes)
        elapsed = (time.perf_counter() - start_time) * 1000.0

        return ProcessDiscoveryResult(
            repository_id=repository_id,
            snapshot_id=snapshot_id,
            total_processes=len(processes),
            total_steps=total_steps,
            total_transitions=total_transitions,
            processes=processes,
            execution_time_ms=round(elapsed, 2),
        )

    def _identify_entry_points(self, artifacts: List[StructuralArtifact]) -> List[StructuralArtifact]:
        """Identifies candidate process entry points from structural artifacts."""
        entry_points = []
        for a in artifacts:
            type_upper = (a.artifact_type or "").upper()
            name_lower = (a.name or "").lower()
            loc_lower = (a.location or "").lower()

            # API Endpoints
            if "API" in type_upper or "ENDPOINT" in type_upper or "route" in loc_lower:
                entry_points.append(a)
            # Controller, Handler, Service or Dispatch classes/methods
            elif any(k in name_lower or k in loc_lower for k in ("controller", "handler", "router", "dispatch", "service", "process")):
                if type_upper in ("FUNCTION", "METHOD", "CLASS", "INTERFACE"):
                    entry_points.append(a)

        if not entry_points:
            # Fallback to public services, classes, or top-level functions
            for a in artifacts:
                type_up = (a.artifact_type or "").upper()
                if type_up in ("CLASS", "MODULE", "FUNCTION", "METHOD") and "test" not in a.name.lower() and "test" not in (a.location or "").lower():
                    entry_points.append(a)
                if len(entry_points) >= 5:
                    break

        return entry_points[:10]  # Cap candidate entry points to 10 distinct workflows

    def _determine_step_type(self, artifact: StructuralArtifact, step_order: int) -> str:
        if step_order == 0:
            return "entrypoint"
        name_lower = artifact.name.lower()
        if any(db_kw in name_lower for db_kw in ("repo", "repository", "db", "database", "dao", "table", "store")):
            return "database_op"
        if any(ext_kw in name_lower for ext_kw in ("client", "external", "remote", "http", "api")):
            return "external_call"
        if any(val_kw in name_lower for val_kw in ("validate", "check", "verify", "auth", "guard")):
            return "validation"
        return "action"

    def _extract_source_location(self, artifact: StructuralArtifact):
        source_file = None
        line_num = None
        if artifact.location:
            parts = artifact.location.split(":")
            source_file = parts[0]
            if len(parts) > 1 and parts[1].isdigit():
                line_num = int(parts[1])
        return source_file, line_num

    def _entity_to_model(self, proc: ProcessDefinition) -> ProcessModel:
        steps_models = []
        for s in proc.steps:
            steps_models.append(
                ProcessStepModel(
                    id=s.id,
                    process_id=s.process_id,
                    step_order=s.step_order,
                    name=s.name,
                    component_artifact_id=s.component_artifact_id,
                    step_type=s.step_type,
                    operation=s.metadata_payload.get("operation"),
                    source_file=s.metadata_payload.get("source_file"),
                    line_number=s.metadata_payload.get("line_number"),
                    confidence=s.metadata_payload.get("confidence", 0.85),
                    evidence_status=ProcessEvidenceStatus(s.metadata_payload.get("evidence_status", "INFERRED")),
                    detection_method=s.metadata_payload.get("detection_method", "STATIC_AST_CALL_CHAIN"),
                    metadata_payload=s.metadata_payload,
                )
            )

        transitions_models = []
        for t in proc.transitions:
            transitions_models.append(
                ProcessTransitionModel(
                    id=t.id,
                    process_id=t.process_id,
                    from_step_id=t.from_step_id,
                    to_step_id=t.to_step_id,
                    transition_type=t.metadata_payload.get("transition_type", "CALLS"),
                    transition_condition=t.transition_condition,
                    confidence=t.metadata_payload.get("confidence", 0.85),
                    evidence_status=ProcessEvidenceStatus(t.metadata_payload.get("evidence_status", "INFERRED")),
                    metadata_payload=t.metadata_payload,
                )
            )

        return ProcessModel(
            id=proc.id,
            project_id=proc.project_id,
            repository_id=proc.repository_id,
            snapshot_id=proc.snapshot_id,
            name=proc.name,
            description=proc.description,
            process_type=proc.process_type,
            evidence_status=ProcessEvidenceStatus(proc.metadata_payload.get("evidence_status", "INFERRED")),
            confidence=proc.metadata_payload.get("confidence", 0.85),
            steps_count=len(steps_models),
            transitions_count=len(transitions_models),
            steps=steps_models,
            transitions=transitions_models,
            metadata_payload=proc.metadata_payload,
            created_at=proc.created_at,
        )


process_discovery_engine = ProcessDiscoveryEngine()
