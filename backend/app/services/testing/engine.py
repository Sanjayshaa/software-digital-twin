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
    ) -> TestImpactResult:
        import time
        import uuid

        start_time = time.time()
        config = config or TestImpactConfig()

        # 1. Detect Changes between snapshots
        change_set: ChangeSet = self.detector.detect_changes(
            db=db,
            repository_id=repository_id,
            base_snapshot_id=base_snapshot_id,
            target_snapshot_id=target_snapshot_id,
        )

        # 2. Fetch all artifacts and relationships for target and base snapshots
        target_artifacts = (
            db.query(StructuralArtifact)
            .filter_by(snapshot_id=target_snapshot_id)
            .all()
        )
        base_artifacts = (
            db.query(StructuralArtifact)
            .filter_by(snapshot_id=base_snapshot_id)
            .all()
        )
        target_rels = (
            db.query(ArtifactRelationship)
            .filter_by(snapshot_id=target_snapshot_id)
            .all()
        )
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
        # In Digital Twin, test artifacts have artifact_type in (TEST_CASE, TEST_SUITE)
        # or location containing 'test'
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
        # We want to know: when component X changes, what other components Y and tests T are affected?
        # Standard propagation direction:
        # - TESTS: (source: Test) -> (target: Component). If target changes, source is affected! (REVERSE)
        # - CALLS: (source: Caller) -> (target: Callee). If Callee changes, Caller is affected! (REVERSE)
        # - IMPORTS: (source: Importer) -> (target: Imported). If Imported changes, Importer is affected! (REVERSE)
        # - DEPENDS_ON: (source: Dependent) -> (target: Dep). If Dep changes, Dependent is affected! (REVERSE)
        # - EXTENDS: (source: Sub) -> (target: Super). If Super changes, Sub is affected! (REVERSE)
        # - IMPLEMENTS: (source: Impl) -> (target: Interface). If Interface changes, Impl is affected! (REVERSE)

        # Adjacency: changed_entity -> list of (affected_entity_id, relationship_type)
        adjacency: Dict[str, List[Tuple[str, str]]] = {}

        def add_edge(trigger_id: str, affected_id: str, rel_type: str):
            if not trigger_id or not affected_id or trigger_id == affected_id:
                return
            if trigger_id not in adjacency:
                adjacency[trigger_id] = []
            if (affected_id, rel_type) not in adjacency[trigger_id]:
                adjacency[trigger_id].append((affected_id, rel_type))

        all_rels = list(target_rels) + [r for r in base_rels if r not in target_rels]
        for r in all_rels:
            rtype = r.relationship_type.upper()
            if rtype in ("TESTS", "CALLS", "IMPORTS", "DEPENDS_ON", "EXTENDS", "IMPLEMENTS", "CONSUMES"):
                # When target changes, source is impacted
                add_edge(r.target_artifact_id, r.source_artifact_id, rtype)
            elif rtype in ("EXPOSES", "CONTAINS", "PART_OF"):
                # When source changes, target is impacted
                add_edge(r.source_artifact_id, r.target_artifact_id, rtype)

        # Build name / location to artifact mapping for placeholder resolution
        name_to_ids: Dict[str, List[str]] = {}
        for a in art_by_id.values():
            name_to_ids.setdefault(a.name, []).append(a.id)
            name_to_ids.setdefault(a.qualified_name, []).append(a.id)

        # 5. Resolve Changed Entities to Starting Graph Nodes
        # Changes can be symbol-level (methods, classes) or file-level
        changed_nodes: List[Tuple[str, ChangeItem]] = []
        for change in change_set.changes:
            node_id = change.artifact_id
            if not node_id:
                # Look up by qualified name or symbol name
                if change.qualified_name in art_by_qual:
                    node_id = art_by_qual[change.qualified_name].id
                elif change.symbol_name in name_to_ids and len(name_to_ids[change.symbol_name]) == 1:
                    node_id = name_to_ids[change.symbol_name][0]
                elif change.source_file:
                    # Match by file location prefix
                    matching = [a.id for a in target_artifacts if a.location and a.location.startswith(change.source_file)]
                    if matching:
                        for m_id in matching:
                            changed_nodes.append((m_id, change))
                        continue
            if node_id:
                changed_nodes.append((node_id, change))

        # 6. Deterministic Multi-Hop Traversal (Cycle-Safe BFS)
        # Find paths from each changed entity to all reachable tests
        affected_tests_map: Dict[str, TestImpactItem] = {}
        entities_with_coverage: Set[str] = set()

        for start_node_id, change in changed_nodes:
            start_art = art_by_id.get(start_node_id)
            start_name = start_art.name if start_art else change.symbol_name
            start_qual = start_art.qualified_name if start_art else change.qualified_name

            # Check if the changed entity ITSELF is a test
            if start_node_id in test_artifacts:
                test_art = test_artifacts[start_node_id]
                entities_with_coverage.add(start_node_id)
                if test_art.id not in affected_tests_map:
                    affected_tests_map[test_art.id] = TestImpactItem(
                        test_id=test_art.id,
                        test_name=test_art.name,
                        qualified_name=test_art.qualified_name,
                        location=test_art.location or "unknown",
                        classification=TestImpactClassification.DIRECTLY_AFFECTED,
                        evidence_status=TestEvidenceStatus.OBSERVED,
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
                        entities_with_coverage.add(start_node_id)

                        # Classification: DIRECTLY_AFFECTED if depth == 1, otherwise INDIRECTLY_AFFECTED
                        is_direct = (depth == 1)
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

                        # Record finding if not already present or if this is a shorter/more direct path
                        if test_art.id not in affected_tests_map or depth < affected_tests_map[test_art.id].depth:
                            affected_tests_map[test_art.id] = TestImpactItem(
                                test_id=test_art.id,
                                test_name=test_art.name,
                                qualified_name=test_art.qualified_name,
                                location=test_art.location or "unknown",
                                classification=classification,
                                evidence_status=evidence_status,
                                reason=reason,
                                impact_path=new_path_names,
                                relationships=new_path_rels,
                                depth=depth,
                                confidence=max(0.6, 1.0 - (depth - 1) * 0.1),
                            )

                    # Continue propagating downstream if depth allows
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
                            reason="Test is outside the transitive change blast radius.",
                            impact_path=[tart.qualified_name],
                            relationships=[],
                            depth=0,
                            confidence=1.0,
                        )
                    )

        # 8. Unknown Coverage Detection (Changed entities with no tests)
        unknown_coverage_items: List[UnknownCoverageItem] = []
        for node_id, change in changed_nodes:
            if node_id not in entities_with_coverage:
                art = art_by_id.get(node_id)
                unknown_coverage_items.append(
                    UnknownCoverageItem(
                        artifact_id=node_id,
                        name=art.name if art else change.symbol_name,
                        qualified_name=art.qualified_name if art else change.qualified_name,
                        artifact_type=art.artifact_type if art else change.artifact_type,
                        location=art.location if art else change.source_file,
                        change_type=change.change_type.value,
                        reason="No direct or indirect test relationships detected for this changed entity.",
                    )
                )

        # Sort affected tests: Directly affected first, then by depth ascending, then test_name
        affected_list = list(affected_tests_map.values())
        affected_list.sort(key=lambda t: (0 if t.classification == TestImpactClassification.DIRECTLY_AFFECTED else 1, t.depth, t.test_name))
        unaffected_tests.sort(key=lambda t: t.test_name)
        unknown_coverage_items.sort(key=lambda u: u.name)

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
            execution_time_ms=exec_time,
        )


test_impact_engine = TestImpactEngine()
