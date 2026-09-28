"""
Phase 8 — What-If / Scenario Simulation Engine.
Deterministic coordinator of virtual twin mutations, impact traversal,
test impact correlation, architecture guardrail checks, and scenario risk synthesis.
Zero LLM dependencies. Guarantees 100% isolation and safety.
"""

import time
import uuid
from typing import List, Dict, Set, Optional, Any
from sqlalchemy.orm import Session

from app.models.entities import (
    StructuralArtifact,
    ArtifactRelationship,
    RepositorySnapshot,
    RuntimeEvent,
    Incident,
)
from app.services.impact.analyzer import change_impact_analyzer, ChangeImpactAnalyzer
from app.services.testing.engine import test_impact_engine, TestImpactEngine
from app.services.testing.models import TestImpactClassification
from app.services.risk.guardrails import guardrail_evaluator, ArchitectureGuardrailEvaluator
from app.services.risk.engine import risk_intelligence_engine, RiskIntelligenceEngine
from app.services.risk.models import GuardrailStatus, RiskAssessmentResult
from app.services.simulation.models import (
    MutationType,
    ScenarioStatus,
    EvidenceCategory,
    ProposedMutation,
    ScenarioValidationResult,
    SimulationEvidenceItem,
    SimulatedImpactSummary,
    SimulatedTestImpactSummary,
    SimulatedRiskSummary,
    VirtualTwinComparison,
    ScenarioAnalysisResult,
)
from app.services.simulation.validator import scenario_validator, ScenarioValidator
from app.services.simulation.virtual_twin import VirtualTwinModel


