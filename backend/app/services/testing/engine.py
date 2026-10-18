"""
Phase 6 — Test Impact Intelligence Engine.
Deterministic, graph-traversal engine that analyzes software changes and computes:
- Directly affected tests
- Indirectly affected tests
- Unaffected tests
- Changed entities with unknown coverage

Produces fully explainable causal impact paths and relationship chains with zero AI hallucination.
"""

from typing import List, Dict, Any, Optional, Set, Tuple
from collections import deque
from sqlalchemy.orm import Session

from app.models.entities import StructuralArtifact, ArtifactRelationship
from app.services.impact.change_detector import ChangeDetector, change_detector
from app.services.impact.models import ChangeSet, ChangeItem, ChangeType
from app.services.testing.models import (
    TestImpactItem,
    UnknownCoverageItem,
    TestImpactClassification,
    TestEvidenceStatus,
    TestCoverageClaim,
    ChangedArtifactEvaluation,
    TestImpactSummary,
    TestImpactConfig,
    TestImpactResult,
)


class TestImpactEngine:
    """
    Deterministic engine mapping code changes to affected test suites and test cases.
    """

    def __init__(self, detector: Optional[ChangeDetector] = None):
        self.detector = detector or change_detector

    def compute_test_impact(
        self,
        db: Session,
        repository_id: str,
        base_snapshot_id: str,
        target_snapshot_id: str,
        config: Optional[TestImpactConfig] = None,
        change_set: Optional[ChangeSet] = None,
        target_artifacts: Optional[List[StructuralArtifact]] = None,
        base_artifacts: Optional[List[StructuralArtifact]] = None,
        target_rels: Optional[List[ArtifactRelationship]] = None,
        base_rels: Optional[List[ArtifactRelationship]] = None,
    ) -> TestImpactResult:
        import time
        import uuid

        start_time = time.time()
        config = config or TestImpactConfig()

        # 1. Detect Changes between snapshots (or use provided change_set)
        if change_set is None:
            change_set = self.detector.detect_changes(
                db=db,
                repository_id=repository_id,
                base_snapshot_id=base_snapshot_id,
                target_snapshot_id=target_snapshot_id,
            )

        # 2. Fetch all artifacts and relationships for target and base snapshots
        if target_artifacts is None:
            target_artifacts = (
                db.query(StructuralArtifact)
                .filter_by(snapshot_id=target_snapshot_id)
                .all()
            )
        if base_artifacts is None:
            base_artifacts = (
                db.query(StructuralArtifact)
                .filter_by(snapshot_id=base_snapshot_id)
                .all()
            )
        if target_rels is None:
            target_rels = (
                db.query(ArtifactRelationship)
                .filter_by(snapshot_id=target_snapshot_id)
                .all()
            )
        if base_rels is None:
            base_rels = (
                db.query(ArtifactRelationship)
                .filter_by(snapshot_id=base_snapshot_id)
                .all()
            )

        # Combined artifacts lookup
        art_by_id: Dict[str, StructuralArtifact] = {}
        art_by_qual: Dict[str, StructuralArtifact] = {}
        for a in base_artifacts:
            art_by_id[a.id] = a
            art_by_qual[a.qualified_name] = a
        for a in target_artifacts:
            art_by_id[a.id] = a
            art_by_qual[a.qualified_name] = a

        # 3. Identify all Test Artifacts in the target snapshot
        test_artifacts: Dict[str, StructuralArtifact] = {}
        for a in target_artifacts:
            is_test_type = a.artifact_type in ("TEST_CASE", "TEST_SUITE")
            is_test_loc = bool(a.location and ("/test" in a.location.lower() or a.location.lower().startswith("test")))
            is_test_name = a.name.startswith("test_") or a.name.endswith("Test") or a.name.endswith("Tests")
            if is_test_type or (is_test_loc and is_test_name):
                test_artifacts[a.id] = a

        # Also identify tests from base snapshot if deleted
        for a in base_artifacts:
            if a.artifact_type in ("TEST_CASE", "TEST_SUITE"):
                if a.id not in test_artifacts and a.qualified_name not in [t.qualified_name for t in test_artifacts.values()]:
                    test_artifacts[a.id] = a

        # 4. Build Dependency and Reverse-Call Graph
        adjacency: Dict[str, List[Tuple[str, str]]] = {}

        def add_edge(trigger_id: str, affected_id: str, rel_type: str):
            if not trigger_id or not affected_id or trigger_id == affected_id:
                return
            if trigger_id not in adjacency:
                adjacency[trigger_id] = []
            if (affected_id, rel_type) not in adjacency[trigger_id]:
                adjacency[trigger_id].append((affected_id, rel_type))

        # Placeholder resolution map for internal aliases and module stems
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

            p_map: Dict[str, str] = {}
            for a in artifacts:
                if a.artifact_type == "EXTERNAL_DEPENDENCY":
                    name = a.name or a.qualified_name
                    if a.qualified_name in concrete_by_qual:
                        p_map[a.id] = concrete_by_qual[a.qualified_name].id
                    elif name.startswith("@/"):
                        cand = "src." + name[2:].replace("/", ".")
                        if cand in concrete_by_qual:
                            p_map[a.id] = concrete_by_qual[cand].id
                            continue
                        alias_stem = name.split("/")[-1].split(".")[0]
                        if alias_stem in concrete_by_stem and len(concrete_by_stem[alias_stem]) == 1:
                            p_map[a.id] = concrete_by_stem[alias_stem][0].id
                            continue
                    elif name in concrete_by_name and len(concrete_by_name[name]) == 1:
                        p_map[a.id] = concrete_by_name[name][0].id
                    else:
                        stem = name.split("/")[-1].split(".")[0]
                        if stem in concrete_by_stem and len(concrete_by_stem[stem]) == 1:
                            p_map[a.id] = concrete_by_stem[stem][0].id
                        else:
                            suffix = name.split(".")[-1]
                            if suffix in concrete_by_name and len(concrete_by_name[suffix]) == 1:
                                p_map[a.id] = concrete_by_name[suffix][0].id
            return p_map

        ph_map = _build_placeholder_map(list(art_by_id.values()))

        all_rels = list(target_rels) + [r for r in base_rels if r not in target_rels]
        forward_adjacency: Dict[str, List[Tuple[str, str]]] = {}
        for r in all_rels:
            rtype = r.relationship_type.upper()
            src_mapped = ph_map.get(r.source_artifact_id, r.source_artifact_id)
            tgt_mapped = ph_map.get(r.target_artifact_id, r.target_artifact_id)
            if rtype in ("TESTS", "CALLS", "IMPORTS", "DEPENDS_ON", "EXTENDS", "IMPLEMENTS", "CONSUMES"):
                add_edge(tgt_mapped, src_mapped, rtype)
                if src_mapped not in forward_adjacency:
                    forward_adjacency[src_mapped] = []
                if (tgt_mapped, rtype) not in forward_adjacency[src_mapped]:
                    forward_adjacency[src_mapped].append((tgt_mapped, rtype))
            elif rtype in ("EXPOSES", "CONTAINS", "PART_OF"):
                add_edge(src_mapped, tgt_mapped, rtype)
                if tgt_mapped not in forward_adjacency:
                    forward_adjacency[tgt_mapped] = []
                if (src_mapped, rtype) not in forward_adjacency[tgt_mapped]:
                    forward_adjacency[tgt_mapped].append((src_mapped, rtype))

        # Build name / location to artifact mapping for placeholder resolution
        name_to_ids: Dict[str, List[str]] = {}
        for a in art_by_id.values():
            name_to_ids.setdefault(a.name, []).append(a.id)
            name_to_ids.setdefault(a.qualified_name, []).append(a.id)

        # 5. Resolve Changed Entities to Starting Graph Nodes
        changed_nodes: List[Tuple[str, ChangeItem]] = []
        for change in change_set.changes:
            node_id = change.artifact_id
            if not node_id:
                if change.qualified_name in art_by_qual:
                    node_id = art_by_qual[change.qualified_name].id
                elif change.symbol_name in name_to_ids and len(name_to_ids[change.symbol_name]) == 1:
                    node_id = name_to_ids[change.symbol_name][0]
                elif change.source_file:
                    matching = [a.id for a in target_artifacts if a.location and a.location.startswith(change.source_file)]
                    if matching:
                        for m_id in matching:
                            changed_nodes.append((m_id, change))
                        continue
            if node_id:
                changed_nodes.append((node_id, change))

        # 6. Deterministic Multi-Hop Traversal (Cycle-Safe BFS)
        affected_tests_map: Dict[str, TestImpactItem] = {}
        # Track tests per changed entity: entity_id -> {"direct": [(test_id, depth)], "indirect": [(test_id, depth)]}
        tests_by_changed_entity: Dict[str, Dict[str, List[Tuple[str, int]]]] = {}

        for start_node_id, change in changed_nodes:
            tests_by_changed_entity.setdefault(start_node_id, {"direct": [], "indirect": []})
            start_art = art_by_id.get(start_node_id)
            start_name = start_art.name if start_art else change.symbol_name
            start_qual = start_art.qualified_name if start_art else change.qualified_name

            # Check if the changed entity ITSELF is a test
            if start_node_id in test_artifacts:
                test_art = test_artifacts[start_node_id]
                tests_by_changed_entity[start_node_id]["direct"].append((test_art.id, 1))
                if test_art.id not in affected_tests_map:
                    affected_tests_map[test_art.id] = TestImpactItem(
                        test_id=test_art.id,
                        test_name=test_art.name,
                        qualified_name=test_art.qualified_name,
                        location=test_art.location or "unknown",
                        classification=TestImpactClassification.DIRECTLY_AFFECTED,
                        evidence_status=TestEvidenceStatus.OBSERVED,
                        coverage_claim=TestCoverageClaim.TEST_IS_AFFECTED,
                        reason=f"Test code itself was {change.change_type.value.lower()} in this change.",
                        impact_path=[test_art.qualified_name],
                        relationships=["MODIFIED"],
                        depth=1,
                        confidence=1.0,
                    )

            # BFS Queue: (current_node_id, path_names, rel_types, depth)
            queue = deque([(start_node_id, [start_qual], [], 1)])
            visited: Set[str] = {start_node_id}

            while queue:
                curr_id, path_names, path_rels, depth = queue.popleft()

                if depth > config.max_depth:
                    continue

                for neighbor_id, rel_type in adjacency.get(curr_id, []):
                    if neighbor_id in visited:
                        continue
                    visited.add(neighbor_id)

                    neighbor_art = art_by_id.get(neighbor_id)
                    neighbor_name = neighbor_art.qualified_name if neighbor_art else neighbor_id

                    new_path_names = path_names + [neighbor_name]
                    new_path_rels = path_rels + [rel_type]

                    # Is the neighbor a test?
                    if neighbor_id in test_artifacts:
                        test_art = test_artifacts[neighbor_id]
                        is_direct = (depth == 1)
                        if is_direct:
                            tests_by_changed_entity[start_node_id]["direct"].append((test_art.id, depth))
                        else:
                            tests_by_changed_entity[start_node_id]["indirect"].append((test_art.id, depth))

                        classification = (
                            TestImpactClassification.DIRECTLY_AFFECTED
                            if is_direct
                            else TestImpactClassification.INDIRECTLY_AFFECTED
                        )

                        evidence_status = (
                            TestEvidenceStatus.OBSERVED
                            if (rel_type == "TESTS" and depth == 1)
                            else TestEvidenceStatus.DERIVED
                        )

                        if is_direct:
                            reason = (
                                f"Directly tests or asserts on modified entity '{start_name}' "
                                f"via {rel_type} relationship."
                            )
                        else:
                            intermediate = new_path_names[-2]
                            reason = (
                                f"Potentially affected because this test covers '{intermediate}' "
                                f"which is reachable from changed '{start_name}' via {len(new_path_rels)} hops."
                            )

                        if test_art.id not in affected_tests_map or depth < affected_tests_map[test_art.id].depth:
                            affected_tests_map[test_art.id] = TestImpactItem(
                                test_id=test_art.id,
                                test_name=test_art.name,
                                qualified_name=test_art.qualified_name,
                                location=test_art.location or "unknown",
                                classification=classification,
                                evidence_status=evidence_status,
                                coverage_claim=TestCoverageClaim.TEST_IS_AFFECTED,
                                reason=reason,
                                impact_path=new_path_names,
                                relationships=new_path_rels,
                                depth=depth,
                                confidence=max(0.6, 1.0 - (depth - 1) * 0.1),
                            )

                    if depth < config.max_depth:
                        queue.append((neighbor_id, new_path_names, new_path_rels, depth + 1))

        # 7. Unaffected Tests (Mapped tests not in any change impact path)
        unaffected_tests: List[TestImpactItem] = []
        if config.include_unaffected:
            for tid, tart in test_artifacts.items():
                if tid not in affected_tests_map:
                    unaffected_tests.append(
                        TestImpactItem(
                            test_id=tart.id,
                            test_name=tart.name,
                            qualified_name=tart.qualified_name,
                            location=tart.location or "unknown",
                            classification=TestImpactClassification.UNAFFECTED,
                            evidence_status=TestEvidenceStatus.OBSERVED,
                            coverage_claim=TestCoverageClaim.TEST_EXISTS_AND_IS_UNAFFECTED,
                            reason="Test exists and its dependency closure does not intersect the change blast radius.",
                            impact_path=[tart.qualified_name],
                            relationships=[],
                            depth=0,
                            confidence=1.0,
                        )
                    )

        # 8. Semantic Classification of Changed Artifact Population
        changed_evaluations: List[ChangedArtifactEvaluation] = []
        unknown_coverage_items: List[UnknownCoverageItem] = []

        for node_id, change in changed_nodes:
            art = art_by_id.get(node_id)
            art_name = art.name if art else change.symbol_name
            art_qual = art.qualified_name if art else change.qualified_name
            art_type = art.artifact_type if art else change.artifact_type
            art_loc = (art.location if art else change.source_file) or "unknown"

            direct_tests = tests_by_changed_entity.get(node_id, {}).get("direct", [])
            indirect_tests = tests_by_changed_entity.get(node_id, {}).get("indirect", [])
            downstream = adjacency.get(node_id, [])

            if direct_tests:
                # Direct test evidence established
                eval_item = ChangedArtifactEvaluation(
                    artifact_id=node_id,
                    name=art_name,
                    qualified_name=art_qual,
                    artifact_type=art_type,
                    location=art_loc,
                    change_type=change.change_type.value,
                    coverage_claim=TestCoverageClaim.TEST_IS_AFFECTED,
                    claim_rationale=f"Direct test evidence established: exercised by {len(direct_tests)} test(s) at hop distance 1.",
                    evidence_category="DIRECT_TEST_EVIDENCE",
                    direct_test_count=len(direct_tests),
                    indirect_test_count=len(indirect_tests),
                    associated_tests=[test_artifacts[t[0]].qualified_name for t in direct_tests if t[0] in test_artifacts],
                    traversal_depth_reached=1,
                    downstream_entities_count=len(downstream),
                )
                changed_evaluations.append(eval_item)
            elif indirect_tests:
                # Indirect test evidence established
                min_depth = min(t[1] for t in indirect_tests)
                eval_item = ChangedArtifactEvaluation(
                    artifact_id=node_id,
                    name=art_name,
                    qualified_name=art_qual,
                    artifact_type=art_type,
                    location=art_loc,
                    change_type=change.change_type.value,
                    coverage_claim=TestCoverageClaim.TEST_IS_AFFECTED,
                    claim_rationale=f"Indirect test evidence established: reachable by {len(indirect_tests)} test(s) at hop distance {min_depth}.",
                    evidence_category="INDIRECT_TEST_EVIDENCE",
                    direct_test_count=0,
                    indirect_test_count=len(indirect_tests),
                    associated_tests=[test_artifacts[t[0]].qualified_name for t in indirect_tests if t[0] in test_artifacts],
                    traversal_depth_reached=min_depth,
                    downstream_entities_count=len(downstream),
                )
                changed_evaluations.append(eval_item)
            else:
                # No test paths found -> Semantically evaluate specific unmapped claim
                forward_deps = forward_adjacency.get(node_id, [])
                downstream_count = len(forward_deps) if forward_deps else len(downstream)

                claim, reason_code, evidence_cat, explanation, evidence_list = self._determine_unknown_reason(
                    art=art,
                    change=change,
                    test_artifacts=test_artifacts,
                    target_artifacts=target_artifacts,
                    adjacency=adjacency,
                    forward_adjacency=forward_adjacency,
                )
                eval_item = ChangedArtifactEvaluation(
                    artifact_id=node_id,
                    name=art_name,
                    qualified_name=art_qual,
                    artifact_type=art_type,
                    location=art_loc,
                    change_type=change.change_type.value,
                    coverage_claim=claim,
                    claim_rationale=explanation,
                    evidence_category=evidence_cat,
                    direct_test_count=0,
                    indirect_test_count=0,
                    associated_tests=[],
                    traversal_depth_reached=config.max_depth,
                    downstream_entities_count=downstream_count,
                    cannot_be_unaffected_proof="Absence of a test path means coverage is UNKNOWN, NOT that the changed code is safe or UNAFFECTED.",
                )
                changed_evaluations.append(eval_item)

                unknown_coverage_items.append(
                    UnknownCoverageItem(
                        artifact_id=node_id,
                        name=art_name,
                        qualified_name=art_qual,
                        artifact_type=art_type,
                        location=art_loc,
                        change_type=change.change_type.value,
                        classification=TestImpactClassification.UNKNOWN_COVERAGE,
                        coverage_claim=claim,
                        reason_code=reason_code,
                        explanation=explanation,
                        reason="No direct or indirect test relationships detected for this changed entity.",
                        evidence=evidence_list,
                        cannot_be_unaffected_proof="Absence of a test path means coverage is UNKNOWN, NOT that the changed code is safe or UNAFFECTED.",
                    )
                )

        # 9. Semantic Invariant & Evidence Hierarchy Assertions
        # Invariant A: A changed source artifact can NEVER be classified as UNAFFECTED.
        for ev in changed_evaluations:
            if ev.coverage_claim == TestCoverageClaim.TEST_EXISTS_AND_IS_UNAFFECTED:
                raise AssertionError(
                    f"Semantic Invariant Violation: Changed artifact '{ev.qualified_name}' was assigned claim "
                    f"TEST_EXISTS_AND_IS_UNAFFECTED! Changed production artifacts can never be UNAFFECTED."
                )
            if ev.direct_test_count == 0 and ev.indirect_test_count == 0:
                if ev.coverage_claim in (TestCoverageClaim.TEST_EXISTS_AND_IS_UNAFFECTED, TestCoverageClaim.TEST_IS_AFFECTED):
                    raise AssertionError(
                        f"Semantic Invariant Violation: Changed artifact '{ev.qualified_name}' with 0 test paths "
                        f"was incorrectly assigned claim {ev.coverage_claim}!"
                    )

        # Invariant B: Strict evidence hierarchy enforcement:
        # Claim NO_AUTOMATED_TEST_EXISTS is ONLY permitted if total_tests_mapped == 0.
        if len(test_artifacts) > 0:
            for ev in changed_evaluations:
                if ev.coverage_claim == TestCoverageClaim.NO_AUTOMATED_TEST_EXISTS:
                    raise AssertionError(
                        f"Evidence hierarchy violation: Claim NO_AUTOMATED_TEST_EXISTS made for '{ev.qualified_name}', "
                        f"but repository contains {len(test_artifacts)} mapped tests!"
                    )

        # Invariant C: Only verified test artifacts may be in unaffected_tests
        for t in unaffected_tests:
            if t.test_id not in test_artifacts:
                raise AssertionError(
                    f"Semantic Invariant Violation: Entity '{t.test_name}' in unaffected_tests is not a recognized test artifact!"
                )
            if t.coverage_claim != TestCoverageClaim.TEST_EXISTS_AND_IS_UNAFFECTED:
                raise AssertionError(
                    f"Semantic Invariant Violation: Unaffected test '{t.test_name}' has invalid claim {t.coverage_claim}!"
                )

        # Sort affected tests: Directly affected first, then by depth ascending, then test_name
        affected_list = list(affected_tests_map.values())
        affected_list.sort(key=lambda t: (0 if t.classification == TestImpactClassification.DIRECTLY_AFFECTED else 1, t.depth, t.test_name))
        unaffected_tests.sort(key=lambda t: t.test_name)
        unknown_coverage_items.sort(key=lambda u: u.name)
        changed_evaluations.sort(key=lambda e: e.name)

        directly_count = sum(1 for t in affected_list if t.classification == TestImpactClassification.DIRECTLY_AFFECTED)
        indirectly_count = sum(1 for t in affected_list if t.classification == TestImpactClassification.INDIRECTLY_AFFECTED)

        summary = TestImpactSummary(
            total_tests_mapped=len(test_artifacts),
            potentially_affected_count=len(affected_list),
            directly_affected_count=directly_count,
            indirectly_affected_count=indirectly_count,
            unaffected_count=len(unaffected_tests),
            unknown_coverage_count=len(unknown_coverage_items),
        )

        exec_time = round((time.time() - start_time) * 1000, 2)

        return TestImpactResult(
            analysis_id=str(uuid.uuid4()),
            repository_id=repository_id,
            base_snapshot_id=base_snapshot_id,
            target_snapshot_id=target_snapshot_id,
            status="completed",
            summary=summary,
            affected_tests=affected_list,
            unaffected_tests=unaffected_tests,
            unknown_coverage=unknown_coverage_items,
            changed_artifact_evaluations=changed_evaluations,
            execution_time_ms=exec_time,
        )

    def _determine_unknown_reason(
        self,
        art: Optional[StructuralArtifact],
        change: ChangeItem,
        test_artifacts: Dict[str, StructuralArtifact],
        target_artifacts: List[StructuralArtifact],
        adjacency: Dict[str, List[Tuple[str, str]]],
        forward_adjacency: Optional[Dict[str, List[Tuple[str, str]]]] = None,
    ) -> Tuple[TestCoverageClaim, str, str, str, List[Dict[str, Any]]]:
        """
        Determines the formal TestCoverageClaim, reason code, evidence category,
        explanation, and evidence dicts for an unmapped changed entity.
        """
        evidence: List[Dict[str, Any]] = []

        # Claim 2: NO AUTOMATED TEST EXISTS (strictly when repository has 0 tests)
        if len(test_artifacts) == 0:
            return (
                TestCoverageClaim.NO_AUTOMATED_TEST_EXISTS,
                "NO_TESTS_IN_REPOSITORY",
                "NO_AUTOMATED_TESTS_IN_REPO",
                "No automated test suites or test cases exist anywhere in this repository.",
                evidence,
            )

        loc = (art.location if art else change.source_file) or ""
        lower_loc = loc.lower()

        # Check for config, generated or build files
        if any(lower_loc.endswith(ext) for ext in [".json", ".yaml", ".yml", ".toml", ".md", ".txt", ".lock", ".env", "dockerfile"]):
            evidence.append({"file": loc, "type": "configuration_or_doc"})
            return (
                TestCoverageClaim.NO_TEST_RELATIONSHIP_FOUND,
                "CONFIG_OR_NON_CODE_FILE",
                "CONFIG_OR_NON_CODE_FILE",
                f"Changed entity is a configuration, deployment, or documentation file ({loc}).",
                evidence,
            )
        if any(gen in lower_loc for gen in ["generated", "migration", "alembic", "dist", "build", "vendor"]):
            evidence.append({"file": loc, "type": "generated_or_migration"})
            return (
                TestCoverageClaim.NO_TEST_RELATIONSHIP_FOUND,
                "GENERATED_OR_MIGRATION_CODE",
                "GENERATED_OR_MIGRATION_CODE",
                f"Artifact is located in generated or database migration path ({loc}).",
                evidence,
            )

        # Claim 3: TEST EXISTS BUT COVERAGE IS UNKNOWN
        # Check if tests exist in proximity (e.g. sibling directory, same folder, stem match)
        src_dir = "/".join(loc.split("/")[:-1]) if "/" in loc else ""
        file_stem = (art.name if art else change.symbol_name).split(".")[0]
        sibling_tests = [
            t for t in test_artifacts.values()
            if (t.location and src_dir and src_dir in t.location) or (file_stem and file_stem in t.name)
        ]
        if sibling_tests:
            evidence.append({
                "sibling_test_count": len(sibling_tests),
                "sample_test": sibling_tests[0].qualified_name,
                "location": sibling_tests[0].location,
            })
            return (
                TestCoverageClaim.TEST_EXISTS_BUT_COVERAGE_IS_UNKNOWN,
                "FRAMEWORK_CONVENTION_UNCERTAINTY",
                "FRAMEWORK_CONVENTION_UNCERTAINTY",
                f"Automated test(s) exist in proximity ({sibling_tests[0].location}), but static AST analysis cannot prove an execution coverage path.",
                evidence,
            )

        # Check if any forward dependencies or downstream nodes exist from this changed node
        entity_id = art.id if art else change.artifact_id
        forward_deps = (forward_adjacency or {}).get(entity_id, [])
        downstream = adjacency.get(entity_id, [])
        active_deps = forward_deps if forward_deps else downstream
        if active_deps:
            evidence.append({
                "downstream_entities_count": len(active_deps),
                "sample_downstream": active_deps[0][0],
                "relationship": active_deps[0][1],
            })
            return (
                TestCoverageClaim.NO_TEST_RELATIONSHIP_FOUND,
                "UNRESOLVED_DEPENDENCY",
                "UNRESOLVED_DEPENDENCY",
                f"Artifact propagates to {len(active_deps)} downstream dependency(s), but dependency chain terminates without resolving to an executable test suite.",
                evidence,
            )

        # Claim 1: NO TEST RELATIONSHIP FOUND
        return (
            TestCoverageClaim.NO_TEST_RELATIONSHIP_FOUND,
            "NO_TEST_RELATIONSHIP",
            "NO_DISCOVERED_TEST_RELATIONSHIP",
            "Graph traversal explored all AST paths to depth limit; no static TESTS, CALLS, or IMPORTS relationship connects any mapped test suite to this artifact.",
            evidence,
        )


test_impact_engine = TestImpactEngine()
