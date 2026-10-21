"""
Phase 4 — Impact Propagator.
Executes deterministic, bounded graph traversal across typed Digital Twin relationships.
Enforces cycle protection, max_depth boundaries, and historical relationship traversal
for deleted artifacts.
"""

from typing import List, Dict, Any, Optional, Set, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.models.entities import StructuralArtifact, ArtifactRelationship
from app.services.impact.models import (
    ChangeSet,
    ChangeItem,
    ChangeType,
    ImpactFinding,
    ImpactConfig,
    PropagationDirection,
    ImpactClassification,
)
from app.services.impact.rules import RelationshipRuleRegistry, relationship_rule_registry


class ImpactPropagator:
    """
    Deterministic traversal engine propagating change impact along typed Digital Twin edges.
    """

    def __init__(self, rule_registry: Optional[RelationshipRuleRegistry] = None):
        self.rule_registry = rule_registry or relationship_rule_registry

    def propagate_impact(
        self,
        db: Session,
        change_set: ChangeSet,
        config: ImpactConfig,
        target_artifacts: Optional[List[StructuralArtifact]] = None,
        target_rels: Optional[List[ArtifactRelationship]] = None,
        base_artifacts: Optional[List[StructuralArtifact]] = None,
        base_rels: Optional[List[ArtifactRelationship]] = None,
    ) -> List[ImpactFinding]:
        """
        Traverses relationships starting from all items in the ChangeSet up to config.max_depth.
        Returns a deterministically ordered list of ImpactFinding objects.
        """
        if not change_set.changes:
            return []

        # Load all relationships for baseline and target snapshots into memory for fast bounded traversal
        if base_rels is None:
            base_rels = (
                db.query(ArtifactRelationship)
                .filter_by(snapshot_id=change_set.base_snapshot_id)
                .all()
            )
        if target_rels is None:
            target_rels = (
                db.query(ArtifactRelationship)
                .filter_by(snapshot_id=change_set.target_snapshot_id)
                .all()
            )

        if base_artifacts is None:
            base_artifacts = (
                db.query(StructuralArtifact)
                .filter_by(snapshot_id=change_set.base_snapshot_id)
                .all()
            )
        if target_artifacts is None:
            target_artifacts = (
                db.query(StructuralArtifact)
                .filter_by(snapshot_id=change_set.target_snapshot_id)
                .all()
            )

        # Artifact lookups
        art_map_target: Dict[str, StructuralArtifact] = {str(a.id): a for a in target_artifacts}
        art_qual_map_target: Dict[str, StructuralArtifact] = {str(a.qualified_name): a for a in target_artifacts}

        art_map_base: Dict[str, StructuralArtifact] = {str(a.id): a for a in base_artifacts}
        art_qual_map_base: Dict[str, StructuralArtifact] = {str(a.qualified_name): a for a in base_artifacts}

        # Build symbol placeholder resolution maps
        def _build_placeholder_map(artifacts: List[StructuralArtifact]) -> Dict[str, str]:
            concrete_by_name: Dict[str, List[StructuralArtifact]] = {}
            concrete_by_qual: Dict[str, StructuralArtifact] = {}
            concrete_by_stem: Dict[str, List[StructuralArtifact]] = {}
            for a in artifacts:
                if a.artifact_type != "EXTERNAL_DEPENDENCY":
                    concrete_by_qual[a.qualified_name] = a
                    concrete_by_name.setdefault(a.name, []).append(a)
                    stem = a.name.split(".")[0]
                    concrete_by_stem.setdefault(stem, []).append(a)

            ph_map: Dict[str, str] = {}
            for a in artifacts:
                if a.artifact_type == "EXTERNAL_DEPENDENCY":
                    name = a.name or a.qualified_name
                    # 1. Exact qualified name
                    if a.qualified_name in concrete_by_qual:
                        ph_map[a.id] = concrete_by_qual[a.qualified_name].id
                    # 2. Vite / TS alias path: @/services/dockerService -> src.services.dockerService
                    elif name.startswith("@/"):
                        cand = "src." + name[2:].replace("/", ".")
                        if cand in concrete_by_qual:
                            ph_map[a.id] = concrete_by_qual[cand].id
                            continue
                        # Try matching file stem from alias path
                        alias_stem = name.split("/")[-1].split(".")[0]
                        if alias_stem in concrete_by_stem and len(concrete_by_stem[alias_stem]) == 1:
                            ph_map[a.id] = concrete_by_stem[alias_stem][0].id
                            continue
                    # 3. Exact artifact name match
                    elif name in concrete_by_name and len(concrete_by_name[name]) == 1:
                        ph_map[a.id] = concrete_by_name[name][0].id
                    # 4. Relative import path stem or filename stem
                    else:
                        stem = name.split("/")[-1].split(".")[0]
                        if stem in concrete_by_stem and len(concrete_by_stem[stem]) == 1:
                            ph_map[a.id] = concrete_by_stem[stem][0].id
                        else:
                            suffix = name.split(".")[-1]
                            if suffix in concrete_by_name and len(concrete_by_name[suffix]) == 1:
                                ph_map[a.id] = concrete_by_name[suffix][0].id
            return ph_map

        target_ph_map = _build_placeholder_map(target_artifacts)
        base_ph_map = _build_placeholder_map(base_artifacts)

        # Build adjacency maps:
        # For each node, what dependent edges does it trigger?
        # If rule.direction == REVERSE: when target changes, source is affected!
        # If rule.direction == FORWARD: when source changes, target is affected!

        # Target snapshot adjacency
        target_adj: Dict[str, List[Tuple[str, str, float, str, str]]] = {}
        for r in target_rels:
            rule = self.rule_registry.get_rule(r.relationship_type)
            if not rule:
                continue

            if rule.direction == PropagationDirection.REVERSE:
                # Triggered when target changes -> impacts source
                trigger_id = target_ph_map.get(r.target_artifact_id, r.target_artifact_id)
                affected_id = target_ph_map.get(r.source_artifact_id, r.source_artifact_id)
            else:
                # Triggered when source changes -> impacts target
                trigger_id = target_ph_map.get(r.source_artifact_id, r.source_artifact_id)
                affected_id = target_ph_map.get(r.target_artifact_id, r.target_artifact_id)

            if not trigger_id or not affected_id:
                continue

            if trigger_id not in target_adj:
                target_adj[trigger_id] = []
            target_adj[trigger_id].append((
                affected_id,
                r.relationship_type,
                r.confidence * rule.confidence_factor,
                r.source_location or r.id,
                r.detection_method,
            ))

        # Base snapshot adjacency (specifically used for REMOVED artifacts)
        base_adj: Dict[str, List[Tuple[str, str, float, str, str]]] = {}
        for r in base_rels:
            rule = self.rule_registry.get_rule(r.relationship_type)
            if not rule:
                continue

            if rule.direction == PropagationDirection.REVERSE:
                trigger_id = base_ph_map.get(r.target_artifact_id, r.target_artifact_id)
                affected_id = base_ph_map.get(r.source_artifact_id, r.source_artifact_id)
            else:
                trigger_id = base_ph_map.get(r.source_artifact_id, r.source_artifact_id)
                affected_id = base_ph_map.get(r.target_artifact_id, r.target_artifact_id)

            if not trigger_id or not affected_id:
                continue

            if trigger_id not in base_adj:
                base_adj[trigger_id] = []
            base_adj[trigger_id].append((
                affected_id,
                r.relationship_type,
                r.confidence * rule.confidence_factor,
                r.source_location or r.id,
                r.detection_method,
            ))

        findings_map: Dict[Tuple[str, str, str], ImpactFinding] = {}

        # Traversal queue:
        # (root_change_item, current_node_id, current_qual_name, depth, path_qual_names, path_node_ids, accumulated_conf, evidence_list)
        for change in change_set.changes:
            is_removed = change.change_type == ChangeType.REMOVED
            art_map: Dict[str, StructuralArtifact] = art_map_base if is_removed else art_map_target
            adj_map: Dict[str, List[Tuple[str, str, float, str, str]]] = base_adj if is_removed else target_adj

            root_art = None
            if change.artifact_id and change.artifact_id in art_map:
                root_art = art_map[change.artifact_id]
            elif change.qualified_name in (art_qual_map_base if is_removed else art_qual_map_target):
                root_art = (art_qual_map_base if is_removed else art_qual_map_target)[change.qualified_name]

            if not root_art:
                continue

            root_id = root_art.id
            root_qual = root_art.qualified_name

            # Bounded BFS/DFS with cycle detection
            # State per root: min_depth_seen to avoid redundant long traversals
            min_depth_seen: Dict[str, int] = {root_id: 0}

            # Queue entry: (current_id, current_qual, depth, path_quals, path_ids, conf, evidence_chain)
            queue: List[Tuple[str, str, int, List[str], List[str], float, List[str]]] = [(
                str(root_id),
                str(root_qual),
                1,
                [str(root_qual)],
                [str(root_id)],
                1.0,
                [f"{change.change_type.value}: {root_qual}"],
            )]

            while queue:
                curr_id, curr_qual, depth, path_quals, path_ids, conf, ev_chain = queue.pop(0)

                if depth > config.max_depth:
                    continue

                # Query successors deterministically
                successors = adj_map.get(curr_id, [])
                # Deterministic sorting: sort by affected_id, relationship_type
                sorted_succs = sorted(successors, key=lambda s: (s[0], s[1]))

                for affected_id, rel_type, edge_conf, loc, det_method in sorted_succs:
                    # 1. Cycle Protection: do not revisit any node already in current branch path
                    if affected_id in path_ids:
                        continue

                    # 2. Check depth pruning: if we have reached affected_id earlier at shallower or equal depth from same root
                    if affected_id in min_depth_seen and min_depth_seen[affected_id] <= depth:
                        continue
                    min_depth_seen[affected_id] = depth

                    affected_art = art_map.get(affected_id) or art_map_target.get(affected_id) or art_map_base.get(affected_id)
                    affected_qual = affected_art.qualified_name if affected_art else affected_id
                    affected_type = affected_art.artifact_type if affected_art else "COMPONENT"

                    # Filter optional entity categories if configured
                    if not config.include_tests and ("TEST" in affected_type or "test" in (affected_art.location or "").lower() if affected_art else False):
                        continue
                    if not config.include_apis and (affected_type == "API_ENDPOINT" or "route" in (affected_art.location or "").lower() if affected_art else False):
                        continue

                    next_path_quals = path_quals + [affected_qual]
                    next_path_ids = path_ids + [affected_id]
                    next_conf = round(conf * edge_conf, 4)
                    step_evidence = f"{curr_qual} --[{rel_type}]--> {affected_qual} (at {loc})"
                    next_ev_chain = ev_chain + [step_evidence]

                    # Record Finding
                    key = (root_qual, affected_qual, rel_type)
                    if key not in findings_map or findings_map[key].impact_level > depth:
                        canonical_rule = self.rule_registry.get_canonical_rule(rel_type)
                        rule_id = canonical_rule.rule_id if canonical_rule else f"RULE_{rel_type}"
                        classification = ImpactClassification.DIRECT if depth == 1 else ImpactClassification.PROVEN_TRANSITIVE
                        ev_id = f"ev_prop_{depth}_{curr_id[:6]}_{affected_id[:6]}"

                        findings_map[key] = ImpactFinding(
                            source_node_id=root_id,
                            source_qual_name=root_qual,
                            impacted_node_id=affected_id,
                            target_qual_name=affected_qual,
                            target_type=affected_type,
                            impact_level=depth,
                            relationship_type=rel_type,
                            path=next_path_quals,
                            evidence=next_ev_chain,
                            confidence=next_conf,
                            detection_method=det_method,
                            rule_id=rule_id,
                            impact_classification=classification,
                            evidence_ids=[ev_id],
                            snapshot_id=change_set.target_snapshot_id,
                            provenance="DERIVED",
                            traversal_depth=depth,
                        )

                    # Enqueue next hop
                    if depth < config.max_depth:
                        queue.append((
                            affected_id,
                            affected_qual,
                            depth + 1,
                            next_path_quals,
                            next_path_ids,
                            next_conf,
                            next_ev_chain,
                        ))

        # Sort findings deterministically: by impact_level, root_qual_name, target_qual_name, relationship_type
        findings = list(findings_map.values())
        findings.sort(key=lambda f: (f.impact_level, f.source_qual_name, f.target_qual_name, f.relationship_type))
        return findings


impact_propagator = ImpactPropagator()
