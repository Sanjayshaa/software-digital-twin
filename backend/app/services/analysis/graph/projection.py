import os
import networkx as nx
from typing import Dict, Any, List, Optional, Set, Tuple
from sqlalchemy.orm import Session
from datetime import datetime

from app.models.entities import (
    Repository,
    RepositorySnapshot,
    StructuralArtifact,
    ArtifactRelationship,
    Evidence,
    AnalysisRun,
    File,
    ProcessDefinition,
    ProcessStep,
    ProcessTransition,
    ArchitectureReportEntity,
    ArchitectureDriftEntity,
)


class TwinGraphProjection:
    """
    Authoritative Digital Twin Graph Projection Service.
    Projects persisted PostgreSQL artifacts, relationships, evidence, process models,
    snapshots, and architecture drift into interactive visualization models.
    Strictly derives all nodes, edges, and evidence from persisted PostgreSQL records.
    Never invents mock edges or fake nodes.
    """

    def get_snapshots(self, db: Session, repository_id: str) -> List[Dict[str, Any]]:
        """Returns all snapshots for a given repository ordered by creation date desc."""
        snaps = (
            db.query(RepositorySnapshot)
            .filter_by(repository_id=repository_id)
            .order_by(RepositorySnapshot.created_at.desc())
            .all()
        )
        result = []
        for s in snaps:
            art_count = db.query(StructuralArtifact).filter_by(snapshot_id=s.id).count()
            rel_count = db.query(ArtifactRelationship).filter_by(snapshot_id=s.id).count()
            result.append({
                "id": s.id,
                "commit_hash": s.commit_hash,
                "branch_name": s.branch_name,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "artifacts_count": art_count,
                "relationships_count": rel_count,
            })
        return result

    def get_file_tree(self, db: Session, repository_id: str, snapshot_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Builds a hierarchical directory and file tree of files in the snapshot
        with artifact counts and primary artifact IDs for synchronized explorer navigation.
        """
        target_snap_id = snapshot_id or self._get_latest_snapshot_id(db, repository_id)
        if not target_snap_id:
            return {"name": "root", "type": "directory", "children": []}

        files = db.query(File).filter_by(repository_id=repository_id, snapshot_id=target_snap_id).all()
        artifacts = db.query(StructuralArtifact).filter_by(snapshot_id=target_snap_id).all()

        file_art_map: Dict[str, List[StructuralArtifact]] = {}
        for a in artifacts:
            loc_file = a.location.split(":")[0] if a.location else ""
            file_art_map.setdefault(loc_file, []).append(a)

        root: Dict[str, Any] = {
            "name": "repository",
            "type": "directory",
            "path": "",
            "children": {},
        }

        for f in files:
            parts = f.path.split("/")
            curr = root
            for idx, part in enumerate(parts[:-1]):
                prefix = "/".join(parts[: idx + 1])
                if part not in curr["children"]:
                    curr["children"][part] = {
                        "name": part,
                        "type": "directory",
                        "path": prefix,
                        "children": {},
                    }
                curr = curr["children"][part]

            file_name = parts[-1]
            arts = file_art_map.get(f.path, [])
            primary_id = arts[0].id if arts else None
            curr["children"][file_name] = {
                "name": file_name,
                "type": "file",
                "path": f.path,
                "language": f.language or (file_name.split(".")[-1] if "." in file_name else "text"),
                "line_count": f.line_count,
                "is_test": f.is_test,
                "artifacts_count": len(arts),
                "primary_artifact_id": primary_id,
                "artifact_ids": [a.id for a in arts],
            }

        def _dict_to_list(node: Dict[str, Any]) -> Dict[str, Any]:
            if "children" in node and isinstance(node["children"], dict):
                children_list = [_dict_to_list(v) for v in sorted(node["children"].values(), key=lambda x: (x["type"] != "directory", x["name"]))]
                node["children"] = children_list
            return node

        return _dict_to_list(root)

    def project_graph(
        self,
        db: Session,
        repository_id: str,
        snapshot_id: Optional[str] = None,
        focus: Optional[str] = None,
        depth: int = 2,
        level: int = 2,
        artifact_types: Optional[List[str]] = None,
        relationship_types: Optional[List[str]] = None,
        languages: Optional[List[str]] = None,
        include_tests: bool = True,
        include_external_dependencies: bool = False,
        diff_snapshot_id: Optional[str] = None,
        impact_artifact_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Projects Digital Twin artifacts and relationships into an interactive node-edge graph.
        Enforces hierarchical progressive disclosure, ego-network extraction, snapshot diffs,
        and forward change impact propagation.
        """
        repo = db.query(Repository).filter_by(id=repository_id).first()
        if not repo:
            raise ValueError(f"Repository with ID '{repository_id}' does not exist.")

        target_snap_id = snapshot_id or self._get_latest_snapshot_id(db, repository_id)
        if not target_snap_id:
            return {
                "repository_id": repo.id,
                "repository_name": repo.name,
                "snapshot_id": None,
                "nodes": [],
                "edges": [],
                "summary": {"total_nodes": 0, "total_edges": 0},
            }

        snap = db.query(RepositorySnapshot).filter_by(id=target_snap_id).first()

        # 1. Fetch raw artifacts & relationships for target snapshot
        artifacts = db.query(StructuralArtifact).filter_by(snapshot_id=target_snap_id).all()
        relationships = db.query(ArtifactRelationship).filter_by(snapshot_id=target_snap_id).all()

        # 2. Fetch architecture drifts for target snapshot
        drifts = (
            db.query(ArchitectureDriftEntity)
            .filter_by(snapshot_id=target_snap_id)
            .all()
        )
        drift_lookup_symbols: Dict[Tuple[str, str], ArchitectureDriftEntity] = {}
        drift_lookup_loc: Dict[str, ArchitectureDriftEntity] = {}
        for d in drifts:
            drift_lookup_symbols[(d.source, d.target)] = d
            if d.file_path and d.line_number:
                drift_lookup_loc[f"{d.file_path}:{d.line_number}"] = d
                if d.file_path.startswith("backend/"):
                    drift_lookup_loc[f"{d.file_path[8:]}:{d.line_number}"] = d

        # 3. Snapshot Diff calculation if diff_snapshot_id requested
        diff_data = None
        if diff_snapshot_id and diff_snapshot_id != target_snap_id:
            diff_data = self._compute_snapshot_diff(db, target_snap_id, diff_snapshot_id)

        # 4. Impact calculation if impact_artifact_id requested
        impact_data: Dict[str, Any] = {}
        if impact_artifact_id:
            impact_data = self._compute_impact_blast_radius(artifacts, relationships, impact_artifact_id)

        # 5. Build full NetworkX MultiDiGraph
        full_graph = nx.MultiDiGraph()
        artifact_by_id: Dict[str, StructuralArtifact] = {}
        artifact_by_qual: Dict[str, StructuralArtifact] = {}

        for art in artifacts:
            artifact_by_id[art.id] = art
            artifact_by_qual[art.qualified_name] = art
            full_graph.add_node(art.id, artifact=art)

        for rel in relationships:
            full_graph.add_edge(
                rel.source_artifact_id,
                rel.target_artifact_id,
                key=rel.id,
                relationship=rel,
            )

        # 6. Apply Focus & Depth Subgraph (Ego-network) if focus is specified
        active_node_ids: Set[str] = set(full_graph.nodes())
        if focus:
            focus_id = focus
            if focus not in full_graph and focus in artifact_by_qual:
                focus_id = artifact_by_qual[focus].id

            if focus_id in full_graph:
                ego_nodes = {focus_id}
                current_layer = {focus_id}
                for _ in range(max(1, depth)):
                    next_layer = set()
                    for n in current_layer:
                        next_layer.update(full_graph.successors(n))
                        next_layer.update(full_graph.predecessors(n))
                    ego_nodes.update(next_layer)
                    current_layer = next_layer
                active_node_ids = ego_nodes
            else:
                active_node_ids = set()

        # 7. Apply Level Filtering (Progressive Hierarchical Disclosure)
        # Level 1: Packages / Modules only
        # Level 2: Modules, Classes, Services, APIs, Tests, Databases, Tables (standard components)
        # Level 3: Level 2 + Functions & Methods
        # Level 4: All (including raw statements, external dependencies, variables)
        filtered_node_ids: Set[str] = set()
        for nid in active_node_ids:
            art = artifact_by_id.get(nid)
            if not art:
                continue

            atype = str(art.artifact_type).upper()

            # External dependencies toggle
            if atype == "EXTERNAL_DEPENDENCY" and not include_external_dependencies:
                continue

            # Tests toggle
            if ("TEST" in atype or (art.location and "test" in art.location.lower())) and not include_tests:
                continue

            # Type filter
            if artifact_types and atype not in [t.upper() for t in artifact_types]:
                continue

            # Language filter
            if languages and art.language and art.language.lower() not in [l.lower() for l in languages]:
                continue

            if level == 1:
                if atype in ("PACKAGE", "MODULE", "DIRECTORY", "SERVICE", "DATABASE"):
                    filtered_node_ids.add(nid)
            elif level == 2:
                if atype in ("PACKAGE", "MODULE", "CLASS", "INTERFACE", "SERVICE", "API_ENDPOINT", "DATABASE_TABLE", "TEST_CASE", "TEST_SUITE"):
                    filtered_node_ids.add(nid)
            elif level == 3:
                if atype in ("PACKAGE", "MODULE", "CLASS", "INTERFACE", "SERVICE", "API_ENDPOINT", "DATABASE_TABLE", "TEST_CASE", "TEST_SUITE", "METHOD", "FUNCTION", "CONSTRUCTOR"):
                    filtered_node_ids.add(nid)
            else:  # Level 4: All
                filtered_node_ids.add(nid)

        # 8. Transform to JSON-ready Nodes
        rendered_nodes: List[Dict[str, Any]] = []
        node_id_set = set(filtered_node_ids)

        for nid in filtered_node_ids:
            art = artifact_by_id[nid]
            loc_parts = (art.location or "").split(":")
            file_path = loc_parts[0] if loc_parts else ""

            # Resolve logical layer from file_path
            layer = self._infer_layer_from_path(file_path)

            diff_status = "UNCHANGED"
            if diff_data:
                if nid in diff_data["added_node_ids"] or art.qualified_name in diff_data["added_qual_names"]:
                    diff_status = "ADDED"
                elif nid in diff_data["modified_node_ids"]:
                    diff_status = "MODIFIED"

            is_impacted = nid in impact_data.get("affected_node_ids", set())
            impact_info = impact_data.get("details", {}).get(nid, {})

            rendered_nodes.append({
                "id": art.id,
                "name": art.name,
                "qualified_name": art.qualified_name,
                "type": art.artifact_type,
                "label": art.name,
                "language": art.language,
                "file": file_path,
                "location": art.location,
                "line_start": art.line_start,
                "line_end": art.line_end,
                "confidence": art.confidence or 1.0,
                "level": self._classify_level(art.artifact_type),
                "logical_layer": layer,
                "in_degree": full_graph.in_degree(nid),
                "out_degree": full_graph.out_degree(nid),
                "diff_status": diff_status,
                "is_impacted": is_impacted,
                "impact_depth": impact_info.get("depth", 0),
                "impact_reasons": impact_info.get("reasons", []),
                "metadata": art.metadata_payload or {},
            })

        # Add removed nodes from diff if diff requested
        if diff_data:
            for r_node in diff_data.get("removed_nodes", []):
                rendered_nodes.append(r_node)
                node_id_set.add(r_node["id"])

        # 9. Transform to JSON-ready Edges
        rendered_edges: List[Dict[str, Any]] = []
        for u, v, k, data in full_graph.edges(keys=True, data=True):
            if u not in node_id_set or v not in node_id_set:
                continue

            rel: ArtifactRelationship = data["relationship"]
            rtype = str(rel.relationship_type).upper()

            if relationship_types and rtype not in [r.upper() for r in relationship_types]:
                continue

            src_art = artifact_by_id.get(u)
            tgt_art = artifact_by_id.get(v)
            src_qual = src_art.qualified_name if src_art else ""
            tgt_qual = tgt_art.qualified_name if tgt_art else ""

            # Check if this edge is an architectural drift violation
            drift_match = drift_lookup_symbols.get((src_qual, tgt_qual))
            if not drift_match and rel.source_location:
                loc_clean = rel.source_location.split("-")[0].strip()
                drift_match = drift_lookup_loc.get(loc_clean)
            if not drift_match:
                for (d_src, d_tgt), d_ent in drift_lookup_symbols.items():
                    if (d_src in src_qual or src_qual in d_src) and (d_tgt in tgt_qual or tgt_qual in d_tgt):
                        drift_match = d_ent
                        break

            is_drift = drift_match is not None
            drift_details = None
            if drift_match:
                drift_details = {
                    "drift_id": drift_match.id,
                    "category": drift_match.category,
                    "severity": drift_match.severity,
                    "expected_rule": drift_match.expected_rule,
                    "actual_evidence": drift_match.actual_evidence,
                    "confidence": drift_match.confidence,
                }

            diff_status = "UNCHANGED"
            if diff_data:
                if rel.id in diff_data["new_edge_ids"] or (src_qual, tgt_qual, rtype) in diff_data["new_edge_tuples"]:
                    diff_status = "NEW"

            ev_loc = (rel.source_location or "").split(":")
            ev_file = ev_loc[0] if ev_loc else ""
            ev_line = int(ev_loc[1]) if len(ev_loc) > 1 and ev_loc[1].isdigit() else (rel.metadata_payload.get("line") if rel.metadata_payload else 1)

            rendered_edges.append({
                "id": rel.id,
                "source": rel.source_artifact_id,
                "target": rel.target_artifact_id,
                "type": rel.relationship_type,
                "confidence": rel.confidence or 1.0,
                "detection_method": rel.detection_method,
                "source_location": rel.source_location,
                "evidence": {
                    "file": ev_file,
                    "line": ev_line,
                    "snippet": rel.metadata_payload.get("snippet", f"{rel.source_artifact_id} -> {rel.target_artifact_id}"),
                },
                "diff_status": diff_status,
                "is_drift": is_drift,
                "drift_details": drift_details,
            })

        # Add removed edges from diff if requested
        if diff_data:
            for r_edge in diff_data.get("removed_edges", []):
                rendered_edges.append(r_edge)

        # 10. Summary Metrics
        summary = {
            "total_nodes": len(rendered_nodes),
            "total_edges": len(rendered_edges),
            "snapshot_id": target_snap_id,
            "commit_hash": snap.commit_hash if snap else "unknown",
            "branch_name": snap.branch_name if snap else "unknown",
            "created_at": snap.created_at.isoformat() if snap and snap.created_at else None,
            "total_artifacts_in_snapshot": len(artifacts),
            "total_relationships_in_snapshot": len(relationships),
            "drift_violations_count": len([e for e in rendered_edges if e["is_drift"]]),
            "node_types": {},
            "relationship_types": {},
            "diff_summary": diff_data.get("summary") if diff_data else None,
            "impact_summary": impact_data.get("summary") if impact_data else None,
        }

        for n in rendered_nodes:
            summary["node_types"][n["type"]] = summary["node_types"].get(n["type"], 0) + 1
        for e in rendered_edges:
            summary["relationship_types"][e["type"]] = summary["relationship_types"].get(e["type"], 0) + 1

        return {
            "repository_id": repo.id,
            "repository_name": repo.name,
            "snapshot_id": target_snap_id,
            "commit_hash": snap.commit_hash if snap else "unknown",
            "branch_name": snap.branch_name if snap else "unknown",
            "nodes": rendered_nodes,
            "edges": rendered_edges,
            "summary": summary,
        }

    def get_process_graph(
        self,
        db: Session,
        repository_id: str,
        snapshot_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Projects process flows with explicit evidence classification
        (OBSERVED, STATICALLY_INFERRED, HEURISTIC, UNKNOWN).
        Never presents inferred relationships as runtime-observed facts.
        """
        target_snap_id = snapshot_id or self._get_latest_snapshot_id(db, repository_id)
        if not target_snap_id:
            return {"processes": [], "nodes": [], "edges": [], "summary": {}}

        # 1. Query persisted ProcessDefinition records
        proc_defs = (
            db.query(ProcessDefinition)
            .filter_by(repository_id=repository_id, snapshot_id=target_snap_id)
            .all()
        )

        nodes: List[Dict[str, Any]] = []
        edges: List[Dict[str, Any]] = []
        processes_list: List[Dict[str, Any]] = []

        if proc_defs:
            for p in proc_defs:
                processes_list.append({
                    "id": p.id,
                    "name": p.name,
                    "description": p.description,
                    "type": p.process_type,
                    "steps_count": len(p.steps),
                })
                for step in p.steps:
                    nodes.append({
                        "id": step.id,
                        "process_id": p.id,
                        "name": step.name,
                        "type": step.step_type,
                        "order": step.step_order,
                        "component_id": step.component_artifact_id,
                        "evidence_status": step.metadata_payload.get("evidence_status", "STATICALLY_INFERRED"),
                        "description": step.metadata_payload.get("description", ""),
                    })
                for trans in p.transitions:
                    edges.append({
                        "id": trans.id,
                        "process_id": p.id,
                        "source": trans.from_step_id,
                        "target": trans.to_step_id,
                        "condition": trans.transition_condition,
                        "evidence_status": trans.metadata_payload.get("evidence_status", "STATICALLY_INFERRED"),
                    })

        # 2. If no explicit ProcessDefinition rows in DB, statically infer end-to-end service/API chains
        if not nodes:
            inferred = self._synthesize_static_process_chains(db, target_snap_id)
            processes_list = inferred["processes"]
            nodes = inferred["nodes"]
            edges = inferred["edges"]

        return {
            "repository_id": repository_id,
            "snapshot_id": target_snap_id,
            "processes": processes_list,
            "nodes": nodes,
            "edges": edges,
            "summary": {
                "total_processes": len(processes_list),
                "total_steps": len(nodes),
                "total_transitions": len(edges),
            },
        }

    def _synthesize_static_process_chains(self, db: Session, snapshot_id: str) -> Dict[str, Any]:
        """
        Synthesizes process flows from static API endpoints, controllers, and service calls.
        Explicitly flags all synthesized steps and edges as STATICALLY_INFERRED.
        """
        artifacts = db.query(StructuralArtifact).filter_by(snapshot_id=snapshot_id).all()
        relationships = db.query(ArtifactRelationship).filter_by(snapshot_id=snapshot_id).all()

        call_edges = [r for r in relationships if r.relationship_type in ("CALLS", "IMPORTS", "DEPENDS_ON")]
        art_map = {a.id: a for a in artifacts}

        # Identify entry points (APIs or controllers)
        entry_points = [
            a for a in artifacts
            if a.artifact_type == "API_ENDPOINT" or ("route" in (a.location or "").lower() or "controller" in a.name.lower())
        ]

        if not entry_points:
            # Fallback to any class or module with outgoing calls
            call_srcs = {r.source_artifact_id for r in call_edges}
            entry_points = [art_map[cid] for cid in call_srcs if cid in art_map][:3]

        processes = []
        nodes = []
        edges = []

        graph = nx.DiGraph()
        for a in artifacts:
            graph.add_node(a.id)
        for r in call_edges:
            graph.add_edge(r.source_artifact_id, r.target_artifact_id, rel=r)

        for idx, ep in enumerate(entry_points[:5]):
            proc_id = f"proc_static_{idx+1}"
            proc_name = f"Process Flow: {ep.name}"
            processes.append({
                "id": proc_id,
                "name": proc_name,
                "description": f"Statically inferred request flow starting from {ep.qualified_name}",
                "type": "API_WORKFLOW",
                "steps_count": 0,
            })

            # Traverse call chain up to depth 4
            visited = set()
            queue = [(ep.id, 1)]
            step_order = 1
            node_ids_in_proc = set()

            while queue:
                curr_id, d = queue.pop(0)
                if curr_id in visited or d > 4:
                    continue
                visited.add(curr_id)

                curr_art = art_map.get(curr_id)
                if not curr_art:
                    continue

                step_id = f"{proc_id}_step_{curr_id}"
                node_ids_in_proc.add(step_id)
                nodes.append({
                    "id": step_id,
                    "process_id": proc_id,
                    "name": curr_art.name,
                    "component_name": curr_art.qualified_name or curr_art.name,
                    "location": curr_art.location or (curr_art.metadata_payload.get("file") if curr_art.metadata_payload else "source"),
                    "type": curr_art.artifact_type,
                    "order": step_order,
                    "component_id": curr_art.id,
                    "evidence_status": "STATICALLY_INFERRED",
                    "confidence": 0.85,
                    "description": f"Component: {curr_art.qualified_name} at {curr_art.location}",
                })
                step_order += 1

                if graph.has_node(curr_id):
                    for succ in graph.successors(curr_id):
                        succ_art = art_map.get(succ)
                        # Separate test artifacts from application workflows unless explicitly requested
                        if succ_art and succ_art.artifact_type in ("TEST_CASE", "TEST_SUITE") and ep.artifact_type not in ("TEST_CASE", "TEST_SUITE"):
                            continue
                        target_step_id = f"{proc_id}_step_{succ}"
                        edge_id = f"trans_{curr_id}_{succ}"
                        edges.append({
                            "id": edge_id,
                            "process_id": proc_id,
                            "source": step_id,
                            "target": target_step_id,
                            "relationship_type": graph[curr_id][succ].get("rel", {}).relationship_type if hasattr(graph[curr_id][succ].get("rel"), "relationship_type") else "CALLS",
                            "condition": "Statically inferred call chain",
                            "evidence_status": "STATICALLY_INFERRED",
                            "confidence": 0.85,
                        })
                        queue.append((succ, d + 1))

        return {
            "processes": processes,
            "nodes": nodes,
            "edges": edges,
        }

    def _compute_snapshot_diff(
        self,
        db: Session,
        snap_a_id: str,
        snap_b_id: str
    ) -> Dict[str, Any]:
        """Computes structural diff between Snapshot A (current) and Snapshot B (previous)."""
        arts_a = db.query(StructuralArtifact).filter_by(snapshot_id=snap_a_id).all()
        arts_b = db.query(StructuralArtifact).filter_by(snapshot_id=snap_b_id).all()

        rels_a = db.query(ArtifactRelationship).filter_by(snapshot_id=snap_a_id).all()
        rels_b = db.query(ArtifactRelationship).filter_by(snapshot_id=snap_b_id).all()

        quals_a = {a.qualified_name: a for a in arts_a}
        quals_b = {b.qualified_name: b for b in arts_b}

        added_quals = set(quals_a.keys()) - set(quals_b.keys())
        removed_quals = set(quals_b.keys()) - set(quals_a.keys())
        common_quals = set(quals_a.keys()) & set(quals_b.keys())

        modified_ids = set()
        for q in common_quals:
            a_obj = quals_a[q]
            b_obj = quals_b[q]
            if a_obj.line_start != b_obj.line_start or a_obj.line_end != b_obj.line_end or a_obj.signature != b_obj.signature:
                modified_ids.add(a_obj.id)

        added_node_ids = {quals_a[q].id for q in added_quals}

        # Removed nodes
        removed_nodes = []
        for q in removed_quals:
            old_art = quals_b[q]
            removed_nodes.append({
                "id": f"removed_{old_art.id}",
                "name": old_art.name,
                "qualified_name": old_art.qualified_name,
                "type": old_art.artifact_type,
                "label": f"[REMOVED] {old_art.name}",
                "language": old_art.language,
                "file": (old_art.location or "").split(":")[0],
                "location": old_art.location,
                "diff_status": "REMOVED",
                "is_impacted": False,
                "in_degree": 0,
                "out_degree": 0,
                "level": self._classify_level(old_art.artifact_type),
                "logical_layer": self._infer_layer_from_path((old_art.location or "").split(":")[0]),
            })

        # Edges diff
        edges_a_tuples = {(r.source_artifact_id, r.target_artifact_id, r.relationship_type): r for r in rels_a}
        edges_b_tuples = {(r.source_artifact_id, r.target_artifact_id, r.relationship_type): r for r in rels_b}

        new_edge_ids = {r.id for k, r in edges_a_tuples.items() if k not in edges_b_tuples}
        new_edge_tuples = set(edges_a_tuples.keys()) - set(edges_b_tuples.keys())

        removed_edges = []
        for k, r in edges_b_tuples.items():
            if k not in edges_a_tuples:
                removed_edges.append({
                    "id": f"removed_edge_{r.id}",
                    "source": f"removed_{r.source_artifact_id}" if r.source_artifact_id not in quals_a else r.source_artifact_id,
                    "target": f"removed_{r.target_artifact_id}" if r.target_artifact_id not in quals_a else r.target_artifact_id,
                    "type": r.relationship_type,
                    "diff_status": "REMOVED",
                    "is_drift": False,
                    "confidence": r.confidence,
                    "evidence": {"file": "", "line": 1, "snippet": "[REMOVED RELATIONSHIP]"},
                })

        return {
            "added_node_ids": added_node_ids,
            "added_qual_names": added_quals,
            "modified_node_ids": modified_ids,
            "removed_nodes": removed_nodes,
            "new_edge_ids": new_edge_ids,
            "new_edge_tuples": new_edge_tuples,
            "removed_edges": removed_edges,
            "summary": {
                "added_artifacts": len(added_quals),
                "removed_artifacts": len(removed_quals),
                "modified_artifacts": len(modified_ids),
                "new_relationships": len(new_edge_ids),
                "removed_relationships": len(removed_edges),
            },
        }

    def _compute_impact_blast_radius(
        self,
        artifacts: List[StructuralArtifact],
        relationships: List[ArtifactRelationship],
        root_artifact_id: str
    ) -> Dict[str, Any]:
        """
        Computes forward change impact blast radius.
        Follows reverse dependency edges (callers and importers) to identify
        all downstream components, APIs, tests, and processes affected by a change.
        """
        art_map = {a.id: a for a in artifacts}
        art_qual_map = {a.qualified_name: a for a in artifacts}

        # Resolve root ID
        root_id = root_artifact_id
        if root_id not in art_map and root_id in art_qual_map:
            root_id = art_qual_map[root_id].id

        if root_id not in art_map:
            return {"affected_node_ids": set(), "details": {}, "summary": {}}

        # Build reverse dependency graph (target -> source, because if B calls A, when A changes B is impacted!)
        rev_graph = nx.DiGraph()
        for r in relationships:
            # When target changes, source is affected!
            rev_graph.add_edge(r.target_artifact_id, r.source_artifact_id, rel_type=r.relationship_type)

        affected_node_ids: Set[str] = {root_id}
        details: Dict[str, Any] = {
            root_id: {
                "depth": 0,
                "reasons": ["Root Changed Artifact"],
            }
        }

        # BFS expansion
        queue = [(root_id, 1)]
        visited = {root_id}

        while queue:
            curr, d = queue.pop(0)
            if d > 4:
                continue

            for pred in rev_graph.successors(curr):
                affected_node_ids.add(pred)
                edge_data = rev_graph.get_edge_data(curr, pred)
                rel_type = edge_data.get("rel_type", "CALLS") if edge_data else "DEPENDS_ON"
                curr_name = art_map.get(curr).name if curr in art_map else "Component"

                reason = f"Depends on {curr_name} via {rel_type} (depth {d})"
                if pred not in details:
                    details[pred] = {"depth": d, "reasons": [reason]}
                else:
                    details[pred]["reasons"].append(reason)

                if pred not in visited:
                    visited.add(pred)
                    queue.append((pred, d + 1))

        # Categorize affected artifacts
        affected_apis = []
        affected_tests = []
        affected_components = []

        for nid in affected_node_ids:
            if nid == root_id:
                continue
            art = art_map.get(nid)
            if not art:
                continue

            atype = str(art.artifact_type).upper()
            if atype == "API_ENDPOINT" or "route" in (art.location or "").lower():
                affected_apis.append(art.qualified_name)
            elif "TEST" in atype or (art.location and "test" in art.location.lower()):
                affected_tests.append(art.qualified_name)
            else:
                affected_components.append(art.qualified_name)

        # Blast radius score (0-100)
        blast_score = min(100.0, round((len(affected_components) * 8.0) + (len(affected_apis) * 20.0) + (len(affected_tests) * 5.0), 1))
        risk_level = "CRITICAL" if blast_score >= 75 else ("HIGH" if blast_score >= 50 else ("MEDIUM" if blast_score >= 25 else "LOW"))

        return {
            "root_artifact_id": root_id,
            "root_name": art_map[root_id].name,
            "affected_node_ids": affected_node_ids,
            "details": details,
            "summary": {
                "root_artifact": art_map[root_id].qualified_name,
                "blast_radius_score": blast_score,
                "risk_level": risk_level,
                "total_affected": len(affected_node_ids),
                "affected_components_count": len(affected_components),
                "affected_apis": affected_apis,
                "affected_tests": affected_tests,
            },
        }

    def _get_latest_snapshot_id(self, db: Session, repository_id: str) -> Optional[str]:
        """Returns the most recent snapshot ID for a repository."""
        snap = (
            db.query(RepositorySnapshot)
            .filter_by(repository_id=repository_id)
            .order_by(RepositorySnapshot.created_at.desc())
            .first()
        )
        return snap.id if snap else None

    def _classify_level(self, artifact_type: str) -> int:
        atype = str(artifact_type).upper()
        if atype in ("PACKAGE", "DIRECTORY", "MODULE"):
            return 1
        elif atype in ("CLASS", "INTERFACE", "SERVICE", "DATABASE_TABLE", "TEST_SUITE"):
            return 2
        elif atype in ("METHOD", "FUNCTION", "CONSTRUCTOR", "API_ENDPOINT", "TEST_CASE"):
            return 3
        return 4

    def _infer_layer_from_path(self, path: str) -> str:
        p_lower = path.lower()
        if any(kw in p_lower for kw in ("api", "controller", "presentation", "routes", "web", "endpoint")):
            return "presentation"
        elif any(kw in p_lower for kw in ("service", "application", "usecase", "handler", "manager")):
            return "application"
        elif any(kw in p_lower for kw in ("domain", "model", "entity", "schema")):
            return "domain"
        elif any(kw in p_lower for kw in ("db", "database", "repository", "infrastructure", "client", "adapter")):
            return "infrastructure"
        elif "test" in p_lower:
            return "test"
        return "core"

    def build_graph(self, db: Session, snapshot_id: str) -> nx.MultiDiGraph:
        """
        Deterministically constructs a directed multi-graph from PostgreSQL artifacts and relationships.
        Never makes in-memory graph the only source of truth.
        """
        graph = nx.MultiDiGraph(snapshot_id=snapshot_id)

        artifacts = db.query(StructuralArtifact).filter_by(snapshot_id=snapshot_id).all()
        relationships = db.query(ArtifactRelationship).filter_by(snapshot_id=snapshot_id).all()

        # Add Nodes
        for art in artifacts:
            graph.add_node(
                art.id,
                artifact_type=art.artifact_type,
                language=art.language,
                name=art.name,
                qualified_name=art.qualified_name,
                location=art.location,
                confidence=art.confidence,
                analyzer_source=art.analyzer_source,
            )

        # Add Directed Edges
        for rel in relationships:
            graph.add_edge(
                rel.source_artifact_id,
                rel.target_artifact_id,
                key=rel.id,
                relationship_type=rel.relationship_type,
                confidence=rel.confidence,
                detection_method=rel.detection_method,
                source_location=rel.source_location,
            )

        return graph

    def get_subgraph_for_artifact(
        self,
        graph: nx.MultiDiGraph,
        artifact_id: str,
        depth: int = 2
    ) -> nx.MultiDiGraph:
        """Extracts ego-network neighborhood around an artifact."""
        if artifact_id not in graph:
            return nx.MultiDiGraph()
        nodes = {artifact_id}
        current_layer = {artifact_id}
        for _ in range(depth):
            next_layer = set()
            for n in current_layer:
                next_layer.update(graph.successors(n))
                next_layer.update(graph.predecessors(n))
            nodes.update(next_layer)
            current_layer = next_layer
        return graph.subgraph(nodes).copy()

    def project_to_networkx(self, db: Session, snapshot_id: str) -> nx.MultiDiGraph:
        """Alias for build_graph."""
        return self.build_graph(db, snapshot_id)

    def get_graph_summary(self, db: Session, snapshot_id: str) -> Dict[str, Any]:
        """Returns node and edge summary for snapshot."""
        g = self.build_graph(db, snapshot_id)
        return {
            "snapshot_id": snapshot_id,
            "nodes": g.number_of_nodes(),
            "edges": g.number_of_edges(),
        }


twin_graph_projection = TwinGraphProjection()
graph_projection_service = twin_graph_projection