class ScenarioSimulationEngine:
    """
    Coordinates what-if scenario simulations against isolated in-memory Virtual Twins.
    """

    def __init__(
        self,
        validator: Optional[ScenarioValidator] = None,
        impact_analyzer: Optional[ChangeImpactAnalyzer] = None,
        test_engine: Optional[TestImpactEngine] = None,
        guardrail_eval: Optional[ArchitectureGuardrailEvaluator] = None,
        risk_engine_instance: Optional[RiskIntelligenceEngine] = None,
    ):
        self.validator = validator or scenario_validator
        self.impact_analyzer = impact_analyzer or change_impact_analyzer
        self.test_engine = test_engine or test_impact_engine
        self.guardrail_evaluator = guardrail_eval or guardrail_evaluator
        self.risk_engine = risk_engine_instance or risk_intelligence_engine

    def simulate_scenario(
        self,
        db: Session,
        repository_id: str,
        base_snapshot_id: str,
        name: str,
        proposed_changes: List[ProposedMutation],
        scenario_id: Optional[str] = None,
        description: Optional[str] = None,
        baseline_path: Optional[str] = None,
    ) -> ScenarioAnalysisResult:
        """
        Executes a deterministic what-if scenario simulation without modifying real repository state.
        """
        start_time = time.perf_counter()
        scen_id = scenario_id or f"scen_{uuid.uuid4().hex[:12]}"
        now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        # 1. Fetch base snapshot artifacts and relationships (read-only baseline)
        base_artifacts = (
            db.query(StructuralArtifact)
            .filter_by(snapshot_id=base_snapshot_id)
            .all()
        )
        base_rels = (
            db.query(ArtifactRelationship)
            .filter_by(snapshot_id=base_snapshot_id)
            .all()
        )

        # 2. Validate proposed mutations against baseline state
        validation: ScenarioValidationResult = self.validator.validate_mutations(
            base_artifacts=base_artifacts,
            base_rels=base_rels,
            mutations=proposed_changes,
        )

        # If invalid, return failed scenario with explanation
        if not validation.is_valid:
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return ScenarioAnalysisResult(
                scenario_id=scen_id,
                repository_id=repository_id,
                base_snapshot_id=base_snapshot_id,
                name=name,
                description=description,
                status=ScenarioStatus.FAILED,
                created_at=now_iso,
                proposed_changes=proposed_changes,
                validation=validation,
                impact=SimulatedImpactSummary(),
                tests=SimulatedTestImpactSummary(),
                risk=SimulatedRiskSummary(
                    scenario_risk_category="UNKNOWN",
                    confidence_level="LOW",
                    confidence_score=0.0,
                    overall_score=0.0,
                    risk_factors=[],
                    explanation=f"Scenario validation failed: {'; '.join(validation.errors)}",
                ),
                guardrails=[],
                evidence=[],
                assumptions=["Baseline state was assumed clean."],
                unknowns=validation.unknown_entities,
                comparison=VirtualTwinComparison(),
                execution_time_ms=elapsed_ms,
            )

        # 3. Create isolated in-memory Virtual Twin and apply validated mutations
        v_twin = VirtualTwinModel(
            repository_id=repository_id,
            base_snapshot_id=base_snapshot_id,
            base_artifacts=base_artifacts,
            base_rels=base_rels,
        )

        for mut in validation.validated_mutations:
            v_twin.apply_mutation(mut)

        v_changeset = v_twin.build_change_set()

        # Handle empty mutations case cleanly
        if not v_changeset.changes:
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return ScenarioAnalysisResult(
                scenario_id=scen_id,
                repository_id=repository_id,
                base_snapshot_id=base_snapshot_id,
                name=name,
                description=description,
                status=ScenarioStatus.COMPLETED,
                created_at=now_iso,
                proposed_changes=proposed_changes,
                validation=validation,
                impact=SimulatedImpactSummary(),
                tests=SimulatedTestImpactSummary(),
                risk=SimulatedRiskSummary(
                    scenario_risk_category="LOW",
                    confidence_level="HIGH",
                    confidence_score=1.0,
                    overall_score=0.0,
                    risk_factors=[],
                    explanation="Scenario evaluated with no proposed structural changes. Baseline state remains unchanged.",
                ),
                guardrails=[],
                evidence=[],
                assumptions=["No hypothetical modifications applied."],
                unknowns=[],
                comparison=VirtualTwinComparison(),
                execution_time_ms=elapsed_ms,
            )

        # 4. Run Phase 4 Change Impact on Virtual Twin
        sim_impact = self.impact_analyzer.analyze(
            db=db,
            repository_id=repository_id,
            base_snapshot_id=base_snapshot_id,
            target_snapshot_id=v_twin.virtual_snapshot_id,
            change_set=v_changeset,
            target_artifacts=v_twin.virtual_artifacts,
            target_rels=v_twin.virtual_rels,
            base_artifacts=base_artifacts,
            base_rels=base_rels,
        )

        changed_ids: Set[str] = {c.artifact_id for c in v_changeset.changes if c.artifact_id}
        impacted_ids: Set[str] = {f.impacted_node_id for f in sim_impact.findings if f.impacted_node_id}
        all_relevant_ids = changed_ids | impacted_ids

        # 5. Run Phase 6 Test Impact on Virtual Twin
        sim_tests = self.test_engine.compute_test_impact(
            db=db,
            repository_id=repository_id,
            base_snapshot_id=base_snapshot_id,
            target_snapshot_id=v_twin.virtual_snapshot_id,
            change_set=v_changeset,
            target_artifacts=v_twin.virtual_artifacts,
            base_artifacts=base_artifacts,
            target_rels=v_twin.virtual_rels,
            base_rels=base_rels,
        )

        # 6. Run Phase 7 Architecture Guardrails on Virtual Twin
        sim_guardrails = self.guardrail_evaluator.evaluate_guardrails(
            db=db,
            repository_id=repository_id,
            snapshot_id=base_snapshot_id,
            changed_artifact_ids=changed_ids,
            impacted_artifact_ids=impacted_ids,
            baseline_path=baseline_path,
            artifacts=v_twin.virtual_artifacts,
            relationships=v_twin.virtual_rels,
        )

        # Also evaluate baseline guardrails to compute delta
        baseline_guardrails = self.guardrail_evaluator.evaluate_guardrails(
            db=db,
            repository_id=repository_id,
            snapshot_id=base_snapshot_id,
            baseline_path=baseline_path,
            artifacts=base_artifacts,
            relationships=base_rels,
        )

        # 7. Run Phase 7 Risk Intelligence Engine on Virtual Twin
        sim_risk: RiskAssessmentResult = self.risk_engine.assess_risk(
            db=db,
            repository_id=repository_id,
            base_snapshot_id=base_snapshot_id,
            target_snapshot_id=v_twin.virtual_snapshot_id,
            precomputed_impact=sim_impact,
            precomputed_test_impact=sim_tests,
            precomputed_guardrails=sim_guardrails,
            target_artifacts=v_twin.virtual_artifacts,
            target_relationships=v_twin.virtual_rels,
        )

        # 8. Separate and Categorize Evidence
        evidence_items: List[SimulationEvidenceItem] = []

        # (a) Simulated Structural Evidence
        for finding in sim_impact.findings:
            evidence_items.append(
                SimulationEvidenceItem(
                    category=EvidenceCategory.SIMULATED_STRUCTURAL,
                    label=f"Simulated propagation: {finding.source_qual_name} -> {finding.target_qual_name}",
                    description=f"Hypothetical change in '{finding.source_qual_name}' potentially propagates to '{finding.target_qual_name}' via {finding.relationship_type} (depth {finding.impact_level}).",
                    source_entity=finding.source_qual_name,
                    target_entity=finding.target_qual_name,
                    details={"relationship_type": finding.relationship_type, "depth": finding.impact_level},
                )
            )

        for t_item in sim_tests.affected_tests:
            src_name = t_item.impact_path[0] if t_item.impact_path else "ChangedEntity"
            evidence_items.append(
                SimulationEvidenceItem(
                    category=EvidenceCategory.SIMULATED_STRUCTURAL,
                    label=f"Simulated test exposure: {t_item.test_name}",
                    description=f"Test '{t_item.test_name}' is classified as {t_item.classification.value} based on structural reachability from proposed changes.",
                    source_entity=src_name,
                    target_entity=t_item.test_name,
                    details={"classification": t_item.classification.value, "impact_path": t_item.impact_path},
                )
            )

        for g in sim_guardrails:
            if g.status in (GuardrailStatus.VIOLATION, GuardrailStatus.WARN):
                evidence_items.append(
                    SimulationEvidenceItem(
                        category=EvidenceCategory.SIMULATED_STRUCTURAL,
                        label=f"Simulated guardrail {g.status.value}: {g.rule_name}",
                        description=f"Proposed scenario triggers architectural guardrail violation: {g.explanation}",
                        source_entity=g.source,
                        target_entity=g.target,
                        details={"rule_id": g.rule_id, "severity": g.severity.value},
                    )
                )

        # (b) Observed Runtime Evidence (Real telemetry intersecting simulated boundary)
        observed_runtime_events: List[RuntimeEvent] = []
        if all_relevant_ids:
            observed_runtime_events = (
                db.query(RuntimeEvent)
                .filter(
                    RuntimeEvent.repository_id == repository_id,
                    RuntimeEvent.component_artifact_id.in_(list(all_relevant_ids)),
                )
                .order_by(RuntimeEvent.timestamp.desc())
                .limit(20)
                .all()
            )

        for rev in observed_runtime_events:
            art_obj = v_twin.art_by_id.get(rev.component_artifact_id)
            art_name = art_obj.qualified_name if art_obj else (rev.service_name or "Component")
            payload = rev.payload or {}
            http_status = payload.get("http_status_code", 200)
            latency = payload.get("latency_ms", 0)
            evidence_items.append(
                SimulationEvidenceItem(
                    category=EvidenceCategory.OBSERVED_RUNTIME,
                    label=f"Observed runtime activity: {art_name}",
                    description=f"Component '{art_name}' has recent production activity (HTTP {http_status}, {latency}ms). Note: This is real observed production telemetry, NOT generated by this hypothetical change.",
                    source_entity=art_name,
                    details={"event_id": rev.id, "latency_ms": latency, "http_status_code": http_status},
                )
            )

        # (c) Historical Incident Evidence (Real past incidents intersecting simulated boundary)
        historical_incidents: List[Incident] = []
        if all_relevant_ids:
            historical_incidents = (
                db.query(Incident)
                .filter(Incident.affected_component_id.in_(list(all_relevant_ids)))
                .order_by(Incident.detected_at.desc())
                .limit(10)
                .all()
            )

        for inc in historical_incidents:
            art_obj = v_twin.art_by_id.get(inc.affected_component_id)
            art_name = art_obj.qualified_name if art_obj else "Component"
            inc_title = inc.title or "Incident"
            evidence_items.append(
                SimulationEvidenceItem(
                    category=EvidenceCategory.HISTORICAL_INCIDENT,
                    label=f"Historical incident: {inc_title} ({art_name})",
                    description=f"Component '{art_name}' was involved in historical incident '{inc_title}' ({inc.severity}). Note: Touched component has historical vulnerability; this is real past data.",
                    source_entity=art_name,
                    details={"incident_id": inc.id, "title": inc_title, "severity": inc.severity, "status": inc.status},
                )
            )

        # (d) Unknown Evidence (Gaps in verification or telemetry)
        unknown_evidence_signals: List[str] = []
        for uk in sim_tests.unknown_coverage:
            msg = f"Changed entity '{uk.name}' has unknown test coverage (0 tests found)."
            unknown_evidence_signals.append(msg)
            evidence_items.append(
                SimulationEvidenceItem(
                    category=EvidenceCategory.UNKNOWN_EVIDENCE,
                    label=f"Unknown test coverage: {uk.name}",
                    description=msg,
                    source_entity=uk.name,
                    details={"artifact_id": uk.artifact_id},
                )
            )

        # 9. Comparison: Current Baseline vs Scenario Twin
        baseline_failed_rules = {g.rule_id for g in baseline_guardrails if g.status == GuardrailStatus.VIOLATION}
        new_violations = [
            g.dict() for g in sim_guardrails
            if g.status == GuardrailStatus.VIOLATION and g.rule_id not in baseline_failed_rules
        ]
        base_violations = [
            g.dict() for g in baseline_guardrails
            if g.status == GuardrailStatus.VIOLATION
        ]

        comparison = VirtualTwinComparison(
            added_relationships=v_twin.added_relationships,
            removed_relationships=v_twin.removed_relationships,
            newly_affected_components=sim_impact.affected_categories.get("affected_components", []),
            removed_affected_components=[],
            new_guardrail_violations=new_violations,
            baseline_guardrail_violations=base_violations,
            risk_factor_deltas={
                (rf.factor_id.value if hasattr(rf.factor_id, "value") else str(rf.factor_id)): rf.score
                for rf in sim_risk.risk_factors
            },
        )

        # 10. Explicit Simulation Phrasing for Risk & Explanations
        scenario_risk_category = sim_risk.overall_category.value
        changed_count = getattr(sim_impact.summary, "changed", len(v_changeset.changes))
        risk_explanation = (
            f"Scenario risk: {scenario_risk_category}. "
            f"Simulated change proposes {len(validation.validated_mutations)} mutations touching "
            f"{changed_count} entities. "
            f"Potentially affects {sim_impact.summary.affected_components} components, "
            f"{sim_impact.summary.affected_apis} APIs, and {len(sim_tests.affected_tests)} tests "
            f"({len(sim_tests.unknown_coverage)} entities with unknown coverage). "
            f"{'Triggers ' + str(len(new_violations)) + ' new architecture guardrail violations.' if new_violations else 'No new architecture violations detected.'}"
        )

        # 11. Compile Results
        impact_summary = SimulatedImpactSummary(
            changed_artifacts=[c.qualified_name for c in v_changeset.changes],
            directly_affected=list({f.target_qual_name for f in sim_impact.findings if f.impact_level == 1}),
            indirectly_affected=list({f.target_qual_name for f in sim_impact.findings if f.impact_level > 1}),
            affected_components=sim_impact.affected_categories.get("affected_components", []),
            affected_services=sim_impact.affected_categories.get("affected_services", []),
            affected_apis=sim_impact.affected_categories.get("affected_apis", []),
            affected_tests=sim_impact.affected_categories.get("affected_tests", []),
            max_propagation_depth=sim_impact.summary.max_depth_reached,
            propagation_paths_count=len(sim_impact.paths),
            propagation_paths=[p.dict() for p in sim_impact.paths[:25]],
        )

        directly_tests = [
            t.test_name for t in sim_tests.affected_tests
            if t.classification == TestImpactClassification.DIRECTLY_AFFECTED
        ]
        indirectly_tests = [
            t.test_name for t in sim_tests.affected_tests
            if t.classification == TestImpactClassification.INDIRECTLY_AFFECTED
        ]
        unaffected_test_names = [
            t.test_name for t in sim_tests.unaffected_tests
        ]

        test_summary = SimulatedTestImpactSummary(
            directly_affected_tests=directly_tests,
            indirectly_affected_tests=indirectly_tests,
            unaffected_tests=unaffected_test_names,
            unknown_coverage_count=sim_tests.summary.unknown_coverage_count,
            unknown_coverage_entities=[u.name for u in sim_tests.unknown_coverage],
        )

        risk_summary = SimulatedRiskSummary(
            scenario_risk_category=scenario_risk_category,
            confidence_level=sim_risk.confidence.value,
            confidence_score=sim_risk.confidence_score,
            overall_score=sim_risk.overall_score,
            risk_factors=[rf.dict() for rf in sim_risk.risk_factors],
            explanation=risk_explanation,
        )

        assumptions = [
            f"Simulation evaluated against baseline snapshot '{base_snapshot_id}'.",
            "Target environment topology is assumed structurally coherent with the baseline Digital Twin.",
            "Relationships outside the tested boundary are assumed stationary during simulation.",
        ]

        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

        return ScenarioAnalysisResult(
            scenario_id=scen_id,
            repository_id=repository_id,
            base_snapshot_id=base_snapshot_id,
            name=name,
            description=description,
            status=ScenarioStatus.COMPLETED,
            created_at=now_iso,
            proposed_changes=validation.validated_mutations,
            validation=validation,
            impact=impact_summary,
            tests=test_summary,
            risk=risk_summary,
            guardrails=[g.dict() for g in sim_guardrails],
            evidence=evidence_items,
            assumptions=assumptions,
            unknowns=unknown_evidence_signals + validation.unknown_entities,
            comparison=comparison,
            execution_time_ms=elapsed_ms,
        )


scenario_simulation_engine = ScenarioSimulationEngine()
