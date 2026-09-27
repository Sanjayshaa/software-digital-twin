import uuid
import networkx as nx
from datetime import datetime
from typing import List, Dict, Any, Optional, Set
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.entities import (
    Incident,
    RuntimeEvent,
    StructuralArtifact,
    ArtifactRelationship,
    ProcessStep,
    ProcessDefinition,
    RepositorySnapshot,
    IncidentEvidenceLink,
)
from app.services.impact.change_detector import change_detector
from app.services.incident.models import (
    InvestigationResult,
    IncidentResponse,
    CandidateCausalPath,
)


class IncidentInvestigator:
    """
    Deterministic Incident Correlation & Root-Cause Investigation Engine.
    Correlates runtime events with structural Digital Twin components, historical
    change diffs, process workflows, and test coverage to construct evidence-backed
    candidate causal paths without speculative hallucinations.
    """

    def investigate(self, db: Session, incident_id: str) -> InvestigationResult:
        incident = db.query(Incident).filter_by(id=incident_id).first()
        if not incident:
            raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")

        repo_id = incident.repository_id
        snap_id = incident.snapshot_id

        # If snapshot not on incident, resolve latest snapshot of repository
        if not snap_id and repo_id:
            latest_snap = (
                db.query(RepositorySnapshot)
                .filter_by(repository_id=repo_id)
                .order_by(RepositorySnapshot.created_at.desc())
                .first()
            )
            if latest_snap:
                snap_id = latest_snap.id
                incident.snapshot_id = snap_id

        # 1. Gather Linked Runtime Events
        linked_events = (
            db.query(RuntimeEvent)
            .filter_by(incident_id=incident_id)
            .order_by(RuntimeEvent.timestamp.desc())
            .all()
        )

        # If no events explicitly linked, query recent ERROR events around detected_at
        if not linked_events and repo_id:
            linked_events = (
                db.query(RuntimeEvent)
                .filter(
                    RuntimeEvent.repository_id == repo_id,
                    RuntimeEvent.severity.in_(["ERROR", "CRITICAL"]),
                )
                .order_by(RuntimeEvent.timestamp.desc())
                .limit(10)
                .all()
            )

        # 2. Determine Affected Component
        affected_art_id = incident.affected_component_id
        if not affected_art_id and linked_events:
            for ev in linked_events:
                if ev.component_artifact_id:
                    affected_art_id = ev.component_artifact_id
                    break

        affected_art = None
        if affected_art_id:
            affected_art = db.query(StructuralArtifact).filter_by(id=affected_art_id).first()

        # 3. Retrieve Snapshot Artifacts & Build Relationship Graph
        artifacts = db.query(StructuralArtifact).filter_by(snapshot_id=snap_id).all() if snap_id else []
        art_map = {a.id: a for a in artifacts}

        relationships = db.query(ArtifactRelationship).filter_by(snapshot_id=snap_id).all() if snap_id else []

        call_graph = nx.DiGraph()
        for a in artifacts:
            call_graph.add_node(a.id, name=a.name, type=a.artifact_type, location=a.location)

        for r in relationships:
            if r.relationship_type in ("CALLS", "DEPENDS_ON", "EXPOSES", "CONSUMES"):
                # Forward edge: Caller -> Callee
                call_graph.add_edge(r.source_artifact_id, r.target_artifact_id, rel_type=r.relationship_type)

        # 4. Correlate Recent Changes (Phase 4 ChangeDetector)
        candidate_changes: List[Dict[str, Any]] = []
        changed_art_ids: Set[str] = set()

        if repo_id:
            recent_snaps = (
                db.query(RepositorySnapshot)
                .filter_by(repository_id=repo_id)
                .order_by(RepositorySnapshot.created_at.desc())
                .limit(2)
                .all()
            )
            if len(recent_snaps) >= 2:
                base_snap = recent_snaps[1]
                target_snap = recent_snaps[0]
                diff_result = change_detector.detect_changes(
                    db=db,
                    repository_id=repo_id,
                    base_snapshot_id=base_snap.id,
                    target_snapshot_id=target_snap.id,
                )
                for item in diff_result.changes:
                    art_name = item.symbol_name or item.source_file
                    candidate_changes.append({
                        "change_type": item.change_type.value,
                        "artifact_id": item.artifact_id,
                        "artifact_name": art_name,
                        "file_path": item.source_file,
                        "is_symbol_level": item.is_symbol_level,
                        "source_hash_before": item.base_hash,
                        "source_hash_after": item.target_hash,
                    })
                    if item.artifact_id:
                        changed_art_ids.add(item.artifact_id)

        # 5. Construct Candidate Causal Paths
        candidate_causal_paths: List[CandidateCausalPath] = []
        path_idx = 1

        if affected_art:
            for chg in candidate_changes:
                chg_id = chg.get("artifact_id")
                if not chg_id:
                    continue

                chg_name = chg.get("artifact_name", "Unknown")
                chg_type = chg.get("change_type", "MODIFIED")

                if chg_id == affected_art.id:
                    # Direct modification on the incident component itself
                    candidate_causal_paths.append(
                        CandidateCausalPath(
                            path_id=f"path_{path_idx}",
                            changed_artifact_id=chg_id,
                            changed_artifact_name=chg_name,
                            change_type=chg_type,
                            target_incident_artifact_id=affected_art.id,
                            hop_count=0,
                            path_nodes=[{
                                "id": affected_art.id,
                                "name": affected_art.name,
                                "type": affected_art.artifact_type,
                                "location": affected_art.location,
                            }],
                            confidence=0.95,
                            explanation=f"Incident component {affected_art.name} was directly modified in recent deployment diff.",
                            evidence_status="DIRECT_MODIFICATION",
                            component_id=affected_art.id,
                            component_name=affected_art.name,
                            relationship="DIRECT",
                        )
                    )
                    path_idx += 1
                else:
                    # Check if changed artifact calls or is called by affected component
                    # 1. Upstream call chain: Changed -> ... -> Affected
                    path = None
                    if call_graph.has_node(chg_id) and call_graph.has_node(affected_art.id):
                        if nx.has_path(call_graph, chg_id, affected_art.id):
                            path = nx.shortest_path(call_graph, chg_id, affected_art.id)
                        elif nx.has_path(call_graph, affected_art.id, chg_id):
                            # Affected component calls changed artifact (downstream dependency failed)
                            path = nx.shortest_path(call_graph, affected_art.id, chg_id)

                    if path and len(path) <= 5:
                        hops = len(path) - 1
                        nodes_info = [
                            {
                                "id": nid,
                                "name": art_map[nid].name if nid in art_map else nid,
                                "type": art_map[nid].artifact_type if nid in art_map else "COMPONENT",
                                "location": art_map[nid].location if nid in art_map else None,
                            }
                            for nid in path
                        ]
                        conf = max(0.50, round(0.90 - (hops * 0.08), 2))
                        candidate_causal_paths.append(
                            CandidateCausalPath(
                                path_id=f"path_{path_idx}",
                                changed_artifact_id=chg_id,
                                changed_artifact_name=chg_name,
                                change_type=chg_type,
                                target_incident_artifact_id=affected_art.id,
                                hop_count=hops,
                                path_nodes=nodes_info,
                                confidence=conf,
                                explanation=(
                                    f"Causal chain of length {hops} connecting recently changed "
                                    f"{chg_name} with incident component {affected_art.name}."
                                ),
                                evidence_status="DERIVED_TOPOLOGICAL_CHAIN",
                                component_id=affected_art.id,
                                component_name=affected_art.name,
                                relationship="CALLS",
                            )
                        )
                        path_idx += 1

        # 6. Correlate Affected Processes
        affected_processes: List[Dict[str, Any]] = []
        if affected_art_id and snap_id:
            # Expire the session to ensure committed ProcessStep/ProcessDefinition records
            # from the discovery engine are visible (avoid SQLAlchemy identity map staleness)
            db.expire_all()
            steps = (
                db.query(ProcessStep)
                .join(ProcessDefinition, ProcessStep.process_id == ProcessDefinition.id)
                .filter(
                    ProcessDefinition.snapshot_id == snap_id,
                    ProcessStep.component_artifact_id == affected_art_id,
                )
                .all()
            )
            seen_proc_ids: Set[str] = set()
            for s in steps:
                if s.process_id not in seen_proc_ids:
                    seen_proc_ids.add(s.process_id)
                    proc = s.process
                    affected_processes.append({
                        "process_id": proc.id,
                        "name": proc.name,
                        "process_type": proc.process_type,
                        "step_name": s.name,
                        "step_order": s.step_order,
                    })

        # 7. Correlate Related Tests
        related_tests: List[Dict[str, Any]] = []
        target_art_ids = {affected_art_id} if affected_art_id else set()
        target_art_ids.update(changed_art_ids)

        if target_art_ids and snap_id:
            test_rels = (
                db.query(ArtifactRelationship)
                .filter(
                    ArtifactRelationship.snapshot_id == snap_id,
                    ArtifactRelationship.relationship_type == "TESTS",
                    ArtifactRelationship.target_artifact_id.in_(list(target_art_ids)),
                )
                .all()
            )
            for tr in test_rels:
                test_art = art_map.get(tr.source_artifact_id)
                tested_art = art_map.get(tr.target_artifact_id)
                if test_art:
                    related_tests.append({
                        "test_artifact_id": test_art.id,
                        "test_name": test_art.name,
                        "location": test_art.location,
                        "tests_component": tested_art.name if tested_art else tr.target_artifact_id,
                        "confidence": tr.confidence,
                    })

        # 8. Persist Incident Evidence Links
        # Clear existing links to keep fresh
        db.query(IncidentEvidenceLink).filter_by(incident_id=incident_id).delete()

        links_to_add: List[IncidentEvidenceLink] = []

        for ev in linked_events:
            links_to_add.append(
                IncidentEvidenceLink(
                    id=str(uuid.uuid4()),
                    incident_id=incident_id,
                    link_type="RUNTIME_EVENT",
                    target_id=ev.id,
                    target_type="RuntimeEvent",
                    confidence=0.90,
                    explanation=f"Runtime {ev.event_type} event: {ev.message or 'No message'}",
                    metadata_payload={"severity": ev.severity, "trace_id": ev.trace_id},
                )
            )

        if affected_art:
            links_to_add.append(
                IncidentEvidenceLink(
                    id=str(uuid.uuid4()),
                    incident_id=incident_id,
                    link_type="AFFECTED_COMPONENT",
                    target_id=affected_art.id,
                    target_type="StructuralArtifact",
                    confidence=0.90,
                    explanation=f"Correlated primary affected component: {affected_art.name}",
                    metadata_payload={"location": affected_art.location},
                )
            )

        for path in candidate_causal_paths:
            links_to_add.append(
                IncidentEvidenceLink(
                    id=str(uuid.uuid4()),
                    incident_id=incident_id,
                    link_type="CAUSAL_PATH",
                    target_id=path.changed_artifact_id,
                    target_type="CandidateCausalPath",
                    confidence=path.confidence,
                    explanation=path.explanation,
                    metadata_payload={"hop_count": path.hop_count, "change_type": path.change_type},
                )
            )

        for proc in affected_processes:
            links_to_add.append(
                IncidentEvidenceLink(
                    id=str(uuid.uuid4()),
                    incident_id=incident_id,
                    link_type="AFFECTED_PROCESS",
                    target_id=proc["process_id"],
                    target_type="ProcessDefinition",
                    confidence=0.85,
                    explanation=f"Workflow '{proc['name']}' participates with affected component.",
                    metadata_payload={"step_order": proc["step_order"]},
                )
            )

        if links_to_add:
            db.add_all(links_to_add)

        # Update incident metadata and status
        incident.status = "investigated" if candidate_causal_paths else "open"
        incident.metadata_payload = {
            "last_investigated_at": datetime.utcnow().isoformat(),
            "candidate_paths_count": len(candidate_causal_paths),
            "affected_processes_count": len(affected_processes),
            "related_tests_count": len(related_tests),
        }
        db.commit()

        # Format output
        obs_events_summary = [
            {
                "id": ev.id,
                "event_type": ev.event_type,
                "severity": ev.severity,
                "service_name": ev.service_name,
                "trace_id": ev.trace_id,
                "message": ev.message,
                "timestamp": ev.timestamp.isoformat() if ev.timestamp else None,
            }
            for ev in linked_events
        ]

        affected_comp_dict = None
        if affected_art:
            affected_comp_dict = {
                "id": affected_art.id,
                "name": affected_art.name,
                "qualified_name": affected_art.qualified_name,
                "type": affected_art.artifact_type,
                "location": affected_art.location,
            }

        # Build deterministic uncertainties based on evidence completeness
        uncertainties = []
        if not linked_events:
            uncertainties.append("No runtime events are linked to this incident.")
        if not candidate_changes:
            uncertainties.append("No recent code changes detected between baseline and target snapshots.")
        if not affected_art:
            uncertainties.append("No affected structural entity identified; correlation is unanchored.")
        if not related_tests:
            uncertainties.append("No automated tests directly cover the affected entity or candidate changed paths.")
        if not affected_processes:
            uncertainties.append("No inferred processes traverse the affected entity.")
        uncertainties.append("Causal paths are evidence-backed hypotheses derived from static call graphs and runtime correlation; runtime execution timing may differ.")

        inc_resp = IncidentResponse(
            id=incident.id,
            project_id=incident.project_id,
            repository_id=incident.repository_id,
            snapshot_id=incident.snapshot_id,
            title=incident.title,
            description=incident.description,
            severity=incident.severity,
            status=incident.status,
            environment=incident.environment,
            affected_component_id=incident.affected_component_id,
            affected_component_name=affected_art.name if affected_art else None,
            detected_at=incident.detected_at,
            resolved_at=incident.resolved_at,
            evidence_links_count=len(incident.evidence_links) if incident.evidence_links else 0,
            evidence_ids=[ev.id for ev in linked_events],
            metadata_payload=incident.metadata_payload or {},
        )

        return InvestigationResult(
            incident_id=incident.id,
            incident_title=incident.title,
            severity=incident.severity,
            environment=incident.environment,
            incident=inc_resp,
            affected_component=affected_comp_dict,
            affected_entities=[affected_comp_dict] if affected_comp_dict else [],
            observed_evidence=obs_events_summary,
            observed_runtime_events=obs_events_summary,
            affected_processes=affected_processes,
            candidate_recent_changes=candidate_changes,
            candidate_causal_paths=candidate_causal_paths,
            related_tests=related_tests,
            uncertainties=uncertainties,
            supporting_evidence_summary={
                "total_events_examined": len(linked_events),
                "total_candidate_changes": len(candidate_changes),
                "total_causal_paths": len(candidate_causal_paths),
                "total_affected_processes": len(affected_processes),
                "total_related_tests": len(related_tests),
            },
            investigation_timestamp=datetime.utcnow(),
        )


incident_investigator = IncidentInvestigator()
