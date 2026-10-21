"""
Phase 9 — Technical Assessment Engine.
Performs deterministic, evidence-backed evaluation of repository architecture,
modularity, coupling, API surfaces, test gaps, change-impact exposure,
and synthesizes a prioritized advisory remediation roadmap.
"""

import os
import uuid
from typing import List, Dict, Any, Optional, Set, Tuple
from datetime import datetime
from collections import deque
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.entities import (
    Repository,
    RepositorySnapshot,
    StructuralArtifact,
    ArtifactRelationship,
    AnalysisRun,
    Incident,
    RuntimeEvent,
)
from app.services.discovery.scanner import RepositoryScanner, FileInventory
from app.services.discovery.engine import discovery_engine
from app.services.discovery.assessment_models import (
    DiscoveryStatus,
    FindingCategory,
    FindingSeverity,
    RoadmapPriority,
    DiscoveryCompleteness,
    AssessmentFinding,
    DimensionalScore,
    RoadmapRecommendation,
    TechnicalAssessmentResult,
    SUPPORTED_SOURCE_EXTENSIONS,
    SUPPORTED_EXTS,
    DOCUMENTATION_EXTENSIONS,
    SKIPPED_EXTENSIONS,
    CONFIGURATION_EXTENSIONS,
)
from app.services.simulation.orchestration import SensitiveDataSanitizer


class TechnicalAssessmentEngine:
    """
    Deterministic evaluation engine producing evidence-backed findings and remediation roadmaps.
    """

    def __init__(self):
        self.scanner = RepositoryScanner()
        self.sanitizer = SensitiveDataSanitizer()

    def assess_repository(
        self,
        db: Session,
        repository_id: str,
        snapshot_id: Optional[str] = None,
    ) -> TechnicalAssessmentResult:
        """
        Executes a comprehensive Technical Health Assessment on the specified repository revision.
        """
        repo = db.query(Repository).filter_by(id=repository_id).first()
        if not repo:
            raise ValueError(f"Repository with ID '{repository_id}' not found.")

        # Resolve Snapshot: exact UUID, commit SHA, or latest snapshot
        snap = None
        if snapshot_id:
            snap = db.query(RepositorySnapshot).filter(
                RepositorySnapshot.repository_id == repo.id,
                or_(
                    RepositorySnapshot.id == snapshot_id,
                    RepositorySnapshot.commit_hash == snapshot_id,
                    RepositorySnapshot.commit_hash.startswith(snapshot_id),
                ),
            ).first()

        if not snap:
            snap = (
                db.query(RepositorySnapshot)
                .filter_by(repository_id=repo.id)
                .order_by(RepositorySnapshot.created_at.desc())
                .first()
            )

        if not snap:
            raise ValueError(f"No snapshot found for repository '{repo.name}' ({repo.id}). Ingest repository first.")

        # Retrieve base structural artifacts and relationships
        artifacts = db.query(StructuralArtifact).filter_by(snapshot_id=snap.id).all()
        relationships = db.query(ArtifactRelationship).filter_by(snapshot_id=snap.id).all()

        # Discover repository file inventory on disk if clone exists
        inventory: Optional[FileInventory] = None
        if repo.local_path and os.path.exists(repo.local_path):
            try:
                inventory = self.scanner.scan(repo.local_path)
            except Exception:
                inventory = None

        # 1. Compute Discovery Completeness
        completeness = self._compute_completeness(repo, snap, artifacts, relationships, inventory)

        # 2. Evaluate 9 Dimensions & Extract Findings
        scores, findings = self._evaluate_dimensions(db, repo, snap, artifacts, relationships, inventory, completeness)

        # 3. Synthesize Prioritized Advisory Roadmap
        roadmap = self._synthesize_roadmap(findings, completeness)

        # 4. Generate Executive Summary & Markdown Report
        summary, markdown_report = self._generate_report(repo, snap, completeness, scores, findings, roadmap)

        assessment_id = f"assess_{uuid.uuid4().hex[:12]}"
        result = TechnicalAssessmentResult(
            assessment_id=assessment_id,
            repository_id=repo.id,
            repository_name=repo.name,
            snapshot_id=snap.id,
            commit_hash=snap.commit_hash or "HEAD",
            assessed_at=datetime.utcnow().isoformat(),
            completeness=completeness,
            dimensional_scores=scores,
            findings=findings,
            roadmap=roadmap,
            executive_summary=summary,
            report_markdown=markdown_report,
            markdown_content=markdown_report,
        )

        # 5. Persist Assessment in PostgreSQL as AnalysisRun
        self._persist_assessment(db, repo, snap, result)

        return result

    def _compute_completeness(
        self,
        repo: Repository,
        snap: RepositorySnapshot,
        artifacts: List[StructuralArtifact],
        relationships: List[ArtifactRelationship],
        inventory: Optional[FileInventory],
    ) -> DiscoveryCompleteness:
        """Determines factual completeness of structural twin extraction."""
        total_discovered = inventory.total_files if inventory else (snap.total_files or len(artifacts))
        
        analyzed_files: Set[str] = set()
        for a in artifacts:
            if a.location:
                f_path = a.location.split(":")[0]
                analyzed_files.add(f_path)

        supported_code_files = 0
        unsupported_code_files = 0
        unsupported_exts: Set[str] = set()
        skipped_files = 0
        doc_files = 0
        config_files = 0

        if inventory:
            manifest_names = {getattr(m, "file_name", "").lower() for m in inventory.manifest_files}
            for f in inventory.files:
                ext = (f.extension or "").lower()
                if ext and not ext.startswith("."):
                    ext = f".{ext}"
                if ext in SUPPORTED_SOURCE_EXTENSIONS:
                    supported_code_files += 1
                elif ext in SKIPPED_EXTENSIONS or f.is_binary:
                    skipped_files += 1
                elif ext in DOCUMENTATION_EXTENSIONS:
                    doc_files += 1
                    if ext:
                        unsupported_exts.add(ext)
                elif ext in CONFIGURATION_EXTENSIONS or f.file_name.lower() in manifest_names:
                    config_files += 1
                else:
                    unsupported_code_files += 1
                    if ext:
                        unsupported_exts.add(ext)

        symbols_count = len(artifacts)
        rels_count = len(relationships)
        tests_count = sum(1 for a in artifacts if a.artifact_type in ("TEST_CASE", "TEST_SUITE"))
        tests_linked = sum(1 for r in relationships if (r.relationship_type or "").upper() == "TESTS")

        files_analyzed_count = len(analyzed_files)
        # Total code files only includes supported code files and unsupported source code files, excluding documentation and skipped assets
        total_code_files = max(files_analyzed_count + unsupported_code_files, 1)
        cov_pct = round((files_analyzed_count / total_code_files) * 100.0, 1) if total_code_files > 0 else 0.0

        total_unsupported_or_noncode = unsupported_code_files + doc_files
        if symbols_count == 0 and files_analyzed_count == 0:
            if supported_code_files > 0:
                status = DiscoveryStatus.FAILED
                explanation = f"File scanning identified {supported_code_files} supported source code files, but AST structural extraction produced zero symbols."
            else:
                status = DiscoveryStatus.UNSUPPORTED
                explanation = "Repository contains only non-code files, documentation, or unsupported programming languages."
        elif files_analyzed_count == 0 and total_discovered > 0:
            status = DiscoveryStatus.FAILED
            explanation = "File scanning succeeded but AST structural extraction produced zero symbols."
        elif unsupported_code_files > 0 or cov_pct < 85.0:
            status = DiscoveryStatus.PARTIAL
            explanation = f"Partial discovery: {files_analyzed_count} files analyzed ({cov_pct}% code coverage). {unsupported_code_files} files in unsupported formats."
        else:
            status = DiscoveryStatus.COMPLETE
            explanation = f"Complete discovery: {files_analyzed_count} files analyzed, {symbols_count} symbols, {rels_count} relationships."

        return DiscoveryCompleteness(
            status=status,
            files_discovered=total_discovered,
            files_analyzed=files_analyzed_count,
            files_skipped=skipped_files,
            files_unsupported=total_unsupported_or_noncode,
            analysis_failures=0,
            symbols_extracted=symbols_count,
            relationships_extracted=rels_count,
            tests_discovered=tests_count,
            tests_linked=tests_linked,
            coverage_percentage=min(cov_pct, 100.0),
            unsupported_extensions=sorted(list(unsupported_exts))[:10],
            explanation=explanation,
        )

    def _evaluate_dimensions(
        self,
        db: Session,
        repo: Repository,
        snap: RepositorySnapshot,
        artifacts: List[StructuralArtifact],
        relationships: List[ArtifactRelationship],
        inventory: Optional[FileInventory],
        completeness: DiscoveryCompleteness,
    ) -> Tuple[List[DimensionalScore], List[AssessmentFinding]]:
        """Evaluates the 9 required architectural and health dimensions."""
        findings: List[AssessmentFinding] = []

        # Build in-memory graph index
        art_by_id = {a.id: a for a in artifacts}
        out_edges: Dict[str, List[Tuple[str, str]]] = {}
        in_edges: Dict[str, List[Tuple[str, str]]] = {}
        for r in relationships:
            rtype = (r.relationship_type or "CALLS").upper()
            out_edges.setdefault(r.source_artifact_id, []).append((r.target_artifact_id, rtype))
            in_edges.setdefault(r.target_artifact_id, []).append((r.source_artifact_id, rtype))

        # --- DIMENSION 1: Architecture & Modularity ---
        cycles: List[Tuple[str, str]] = []
        visited: Set[str] = set()
        for src_id, targets in out_edges.items():
            for tgt_id, _ in targets:
                # Check 2-node cycle A -> B -> A
                if tgt_id in out_edges and any(rev_tgt == src_id for rev_tgt, _ in out_edges[tgt_id]):
                    pair = tuple(sorted([src_id, tgt_id]))
                    if pair not in visited:
                        visited.add(pair)
                        cycles.append((src_id, tgt_id))

        if cycles:
            for idx, (node_a, node_b) in enumerate(cycles[:3], 1):
                name_a = art_by_id.get(node_a, StructuralArtifact(name=node_a)).name
                name_b = art_by_id.get(node_b, StructuralArtifact(name=node_b)).name
                findings.append(AssessmentFinding(
                    finding_id=f"FIND-ARCH-CIRCULAR-{idx:02d}",
                    category=FindingCategory.ARCHITECTURE,
                    severity=FindingSeverity.HIGH,
                    title=f"Circular Architectural Dependency between '{name_a}' and '{name_b}'",
                    description=f"Mutual direct dependencies detected between component '{name_a}' and '{name_b}'. Circular coupling obstructs modular testing and prevents clean layer decomposition.",
                    rationale="Circular dependencies introduce tight coupling, cascading runtime failures, and circular build dependencies.",
                    affected_entities=[name_a, name_b],
                    affected_files=[art_by_id[node_a].location.split(":")[0] if node_a in art_by_id and art_by_id[node_a].location else ""],
                    evidence_references=[{"source": name_a, "target": name_b, "relation": "MUTUAL_CALLS"}],
                    detection_method="graph_cycle_inspection",
                    confidence=1.0,
                    known_limitations="Evaluated among direct 2-node dependency cycles.",
                    recommended_action=f"Extract shared interface or introduce mediator service to decouple '{name_a}' and '{name_b}'.",
                ))

        arch_score = max(100.0 - (len(cycles) * 15.0), 30.0) if artifacts else 100.0
        dim_arch = DimensionalScore(
            dimension_name="Architecture & Modularity",
            score=arch_score,
            status="HEALTHY" if arch_score >= 80 else ("ATTENTION" if arch_score >= 50 else "AT_RISK"),
            summary=f"{len(cycles)} circular dependencies detected across {len(artifacts)} structural entities.",
            key_metrics={"circular_cycles_count": len(cycles), "total_entities": len(artifacts)},
        )

        # --- DIMENSION 2: Dependency & Coupling ---
        god_components = []
        for a_id, a in art_by_id.items():
            fan_out = len(out_edges.get(a_id, []))
            fan_in = len(in_edges.get(a_id, []))
            if fan_out >= 12 or (fan_in >= 15 and fan_out >= 8):
                god_components.append((a, fan_out, fan_in))

        for idx, (g_art, f_out, f_in) in enumerate(god_components[:4], 1):
            findings.append(AssessmentFinding(
                finding_id=f"FIND-COUP-HIGH-FANOUT-{idx:02d}",
                category=FindingCategory.COUPLING,
                severity=FindingSeverity.HIGH if f_out >= 18 else FindingSeverity.MEDIUM,
                title=f"High Coupling Hotspot in '{g_art.name}' (Fan-Out: {f_out}, Fan-In: {f_in})",
                description=f"Entity '{g_art.name}' has excessive fan-out dependencies ({f_out} outbound calls, {f_in} inbound callers). It functions as a central coupling nexus.",
                rationale="Changes to highly coupled components trigger widespread downstream blast radiuses.",
                affected_entities=[g_art.name],
                affected_files=[g_art.location.split(":")[0] if g_art.location else ""],
                evidence_references=[{"fan_out": f_out, "fan_in": f_in, "entity_type": g_art.artifact_type}],
                detection_method="graph_degree_inspection",
                confidence=1.0,
                known_limitations="Based on static relationship density.",
                recommended_action=f"Refactor '{g_art.name}' by segregating responsibilities into cohesive sub-services.",
            ))

        coupling_score = max(100.0 - (len(god_components) * 12.0), 40.0) if artifacts else 100.0
        dim_coupling = DimensionalScore(
            dimension_name="Dependency & Coupling",
            score=coupling_score,
            status="HEALTHY" if coupling_score >= 80 else ("ATTENTION" if coupling_score >= 50 else "AT_RISK"),
            summary=f"{len(god_components)} high-coupling hotspot components identified with fan-out >= 12.",
            key_metrics={"high_coupling_components_count": len(god_components)},
        )

        # --- DIMENSION 3: API & Interface Relationships ---
        endpoints = [a for a in artifacts if a.artifact_type in ("API_ENDPOINT", "ENDPOINT") or "/api/" in (a.location or "")]
        orphaned_apis = [ep for ep in endpoints if ep.id not in in_edges or len(in_edges[ep.id]) == 0]
        
        if orphaned_apis and len(endpoints) > 0:
            for idx, o_api in enumerate(orphaned_apis[:3], 1):
                findings.append(AssessmentFinding(
                    finding_id=f"FIND-API-ORPHANED-{idx:02d}",
                    category=FindingCategory.API_INTERFACE,
                    severity=FindingSeverity.LOW,
                    title=f"Unreferenced API Endpoint '{o_api.name}'",
                    description=f"Endpoint '{o_api.name}' has zero internal callers indexed in the digital twin graph.",
                    rationale="Unreferenced endpoints may be dead code or lack automated integration tests.",
                    affected_entities=[o_api.name],
                    affected_files=[o_api.location.split(":")[0] if o_api.location else ""],
                    evidence_references=[{"endpoint": o_api.name, "inbound_callers": 0}],
                    detection_method="graph_in_degree_audit",
                    confidence=0.85,
                    known_limitations="External consumers calling from outside the repository are not tracked.",
                    recommended_action="Verify if endpoint is called externally; if obsolete, deprecate or add integration tests.",
                ))

        api_score = 90.0 if not endpoints else max(100.0 - (len(orphaned_apis) * 5.0), 60.0)
        dim_api = DimensionalScore(
            dimension_name="API & Interface Exposure",
            score=api_score,
            status="HEALTHY" if api_score >= 80 else "ATTENTION",
            summary=f"{len(endpoints)} API endpoints discovered; {len(orphaned_apis)} have zero internal callers.",
            key_metrics={"total_endpoints": len(endpoints), "uncalled_endpoints": len(orphaned_apis)},
        )

        # --- DIMENSION 4: Test Inventory & Linkage Gaps ---
        tests_count = completeness.tests_discovered
        tests_linked = completeness.tests_linked
        tested_entities = {r.target_artifact_id for r in relationships if (r.relationship_type or "").upper() == "TESTS"}
        core_components = [a for a in artifacts if a.artifact_type in ("SERVICE", "CONTROLLER", "COMPONENT", "CLASS")]
        untested_core = [c for c in core_components if c.id not in tested_entities]

        if core_components and (tests_count == 0 or len(untested_core) > len(core_components) * 0.5):
            findings.append(AssessmentFinding(
                finding_id="FIND-TEST-GAP-001",
                category=FindingCategory.TEST_COVERAGE,
                severity=FindingSeverity.CRITICAL if tests_count == 0 else FindingSeverity.HIGH,
                title="Critical Automated Test Coverage Deficit",
                description=f"Repository contains {len(core_components)} core architecture components, but only {len(tested_entities)} have verified test linkages ({len(untested_core)} untested components).",
                rationale="Unverified components lack regression protection during pre-deployment change impact analysis.",
                affected_entities=[c.name for c in untested_core[:5]],
                affected_files=[c.location.split(":")[0] for c in untested_core[:5] if c.location],
                evidence_references=[{"untested_components_count": len(untested_core), "total_components": len(core_components)}],
                detection_method="twin_test_linkage_audit",
                confidence=1.0,
                known_limitations="Only deterministically linked unit and integration test fixtures are evaluated.",
                recommended_action="Prioritize unit test suite construction for untested services and controllers.",
            ))

        test_ratio = len(tested_entities) / max(len(core_components), 1)
        test_score = round(min(test_ratio * 100.0, 100.0), 1) if core_components else 100.0
        dim_tests = DimensionalScore(
            dimension_name="Testing Inventory & Coverage Gaps",
            score=test_score,
            status="HEALTHY" if test_score >= 75 else ("ATTENTION" if test_score >= 40 else "AT_RISK"),
            summary=f"{tests_count} tests discovered, {tests_linked} relationships mapped. {len(untested_core)} core components currently lack verified test coverage.",
            key_metrics={"tests_discovered": tests_count, "tests_linked": tests_linked, "untested_components": len(untested_core)},
        )

        # --- DIMENSION 5: Change Impact Exposure ---
        deep_blast_components = []
        for a in core_components[:30]:
            # Simple breadth-first blast radius calculation
            q = deque([(a.id, 0)])
            visited_blast = {a.id}
            max_depth = 0
            while q:
                curr_id, depth = q.popleft()
                max_depth = max(max_depth, depth)
                if depth >= 5:
                    continue
                for caller_id, _ in in_edges.get(curr_id, []):
                    if caller_id not in visited_blast:
                        visited_blast.add(caller_id)
                        q.append((caller_id, depth + 1))
            if len(visited_blast) >= 15 or max_depth >= 4:
                deep_blast_components.append((a, len(visited_blast), max_depth))

        for idx, (b_art, b_size, b_depth) in enumerate(deep_blast_components[:3], 1):
            findings.append(AssessmentFinding(
                finding_id=f"FIND-IMPACT-BLAST-{idx:02d}",
                category=FindingCategory.CHANGE_IMPACT,
                severity=FindingSeverity.HIGH if b_size >= 25 else FindingSeverity.MEDIUM,
                title=f"Widespread Blast-Radius Exposure in '{b_art.name}' ({b_size} Nodes, Depth {b_depth})",
                description=f"Modifications to '{b_art.name}' propagate up to {b_depth} tiers and directly/indirectly impact {b_size} downstream nodes.",
                rationale="High propagation depth exponentially increases the probability of regression bugs during deployments.",
                affected_entities=[b_art.name],
                affected_files=[b_art.location.split(":")[0] if b_art.location else ""],
                evidence_references=[{"propagation_depth": b_depth, "impact_radius_nodes": b_size}],
                detection_method="blast_radius_bfs_traversal",
                confidence=0.95,
                known_limitations="Evaluated over static AST and dependency edges.",
                recommended_action=f"Implement facade or anti-corruption layer to constrain '{b_art.name}' blast radius.",
            ))

        impact_score = max(100.0 - (len(deep_blast_components) * 10.0), 40.0) if artifacts else 100.0
        dim_impact = DimensionalScore(
            dimension_name="Change Impact Exposure",
            score=impact_score,
            status="HEALTHY" if impact_score >= 80 else ("ATTENTION" if impact_score >= 50 else "AT_RISK"),
            summary=f"{len(deep_blast_components)} components exhibit high blast-radius propagation depth (depth >= 4 or nodes >= 15).",
            key_metrics={"deep_blast_components_count": len(deep_blast_components)},
        )

        # --- DIMENSION 6: Configuration & Build Management ---
        conf_findings = []
        if inventory:
            manifest_count = len(inventory.manifest_files)
            if manifest_count > 4:
                conf_findings.append(("Multiple heterogeneous package manifests detected", "Consolidate build configurations."))
        
        conf_score = 90.0 if not conf_findings else 70.0
        dim_config = DimensionalScore(
            dimension_name="Configuration & Build Management",
            score=conf_score,
            status="HEALTHY" if conf_score >= 80 else "ATTENTION",
            summary="Package manifests and build configurations consistent with repository typology.",
            key_metrics={"manifests_scanned": len(inventory.manifest_files) if inventory else 0},
        )

        # --- DIMENSION 7: Maintenance Hotspots ---
        large_files = []
        if inventory:
            for f in inventory.files:
                size_kb = (f.size_bytes or 0) / 1024.0
                rel_path = getattr(f, "relative_path", f.file_name)
                ext = (f.extension or "").lower()
                if ext and not ext.startswith("."):
                    ext = f".{ext}"
                if size_kb >= 100.0 and ext in SUPPORTED_EXTS:
                    large_files.append((rel_path, round(size_kb, 1)))

        if large_files:
            for idx, (f_name, f_kb) in enumerate(large_files[:3], 1):
                findings.append(AssessmentFinding(
                    finding_id=f"FIND-MAINT-HOTSPOT-{idx:02d}",
                    category=FindingCategory.MAINTENANCE,
                    severity=FindingSeverity.MEDIUM,
                    title=f"Large Source Code File Hotspot '{f_name}' ({f_kb} KB)",
                    description=f"File '{f_name}' is unusually large ({f_kb} KB). Over-sized files frequently exhibit lower cohesion and higher defect rates.",
                    rationale="Monolithic files impede parallel team development and increase merge conflict frequencies.",
                    affected_entities=[f_name],
                    affected_files=[f_name],
                    evidence_references=[{"file_size_kb": f_kb}],
                    detection_method="file_system_size_inspection",
                    confidence=1.0,
                    known_limitations="Evaluated based on physical file byte size.",
                    recommended_action=f"Decompose '{f_name}' into cohesive single-responsibility modules.",
                ))

        maint_score = max(100.0 - (len(large_files) * 8.0), 50.0)
        dim_maint = DimensionalScore(
            dimension_name="Maintenance & Code Health Hotspots",
            score=maint_score,
            status="HEALTHY" if maint_score >= 80 else "ATTENTION",
            summary=f"{len(large_files)} large source code file hotspots identified exceeding 100 KB.",
            key_metrics={"large_files_count": len(large_files)},
        )

        # --- DIMENSION 8: Incident & Runtime Evidence ---
        incidents = db.query(Incident).filter_by(repository_id=repo.id).all() if repo.id else []
        runtime_events = db.query(RuntimeEvent).filter_by(repository_id=repo.id).all() if repo.id else []
        error_events = [e for e in runtime_events if (e.event_type or "").upper() in ("ERROR", "EXCEPTION", "CRASH")]

        if error_events:
            findings.append(AssessmentFinding(
                finding_id="FIND-RNTM-ERRORS-001",
                category=FindingCategory.RUNTIME_INCIDENT,
                severity=FindingSeverity.HIGH,
                title=f"Active Runtime Exceptions Observed ({len(error_events)} Events)",
                description=f"The runtime telemetry ledger recorded {len(error_events)} error/exception events linked to components in this repository.",
                rationale="Runtime exceptions point to active instability under live operational traffic.",
                affected_entities=list({e.service_name for e in error_events if e.service_name})[:5],
                affected_files=[],
                evidence_references=[{"error_event_count": len(error_events)}],
                detection_method="runtime_telemetry_correlation",
                confidence=1.0,
                known_limitations="Requires continuous runtime event stream ingestion.",
                recommended_action="Inspect correlated incident traces and harden error recovery in affected services.",
            ))

        runtime_score = max(100.0 - (len(error_events) * 10.0) - (len(incidents) * 15.0), 30.0)
        dim_runtime = DimensionalScore(
            dimension_name="Runtime & Incident Evidence",
            score=runtime_score,
            status="HEALTHY" if runtime_score >= 80 else ("ATTENTION" if runtime_score >= 50 else "AT_RISK"),
            summary=f"{len(incidents)} incidents and {len(error_events)} runtime exception events recorded.",
            key_metrics={"incidents_count": len(incidents), "runtime_errors_count": len(error_events)},
        )

        # --- DIMENSION 9: Analysis Completeness & Confidence ---
        comp_score = completeness.coverage_percentage
        dim_comp = DimensionalScore(
            dimension_name="Analysis Completeness & Confidence",
            score=comp_score,
            status="HEALTHY" if comp_score >= 85 else ("ATTENTION" if comp_score >= 50 else "AT_RISK"),
            summary=completeness.explanation,
            key_metrics={
                "coverage_pct": comp_score,
                "analyzed_files": completeness.files_analyzed,
                "total_files": completeness.files_discovered,
            },
        )

        scores = [
            dim_arch,
            dim_coupling,
            dim_api,
            dim_tests,
            dim_impact,
            dim_config,
            dim_maint,
            dim_runtime,
            dim_comp,
        ]

        return scores, findings

    def _synthesize_roadmap(
        self,
        findings: List[AssessmentFinding],
        completeness: DiscoveryCompleteness,
    ) -> List[RoadmapRecommendation]:
        """Synthesizes prioritized, non-destructive advisory recommendations."""
        roadmap: List[RoadmapRecommendation] = []
        rec_idx = 1

        # Priority P0: Critical test gaps or circular dependencies
        crit_findings = [f for f in findings if f.severity in (FindingSeverity.CRITICAL, FindingSeverity.HIGH)]
        for f in crit_findings[:3]:
            priority = RoadmapPriority.P0_IMMEDIATE if f.category in (FindingCategory.TEST_COVERAGE, FindingCategory.ARCHITECTURE) else RoadmapPriority.P1_HIGH
            roadmap.append(RoadmapRecommendation(
                recommendation_id=f"REC-{rec_idx:03d}",
                priority=priority,
                title=f"Resolve {f.title}",
                supporting_finding_ids=[f.finding_id],
                affected_components=f.affected_entities,
                technical_rationale=f.rationale,
                expected_benefit="Constrain change-impact blast radius and establish verified regression boundaries.",
                implementation_considerations=[
                    "Draft remediation plan before altering any production source files.",
                    "Execute regression test suite to confirm baseline stationary state.",
                ],
                dependencies_or_prerequisites=[],
                verification_criteria="Re-run technical assessment; finding status must resolve to clean.",
                confidence=f.confidence,
                known_limitations="Advisory guidance; engineer review required.",
            ))
            rec_idx += 1

        # Priority P2/P3: Moderate coupling and hotspots
        med_findings = [f for f in findings if f.severity in (FindingSeverity.MEDIUM, FindingSeverity.LOW)]
        for f in med_findings[:3]:
            roadmap.append(RoadmapRecommendation(
                recommendation_id=f"REC-{rec_idx:03d}",
                priority=RoadmapPriority.P2_MEDIUM if f.severity == FindingSeverity.MEDIUM else RoadmapPriority.P3_LONG_TERM,
                title=f"Address {f.title}",
                supporting_finding_ids=[f.finding_id],
                affected_components=f.affected_entities,
                technical_rationale=f.rationale,
                expected_benefit="Improve codebase cohesion and maintainability over multi-sprint modernization.",
                implementation_considerations=["Perform modular refactoring incrementally."],
                dependencies_or_prerequisites=[],
                verification_criteria="Fan-out density or file size reduces beneath threshold.",
                confidence=f.confidence,
                known_limitations="Advisory guidance.",
            ))
            rec_idx += 1

        return roadmap

    def _generate_report(
        self,
        repo: Repository,
        snap: RepositorySnapshot,
        completeness: DiscoveryCompleteness,
        scores: List[DimensionalScore],
        findings: List[AssessmentFinding],
        roadmap: List[RoadmapRecommendation],
    ) -> Tuple[str, str]:
        """Generates executive summary and comprehensive sanitized markdown engineering report."""
        avg_score = round(sum(s.score for s in scores) / len(scores), 1) if scores else 0.0

        summary = (
            f"Technical Health Assessment for '{repo.name}' (Revision: {snap.commit_hash[:8] if snap.commit_hash else 'HEAD'}). "
            f"Discovery Status: {completeness.status.value} ({completeness.coverage_percentage}% code coverage across {completeness.files_analyzed} files). "
            f"Average Technical Health Score: {avg_score}/100. "
            f"Identified {len(findings)} findings ({sum(1 for f in findings if f.severity in (FindingSeverity.CRITICAL, FindingSeverity.HIGH))} Critical/High) "
            f"and synthesized {len(roadmap)} prioritized advisory remediation roadmap recommendations."
        )

        md_lines = [
            f"# Technical Assessment & Architecture Health Report: {repo.name}",
            "",
            f"**Repository:** `{repo.name}` (`{repo.id}`)  ",
            f"**Revision Commit SHA:** `{snap.commit_hash or 'N/A'}`  ",
            f"**Assessment ID:** `assess_{snap.id[:8]}`  ",
            f"**Generated At:** `{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}`  ",
            f"**Discovery Status:** `{completeness.status.value}` ({completeness.coverage_percentage}% AST Coverage)  ",
            "",
            "---",
            "",
            "## 1. Executive Summary",
            "",
            summary,
            "",
            "---",
            "",
            "## 2. Discovery Scope & Completeness",
            "",
            "| Discovery Dimension | Metric | Detail |",
            "| :--- | :---: | :--- |",
            f"| **Files Discovered** | `{completeness.files_discovered}` | Total scanned repository files |",
            f"| **Files Analyzed (AST)** | `{completeness.files_analyzed}` | Verified parsed source files |",
            f"| **Files Skipped** | `{completeness.files_skipped}` | Binary, vendor, or generated assets |",
            f"| **Unsupported Files** | `{completeness.files_unsupported}` | Non-code or unsupported language extensions |",
            f"| **Extracted Symbols** | `{completeness.symbols_extracted}` | Classes, interfaces, functions, services |",
            f"| **Indexed Relationships** | `{completeness.relationships_extracted}` | Calls, imports, dependencies, tests |",
            f"| **Discovered Tests** | `{completeness.tests_discovered}` | Identified test suites and test cases |",
            f"| **Linked Tests** | `{completeness.tests_linked}` | Deterministically mapped to tested components |",
            "",
            f"> [!NOTE]",
            f"> **Discovery Note:** {completeness.explanation}",
            "",
            "---",
            "",
            "## 3. 9-Dimensional Technical Health Scorecard",
            "",
            "| Technical Dimension | Score | Status | Key Evaluation Summary |",
            "| :--- | :---: | :---: | :--- |",
        ]

        for s in scores:
            status_badge = f"**{s.status}**"
            md_lines.append(f"| {s.dimension_name} | `{s.score}/100` | {status_badge} | {s.summary} |")

        md_lines.extend([
            "",
            "---",
            "",
            f"## 4. Prioritized Findings ({len(findings)} Detected)",
            "",
        ])

        if not findings:
            md_lines.append("_No critical architectural, coupling, or testing findings identified._\n")
        else:
            for f in findings:
                md_lines.extend([
                    f"### [{f.severity.value}] {f.title}",
                    f"- **Finding ID:** `{f.finding_id}`",
                    f"- **Category:** `{f.category.value}`",
                    f"- **Detection Method:** `{f.detection_method}` (Confidence: `{f.confidence}`)",
                    f"- **Affected Entities:** {', '.join(f'`{e}`' for e in f.affected_entities) if f.affected_entities else 'None'}",
                    f"- **Description:** {f.description}",
                    f"- **Technical Rationale:** {f.rationale}",
                    f"- **Recommended Action:** {f.recommended_action}",
                    f"- **Limitations:** _{f.known_limitations}_",
                    "",
                ])

        md_lines.extend([
            "---",
            "",
            f"## 5. Advisory Remediation Roadmap ({len(roadmap)} Recommendations)",
            "",
            "> [!IMPORTANT]",
            "> **Governance Rule:** The remediation roadmap is advisory and strictly non-destructive. No source code modifications or git commits are performed without explicit engineer authorization.",
            "",
        ])

        for r in roadmap:
            md_lines.extend([
                f"### [{r.priority.value}] {r.title}",
                f"- **Recommendation ID:** `{r.recommendation_id}`",
                f"- **Target Components:** {', '.join(f'`{c}`' for c in r.affected_components) if r.affected_components else 'General'}",
                f"- **Expected Benefit:** {r.expected_benefit}",
                f"- **Technical Rationale:** {r.technical_rationale}",
                f"- **Verification Criteria:** `{r.verification_criteria}`",
                "",
            ])

        md_lines.extend([
            "---",
            "",
            "## 6. Analysis Limitations & Forensic Boundaries",
            "",
            "- **Static Determinism:** Analysis relies on verifiable AST symbols and dependency relationships; untracked external HTTP callers outside this repository cannot be evaluated.",
            "- **Zero Code Modification:** This technical assessment is strictly read-only and analytical.",
            "",
            "**Report Version:** `Phase-9-v1.0`  ",
            "**Engine:** TwinCore Deterministic Assessment Engine  ",
        ])

        full_markdown = "\n".join(md_lines)
        sanitized_markdown, _ = self.sanitizer.sanitize_text(full_markdown)
        return summary, sanitized_markdown

    def _persist_assessment(
        self,
        db: Session,
        repo: Repository,
        snap: RepositorySnapshot,
        result: TechnicalAssessmentResult,
    ) -> None:
        """Persists technical assessment record into PostgreSQL under AnalysisRun."""
        try:
            analysis_run = AnalysisRun(
                id=result.assessment_id,
                project_id=repo.project_id,
                repository_id=repo.id,
                snapshot_id=snap.id,
                run_type="technical_assessment",
                status="COMPLETED",
                analyzer_names=["technical_assessment_engine", "discovery_brain_engine"],
                summary={
                    "assessment_id": result.assessment_id,
                    "repository_id": repo.id,
                    "snapshot_id": snap.id,
                    "commit_hash": result.commit_hash,
                    "completeness": result.completeness.dict(),
                    "findings_count": len(result.findings),
                    "roadmap_count": len(result.roadmap),
                    "executive_summary": result.executive_summary,
                    "dimensional_scores": [s.dict() for s in result.dimensional_scores],
                    "report_markdown": result.report_markdown,
                },
                artifacts_created=len(result.findings),
                errors=[],
                completed_at=datetime.utcnow(),
            )
            db.merge(analysis_run)
            db.commit()
        except Exception as err:
            db.rollback()
            # Non-blocking persistence warning
            print(f"Warning: Failed to persist assessment analysis run: {err}")


technical_assessment_engine = TechnicalAssessmentEngine()
