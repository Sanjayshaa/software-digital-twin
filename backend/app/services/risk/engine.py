"""
Phase 7 — Risk Intelligence Engine.
Deterministic, evidence-driven risk factor computation, architecture guardrail verification,
and explainable assessment generation.
Zero LLM dependencies. 100% deterministic graph, test, and telemetry correlation.
"""

import time
import uuid
from typing import List, Dict, Set, Optional, Any, Tuple
from sqlalchemy.orm import Session
from datetime import datetime

from app.models.entities import (
    Repository,
    RepositorySnapshot,
    StructuralArtifact,
    ArtifactRelationship,
    RuntimeEvent,
    Incident,
    APIEndpoint,
)
from app.services.impact.analyzer import change_impact_analyzer, ChangeImpactAnalyzer
from app.services.impact.models import ChangeSet, ImpactResult, ImpactConfig
from app.services.testing.engine import test_impact_engine, TestImpactEngine
from app.services.testing.models import TestImpactResult, TestImpactConfig
from app.services.risk.guardrails import guardrail_evaluator, ArchitectureGuardrailEvaluator
from app.services.risk.models import (
    RiskCategory,
    ConfidenceLevel,
    GuardrailResult,
    GuardrailStatus,
    GuardrailSeverity,
    RiskFactorType,
    RiskFactorItem,
    RiskConfig,
    RiskAssessmentResult,
)


class RiskIntelligenceEngine:
    """
    Coordinates multi-dimensional risk synthesis:
    Change Evidence + Impact Evidence + Test Impact + Architecture Guardrails +
    Dependency Coupling + Runtime Evidence + Incident History -> Explainable Risk Assessment.
    """

    def __init__(
        self,
        impact_analyzer: Optional[ChangeImpactAnalyzer] = None,
        test_engine: Optional[TestImpactEngine] = None,
        guardrail_eval: Optional[ArchitectureGuardrailEvaluator] = None,
    ):
        self.impact_analyzer = impact_analyzer or change_impact_analyzer
        self.test_engine = test_engine or test_impact_engine
        self.guardrail_evaluator = guardrail_eval or guardrail_evaluator

    def assess_risk(
        self,
        db: Session,
        repository_id: str,
        base_snapshot_id: str,
        target_snapshot_id: str,
        config: Optional[RiskConfig] = None,
        precomputed_impact: Optional[ImpactResult] = None,
        precomputed_test_impact: Optional[TestImpactResult] = None,
        precomputed_guardrails: Optional[List[GuardrailResult]] = None,
        target_artifacts: Optional[List[StructuralArtifact]] = None,
        target_relationships: Optional[List[ArtifactRelationship]] = None,
    ) -> RiskAssessmentResult:
        """
        Executes deterministic, evidence-driven Risk Intelligence analysis between two snapshots.
        """
        start_time = time.perf_counter()
        cfg = config or RiskConfig()
        analysis_id = f"risk_{uuid.uuid4().hex[:12]}"

        # 1. Reuse or Compute Phase 4 Change Impact
        if precomputed_impact:
            impact_res = precomputed_impact
        else:
            impact_cfg = ImpactConfig(max_depth=cfg.max_impact_depth)
            impact_res = self.impact_analyzer.analyze(
                db=db,
                repository_id=repository_id,
                base_snapshot_id=base_snapshot_id,
                target_snapshot_id=target_snapshot_id,
                config=impact_cfg,
            )

        changes = impact_res.changes
        changed_artifact_ids: Set[str] = {c.artifact_id for c in changes if c.artifact_id}
        impacted_artifact_ids: Set[str] = {f.impacted_node_id for f in impact_res.findings if f.impacted_node_id}
        all_relevant_ids = changed_artifact_ids | impacted_artifact_ids

        # 2. Reuse or Compute Phase 6 Test Impact
        test_impact_error: Optional[str] = None
        if precomputed_test_impact:
            test_res = precomputed_test_impact
        else:
            try:
                test_cfg = TestImpactConfig(max_depth=cfg.max_impact_depth)
                test_res = self.test_engine.compute_test_impact(
                    db=db,
                    repository_id=repository_id,
                    base_snapshot_id=base_snapshot_id,
                    target_snapshot_id=target_snapshot_id,
                    config=test_cfg,
                )
            except Exception as e:
                test_res = None
                test_impact_error = str(e)

        # 3. Evaluate Architecture Guardrails
        if precomputed_guardrails is not None:
            guardrail_results = precomputed_guardrails
        else:
            guardrail_results = self.guardrail_evaluator.evaluate_guardrails(
                db=db,
                repository_id=repository_id,
                snapshot_id=target_snapshot_id,
                changed_artifact_ids=changed_artifact_ids,
                impacted_artifact_ids=impacted_artifact_ids,
                baseline_path=cfg.baseline_path,
                artifacts=target_artifacts,
                relationships=target_relationships,
            )

        # 4. Query Snapshot Structural Artifacts & Relationships for Coupling & API Analysis
        if target_artifacts is None:
            target_artifacts = db.query(StructuralArtifact).filter_by(snapshot_id=target_snapshot_id).all()
        if target_relationships is None:
            target_relationships = db.query(ArtifactRelationship).filter_by(snapshot_id=target_snapshot_id).all()
        art_map = {a.id: a for a in target_artifacts}

        # 5. Query Phase 5 Runtime Events for affected components
        runtime_events: List[RuntimeEvent] = []
        if cfg.include_runtime and all_relevant_ids:
            runtime_events = (
                db.query(RuntimeEvent)
                .filter(
                    RuntimeEvent.repository_id == repository_id,
                    RuntimeEvent.component_artifact_id.in_(list(all_relevant_ids)),
                )
                .order_by(RuntimeEvent.timestamp.desc())
                .limit(50)
                .all()
            )

        # 6. Query Phase 5 Incidents for affected components
        incidents: List[Incident] = []
        if cfg.include_incidents and all_relevant_ids:
            incidents = (
                db.query(Incident)
                .filter(
                    Incident.affected_component_id.in_(list(all_relevant_ids)),
                )
                .order_by(Incident.detected_at.desc())
                .limit(20)
                .all()
            )

        # 7. Compute the 9 Deterministic Risk Factors
        risk_factors: List[RiskFactorItem] = []
        unknown_signals: List[str] = []

        # Factor 1: IMPACT_BREADTH
        f_breadth = self._compute_impact_breadth(impact_res, changes)
        risk_factors.append(f_breadth)

        # Factor 2: IMPACT_DEPTH
        f_depth = self._compute_impact_depth(impact_res)
        risk_factors.append(f_depth)

        # Factor 3: TEST_IMPACT
        f_test, test_unknowns = self._compute_test_impact_factor(test_res, test_impact_error)
        risk_factors.append(f_test)
        unknown_signals.extend(test_unknowns)

        # Factor 4: ARCHITECTURE_DRIFT
        f_arch, arch_unknowns = self._compute_architecture_factor(guardrail_results)
        risk_factors.append(f_arch)
        unknown_signals.extend(arch_unknowns)

        # Factor 5: DEPENDENCY_COUPLING
        f_coupling = self._compute_coupling_factor(changed_artifact_ids, target_relationships, art_map)
        risk_factors.append(f_coupling)

        # Factor 6: RUNTIME_ACTIVITY
        f_runtime, runtime_unknowns = self._compute_runtime_factor(runtime_events, changes)
        risk_factors.append(f_runtime)
        unknown_signals.extend(runtime_unknowns)

        # Factor 7: INCIDENT_HISTORY
        f_incident = self._compute_incident_factor(incidents, changes, art_map)
        risk_factors.append(f_incident)

        # Factor 8: API_SURFACE
        f_api, affected_apis = self._compute_api_surface_factor(changes, impact_res, art_map, target_relationships)
        risk_factors.append(f_api)

        # Factor 9: UNKNOWN_EVIDENCE
        f_unknown = self._compute_unknown_evidence_factor(unknown_signals)
        risk_factors.append(f_unknown)

        # 8. Compute Transparent Category, Confidence, and Natural Language Explanation
        overall_category, overall_score = self._derive_overall_category(
            risk_factors=risk_factors,
            guardrail_results=guardrail_results,
            f_breadth=f_breadth,
            f_runtime=f_runtime,
            changes_count=len(changes),
        )

        confidence_level, confidence_score = self._derive_confidence(unknown_signals, test_res, runtime_events)

        explanation, recommendations = self._generate_explanation_and_recommendations(
            overall_category=overall_category,
            confidence_level=confidence_level,
            risk_factors=risk_factors,
            guardrail_results=guardrail_results,
            unknown_signals=unknown_signals,
            changes_count=len(changes),
        )

        # Summary collections
        affected_components = list({
            art_map[aid].qualified_name for aid in all_relevant_ids if aid in art_map
        })
        affected_test_names = [t.test_name for t in test_res.affected_tests]
        runtime_evidence_lines = [f"{e.service_name or 'service'}: {e.event_type} ({e.environment})" for e in runtime_events[:5]]
        incident_evidence_lines = [f"{i.title} [{i.severity.upper()}]" for i in incidents[:5]]

        execution_time_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

        return RiskAssessmentResult(
            analysis_id=analysis_id,
            repository_id=repository_id,
            base_snapshot_id=base_snapshot_id,
            target_snapshot_id=target_snapshot_id,
            overall_category=overall_category,
            overall_score=round(overall_score, 1),
            confidence=confidence_level,
            confidence_score=round(confidence_score, 2),
            explanation=explanation,
            risk_factors=risk_factors,
            guardrail_results=guardrail_results,
            affected_components=affected_components[:30],
            affected_apis=affected_apis,
            affected_tests=affected_test_names[:30],
            runtime_evidence=runtime_evidence_lines,
            incident_evidence=incident_evidence_lines,
            unknown_evidence=unknown_signals,
            recommendations=recommendations,
            execution_time_ms=execution_time_ms,
        )

    # -------------------------------------------------------------------------
    # FACTOR 1: IMPACT BREADTH
    # -------------------------------------------------------------------------
    def _compute_impact_breadth(self, impact_res: ImpactResult, changes: List[Any]) -> RiskFactorItem:
        total_affected = impact_res.summary.changed + impact_res.summary.directly_affected + impact_res.summary.indirectly_affected
        evidence = [
            f"{len(changes)} directly modified entity/entities",
            f"{impact_res.summary.directly_affected} directly affected downstream entity/entities",
            f"{impact_res.summary.indirectly_affected} indirectly affected entity/entities",
            f"Total affected blast radius: {total_affected} entities",
        ]

        if total_affected == 0:
            score = 0.0
            sev = "LOW"
            status = "NOT_APPLICABLE"
        elif total_affected <= 3:
            score = 20.0
            sev = "LOW"
            status = "OBSERVED"
        elif total_affected <= 8:
            score = 50.0
            sev = "MEDIUM"
            status = "OBSERVED"
        elif total_affected <= 15:
            score = 75.0
            sev = "HIGH"
            status = "OBSERVED"
        else:
            score = 95.0
            sev = "CRITICAL"
            status = "OBSERVED"

        return RiskFactorItem(
            factor_id=RiskFactorType.IMPACT_BREADTH,
            name="Impact Breadth",
            score=score,
            weight=1.1,
            severity=sev,
            status=status,
            evidence=evidence,
            details={"total_affected": total_affected, "changed": len(changes)},
            description="Measures the total quantity and scope of entities reached in the dependency blast radius.",
        )

    # -------------------------------------------------------------------------
    # FACTOR 2: IMPACT DEPTH
    # -------------------------------------------------------------------------
    def _compute_impact_depth(self, impact_res: ImpactResult) -> RiskFactorItem:
        max_depth = impact_res.summary.max_depth_reached
        evidence = [f"Maximum graph propagation depth reached: {max_depth} hop(s)"]
        if impact_res.paths:
            longest = max(impact_res.paths, key=lambda p: p.depth)
            evidence.append(f"Deepest causal chain ({longest.depth} hops): {' -> '.join(longest.nodes)}")

        if max_depth <= 1:
            score = 15.0 if max_depth == 1 else 0.0
            sev = "LOW"
            status = "OBSERVED" if max_depth == 1 else "NOT_APPLICABLE"
        elif max_depth == 2:
            score = 40.0
            sev = "MEDIUM"
            status = "OBSERVED"
        elif max_depth == 3:
            score = 70.0
            sev = "HIGH"
            status = "OBSERVED"
        else:
            score = 90.0
            sev = "CRITICAL"
            status = "OBSERVED"

        return RiskFactorItem(
            factor_id=RiskFactorType.IMPACT_DEPTH,
            name="Impact Depth",
            score=score,
            weight=0.8,
            severity=sev,
            status=status,
            evidence=evidence,
            details={"max_depth": max_depth},
            description="Measures the distance transitive changes propagate through the call and dependency graph.",
        )

    # -------------------------------------------------------------------------
    # FACTOR 3: TEST IMPACT
    # -------------------------------------------------------------------------
    def _compute_test_impact_factor(
        self,
        test_res: Optional[TestImpactResult],
        test_impact_error: Optional[str] = None,
    ) -> Tuple[RiskFactorItem, List[str]]:
        unknowns = []

        if test_res is None:
            err_msg = test_impact_error or "Test impact computation failed"
            unknown_msg = f"Evidence gap: Test impact analysis failed ({err_msg}). Test coverage cannot be verified."
            unknowns.append(unknown_msg)
            return RiskFactorItem(
                factor_id=RiskFactorType.TEST_IMPACT,
                name="Test Impact & Coverage",
                score=50.0,
                weight=1.2,
                severity="MEDIUM",
                status="FAILED",
                evidence=[
                    unknown_msg,
                    "Regression blast radius is unverified because test impact engine did not complete successfully.",
                ],
                details={"total_mapped": 0, "potentially_affected": 0, "unknown_coverage": 0, "analysis_failed": True},
                description="Reflects the potential regression risk based on affected tests and coverage completeness.",
            ), unknowns

        summ = test_res.summary

        if summ.total_tests_mapped == 0:
            unknown_msg = "Test coverage unknown: Zero test suites or cases mapped for repository."
            unknowns.append(unknown_msg)
            return RiskFactorItem(
                factor_id=RiskFactorType.TEST_IMPACT,
                name="Test Impact & Coverage",
                score=45.0,
                weight=1.2,
                severity="MEDIUM",
                status="UNKNOWN",
                evidence=[unknown_msg],
                details={"total_mapped": 0, "potentially_affected": 0, "unknown_coverage": 0},
                description="Reflects the potential regression risk based on affected tests and coverage completeness.",
            ), unknowns

        evidence = [
            f"{summ.potentially_affected_count} test(s) potentially affected ({summ.directly_affected_count} direct, {summ.indirectly_affected_count} indirect)",
            f"{summ.unaffected_count} mapped test(s) isolated from change blast radius",
        ]

        if summ.unknown_coverage_count > 0:
            evidence.append(f"Warning: {summ.unknown_coverage_count} changed entity/entities lack test coverage.")
            for u in test_res.unknown_coverage[:3]:
                unknowns.append(f"Changed entity '{u.qualified_name}' has unknown test coverage.")

        # Scoring
        base_test_score = min(60.0, summ.directly_affected_count * 15.0 + summ.indirectly_affected_count * 5.0)
        unknown_coverage_penalty = min(40.0, summ.unknown_coverage_count * 20.0)
        total_score = min(100.0, base_test_score + unknown_coverage_penalty)

        if total_score >= 75.0:
            sev = "HIGH"
        elif total_score >= 35.0:
            sev = "MEDIUM"
        else:
            sev = "LOW"

        return RiskFactorItem(
            factor_id=RiskFactorType.TEST_IMPACT,
            name="Test Impact & Coverage",
            score=total_score,
            weight=1.2,
            severity=sev,
            status="OBSERVED",
            evidence=evidence,
            details={
                "potentially_affected": summ.potentially_affected_count,
                "directly_affected": summ.directly_affected_count,
                "indirectly_affected": summ.indirectly_affected_count,
                "unknown_coverage": summ.unknown_coverage_count,
            },
            description="Reflects regression exposure based on affected tests and missing coverage for changed code.",
        ), unknowns

    # -------------------------------------------------------------------------
    # FACTOR 4: ARCHITECTURE DRIFT
    # -------------------------------------------------------------------------
    def _compute_architecture_factor(self, guardrails: List[GuardrailResult]) -> Tuple[RiskFactorItem, List[str]]:
        unknowns = []
        is_unknown = any(g.status == GuardrailStatus.UNKNOWN for g in guardrails)

        if is_unknown or not guardrails:
            msg = "Architecture status unknown: Baseline specification not configured or cannot be evaluated."
            unknowns.append(msg)
            return RiskFactorItem(
                factor_id=RiskFactorType.ARCHITECTURE_DRIFT,
                name="Architecture Conformance",
                score=30.0,
                weight=1.5,
                severity="MEDIUM",
                status="UNKNOWN",
                evidence=[msg],
                details={"violations": 0, "warnings": 0, "status": "UNKNOWN"},
                description="Evaluates changes against architectural layers, forbidden dependencies, and boundaries.",
            ), unknowns

        violations = [g for g in guardrails if g.status == GuardrailStatus.VIOLATION]
        warnings = [g for g in guardrails if g.status == GuardrailStatus.WARN]
        has_critical = any(v.severity == GuardrailSeverity.CRITICAL for v in violations)

        evidence = []
        for v in violations:
            evidence.append(f"VIOLATION [{v.rule_id}]: {v.rule_name} — {v.explanation}")
        for w in warnings:
            evidence.append(f"WARN [{w.rule_id}]: {w.rule_name} — {w.explanation}")

        if not violations and not warnings:
            evidence.append("All architectural boundary guardrails passed cleanly.")
            score = 0.0
            sev = "LOW"
            status = "OBSERVED"
        elif has_critical:
            score = 100.0
            sev = "CRITICAL"
            status = "OBSERVED"
        elif violations:
            score = 80.0
            sev = "HIGH"
            status = "OBSERVED"
        else:
            score = 40.0
            sev = "MEDIUM"
            status = "OBSERVED"

        return RiskFactorItem(
            factor_id=RiskFactorType.ARCHITECTURE_DRIFT,
            name="Architecture Conformance",
            score=score,
            weight=1.5,
            severity=sev,
            status=status,
            evidence=evidence,
            details={"violations_count": len(violations), "warnings_count": len(warnings)},
            description="Evaluates changes against architectural layers, forbidden dependencies, and boundaries.",
        ), unknowns

    # -------------------------------------------------------------------------
    # FACTOR 5: DEPENDENCY COUPLING
    # -------------------------------------------------------------------------
    def _compute_coupling_factor(
        self,
        changed_ids: Set[str],
        relationships: List[ArtifactRelationship],
        art_map: Dict[str, StructuralArtifact],
    ) -> RiskFactorItem:
        if not changed_ids:
            return RiskFactorItem(
                factor_id=RiskFactorType.DEPENDENCY_COUPLING,
                name="Dependency Coupling",
                score=0.0,
                weight=1.0,
                severity="LOW",
                status="NOT_APPLICABLE",
                evidence=["No changed entities to evaluate coupling."],
                details={"max_fan_in": 0, "max_fan_out": 0},
                description="Measures in-degree (hub centrality) and out-degree of modified entities.",
            )

        # In-degree: how many other entities depend on / call changed entities
        in_degrees: Dict[str, Set[str]] = {}
        # Out-degree: how many dependencies changed entities rely on
        out_degrees: Dict[str, Set[str]] = {}

        for r in relationships:
            if r.relationship_type in {"CALLS", "IMPORTS", "DEPENDS_ON", "EXTENDS", "IMPLEMENTS"}:
                if r.target_artifact_id in changed_ids:
                    in_degrees.setdefault(r.target_artifact_id, set()).add(r.source_artifact_id)
                if r.source_artifact_id in changed_ids:
                    out_degrees.setdefault(r.source_artifact_id, set()).add(r.target_artifact_id)

        max_fan_in = max([len(s) for s in in_degrees.values()], default=0)
        max_fan_out = max([len(s) for s in out_degrees.values()], default=0)

        evidence = [
            f"Maximum caller fan-in (in-degree): {max_fan_in} dependent caller(s)",
            f"Maximum dependency fan-out (out-degree): {max_fan_out} outbound dependency/dependencies",
        ]

        # Highlight top hub symbols
        for cid, callers in in_degrees.items():
            if len(callers) >= 3 and cid in art_map:
                art = art_map[cid]
                evidence.append(f"Hub node '{art.qualified_name}' is consumed by {len(callers)} dependent components.")

        if max_fan_in <= 2 and max_fan_out <= 4:
            score = 15.0 if (max_fan_in > 0 or max_fan_out > 0) else 0.0
            sev = "LOW"
        elif max_fan_in <= 5:
            score = 50.0
            sev = "MEDIUM"
        else:
            score = 85.0
            sev = "HIGH"

        return RiskFactorItem(
            factor_id=RiskFactorType.DEPENDENCY_COUPLING,
            name="Dependency Coupling",
            score=score,
            weight=1.0,
            severity=sev,
            status="OBSERVED",
            evidence=evidence,
            details={"max_fan_in": max_fan_in, "max_fan_out": max_fan_out},
            description="Evaluates hub centrality: highly depended-on entities amplify risk when modified.",
        )

    # -------------------------------------------------------------------------
    # FACTOR 6: RUNTIME ACTIVITY
    # -------------------------------------------------------------------------
    def _compute_runtime_factor(self, events: List[RuntimeEvent], changes: List[Any]) -> Tuple[RiskFactorItem, List[str]]:
        unknowns = []
        if not events:
            msg = "Runtime evidence unavailable: No runtime events observed for affected components."
            unknowns.append(msg)
            return RiskFactorItem(
                factor_id=RiskFactorType.RUNTIME_ACTIVITY,
                name="Runtime Activity",
                score=0.0,
                weight=1.0,
                severity="LOW",
                status="UNKNOWN",
                evidence=[msg],
                details={"event_count": 0, "status": "UNKNOWN"},
                description="Correlates real production execution traces and activity with modified components.",
            ), unknowns

        prod_events = [e for e in events if e.environment and e.environment.lower() == "production"]
        error_events = [e for e in events if e.severity and e.severity.lower() in ("error", "critical")]

        evidence = [
            f"{len(events)} correlated runtime event(s) observed for affected components.",
            f"{len(prod_events)} production event(s), {len(error_events)} error/critical severity event(s).",
        ]
        if events:
            latest = events[0]
            evidence.append(f"Most recent runtime event: {latest.event_type} on {latest.service_name} at {latest.timestamp.isoformat() if latest.timestamp else 'unknown'}")

        if error_events:
            score = 90.0
            sev = "CRITICAL"
        elif prod_events:
            score = 70.0
            sev = "HIGH"
        else:
            score = 40.0
            sev = "MEDIUM"

        return RiskFactorItem(
            factor_id=RiskFactorType.RUNTIME_ACTIVITY,
            name="Runtime Activity",
            score=score,
            weight=1.0,
            severity=sev,
            status="OBSERVED",
            evidence=evidence,
            details={"total_events": len(events), "prod_events": len(prod_events), "error_events": len(error_events)},
            description="Identifies whether changed code actively serves live traffic or experiences errors in production.",
        ), unknowns

    # -------------------------------------------------------------------------
    # FACTOR 7: INCIDENT HISTORY
    # -------------------------------------------------------------------------
    def _compute_incident_factor(
        self,
        incidents: List[Incident],
        changes: List[Any],
        art_map: Dict[str, StructuralArtifact],
    ) -> RiskFactorItem:
        if not incidents:
            return RiskFactorItem(
                factor_id=RiskFactorType.INCIDENT_HISTORY,
                name="Incident History",
                score=0.0,
                weight=1.0,
                severity="LOW",
                status="NOT_APPLICABLE",
                evidence=["No related incidents recorded for affected components."],
                details={"incident_count": 0},
                description="Checks past operational outages and incident linkages for modified components.",
            )

        evidence = [f"{len(incidents)} past operational incident(s) linked to affected components:"]
        has_critical = False
        for inc in incidents[:4]:
            sev_str = (inc.severity or "medium").upper()
            if sev_str == "CRITICAL":
                has_critical = True
            c_name = getattr(inc, "affected_component_name", None) or (art_map[inc.affected_component_id].name if inc.affected_component_id and inc.affected_component_id in art_map else "Component")
            evidence.append(f"• '{inc.title}' [{sev_str}] on {c_name}")

        if has_critical:
            score = 90.0
            sev = "CRITICAL"
        else:
            score = 60.0
            sev = "HIGH"

        return RiskFactorItem(
            factor_id=RiskFactorType.INCIDENT_HISTORY,
            name="Incident History",
            score=score,
            weight=1.0,
            severity=sev,
            status="OBSERVED",
            evidence=evidence,
            details={"incident_count": len(incidents), "has_critical": has_critical},
            description="Checks past operational outages and incident linkages for modified components.",
        )

    # -------------------------------------------------------------------------
    # FACTOR 8: API SURFACE
    # -------------------------------------------------------------------------
    def _compute_api_surface_factor(
        self,
        changes: List[Any],
        impact_res: ImpactResult,
        art_map: Dict[str, StructuralArtifact],
        relationships: List[ArtifactRelationship],
    ) -> Tuple[RiskFactorItem, List[str]]:
        affected_apis: List[str] = []
        direct_api_changes = []

        # Check directly changed artifacts
        for c in changes:
            if c.artifact_type in ("API_ENDPOINT", "ROUTE", "CONTROLLER") or "api" in c.source_file.lower():
                direct_api_changes.append(c.symbol_name or c.qualified_name)
                affected_apis.append(c.symbol_name or c.qualified_name)

        # Check downstream impacted artifacts
        for f in impact_res.findings:
            if f.target_type in ("API_ENDPOINT", "ROUTE", "CONTROLLER"):
                if f.target_qual_name not in affected_apis:
                    affected_apis.append(f.target_qual_name)

        # Check EXPOSES relationships connected to changed/impacted nodes
        changed_ids = {c.artifact_id for c in changes if c.artifact_id}
        for r in relationships:
            if r.relationship_type in ("EXPOSES", "CONSUMES"):
                if r.source_artifact_id in changed_ids or r.target_artifact_id in changed_ids:
                    target_art = art_map.get(r.target_artifact_id)
                    if target_art and target_art.qualified_name not in affected_apis:
                        affected_apis.append(target_art.qualified_name)

        affected_apis = list(set(affected_apis))

        if direct_api_changes:
            score = 85.0
            sev = "HIGH"
            evidence = [
                f"Directly modified API endpoint / surface: {', '.join(direct_api_changes)}",
                f"Total affected API surface count: {len(affected_apis)}",
            ]
        elif affected_apis:
            score = 50.0
            sev = "MEDIUM"
            evidence = [
                f"Downstream API surface potentially affected: {', '.join(affected_apis[:5])}",
                f"Total affected API count: {len(affected_apis)}",
            ]
        else:
            score = 0.0
            sev = "LOW"
            evidence = ["No public API endpoints or contracts affected by this change."]

        return RiskFactorItem(
            factor_id=RiskFactorType.API_SURFACE,
            name="API Surface Impact",
            score=score,
            weight=1.2,
            severity=sev,
            status="OBSERVED" if affected_apis else "NOT_APPLICABLE",
            evidence=evidence,
            details={"direct_apis": direct_api_changes, "total_apis": len(affected_apis)},
            description="Detects whether public API contracts, endpoints, or network entrypoints are modified.",
        ), affected_apis

    # -------------------------------------------------------------------------
    # FACTOR 9: UNKNOWN EVIDENCE
    # -------------------------------------------------------------------------
    def _compute_unknown_evidence_factor(self, unknown_signals: List[str]) -> RiskFactorItem:
        if not unknown_signals:
            return RiskFactorItem(
                factor_id=RiskFactorType.UNKNOWN_EVIDENCE,
                name="Evidence Completeness",
                score=0.0,
                weight=0.6,
                severity="LOW",
                status="OBSERVED",
                evidence=["High evidence completeness: All relevant test, architecture, and telemetry signals observed."],
                details={"unknown_count": 0},
                description="Highlights epistemic gaps where missing tests or telemetry prevent conclusive assessment.",
            )

        evidence = [f"{len(unknown_signals)} epistemic gap(s) or unobserved evidence item(s):"]
        for u in unknown_signals:
            evidence.append(f"• {u}")

        score = min(100.0, len(unknown_signals) * 25.0)
        sev = "HIGH" if score >= 60.0 else "MEDIUM"

        return RiskFactorItem(
            factor_id=RiskFactorType.UNKNOWN_EVIDENCE,
            name="Evidence Completeness",
            score=score,
            weight=0.6,
            severity=sev,
            status="DERIVED",
            evidence=evidence,
            details={"unknown_count": len(unknown_signals)},
            description="Highlights epistemic gaps where missing tests or telemetry prevent conclusive assessment.",
        )

    # -------------------------------------------------------------------------
    # CATEGORY, CONFIDENCE & EXPLANATION DERIVATION
    # -------------------------------------------------------------------------
    def _derive_overall_category(
        self,
        risk_factors: List[RiskFactorItem],
        guardrail_results: List[GuardrailResult],
        f_breadth: RiskFactorItem,
        f_runtime: RiskFactorItem,
        changes_count: int = 1,
    ) -> Tuple[RiskCategory, float]:
        """
        Derives transparent RiskCategory from explicit deterministic rules and weighted composite score.
        """
        if changes_count == 0:
            return RiskCategory.LOW, 0.0

        active_factors = [f for f in risk_factors if f.status != "NOT_APPLICABLE"]
        if not active_factors:
            return RiskCategory.LOW, 0.0

        total_weight = sum(f.weight for f in active_factors)
        weighted_score = sum(f.score * f.weight for f in active_factors) / total_weight if total_weight > 0 else 0.0

        # Deterministic override rules based on evidence
        has_critical_guardrail = any(
            g.status == GuardrailStatus.VIOLATION and g.severity == GuardrailSeverity.CRITICAL
            for g in guardrail_results
        )
        has_guardrail_violation = any(g.status == GuardrailStatus.VIOLATION for g in guardrail_results)
        is_broad_and_live = (f_breadth.score >= 70.0 and f_runtime.score >= 70.0)

        if has_critical_guardrail or weighted_score >= 75.0 or (is_broad_and_live and has_guardrail_violation):
            category = RiskCategory.CRITICAL
        elif has_guardrail_violation or weighted_score >= 50.0 or is_broad_and_live or f_breadth.score >= 75.0:
            category = RiskCategory.HIGH
        elif weighted_score >= 25.0 or f_breadth.score >= 40.0:
            category = RiskCategory.MODERATE
        else:
            category = RiskCategory.LOW

        return category, weighted_score

    def _derive_confidence(
        self,
        unknown_signals: List[str],
        test_res: Optional[TestImpactResult],
        runtime_events: List[RuntimeEvent],
    ) -> Tuple[ConfidenceLevel, float]:
        """
        Computes Confidence based strictly on completeness and reliability of available evidence.
        Never combines confidence with risk into a single score.
        """
        score = 1.0

        # Penalty for missing tests or test impact failure
        if test_res is None:
            score -= 0.40
        elif test_res.summary.total_tests_mapped == 0:
            score -= 0.35
        elif test_res.summary.unknown_coverage_count > 0:
            score -= min(0.30, test_res.summary.unknown_coverage_count * 0.10)

        # Penalty for unavailable runtime telemetry
        if not runtime_events:
            score -= 0.20

        # Penalty for each other unknown signal
        other_unknowns = [u for u in unknown_signals if "test" not in u.lower() and "runtime" not in u.lower()]
        score -= min(0.20, len(other_unknowns) * 0.10)

        score = max(0.1, min(1.0, score))

        if score >= 0.80:
            level = ConfidenceLevel.HIGH
        elif score >= 0.50:
            level = ConfidenceLevel.MEDIUM
        else:
            level = ConfidenceLevel.LOW

        return level, score

    def _generate_explanation_and_recommendations(
        self,
        overall_category: RiskCategory,
        confidence_level: ConfidenceLevel,
        risk_factors: List[RiskFactorItem],
        guardrail_results: List[GuardrailResult],
        unknown_signals: List[str],
        changes_count: int,
    ) -> Tuple[str, List[str]]:
        """
        Synthesizes an explainable natural language rationale citing exact contributing facts.
        Zero LLM hallucination. Pure deterministic provenance.
        """
        reasons: List[str] = []
        recommendations: List[str] = []

        # Collect high and critical drivers
        high_drivers = [f for f in risk_factors if f.severity in ("HIGH", "CRITICAL") and f.factor_id != RiskFactorType.UNKNOWN_EVIDENCE]
        medium_drivers = [f for f in risk_factors if f.severity == "MEDIUM" and f.factor_id != RiskFactorType.UNKNOWN_EVIDENCE]

        if high_drivers:
            reasons.append(f"significant factors ({', '.join(f.name.lower() for f in high_drivers)})")
        elif medium_drivers:
            reasons.append(f"moderate factors ({', '.join(f.name.lower() for f in medium_drivers)})")
        else:
            reasons.append("isolated scope and zero detected architectural drift")

        # Mention architecture violations specifically
        violations = [g for g in guardrail_results if g.status == GuardrailStatus.VIOLATION]
        if violations:
            reasons.append(f"{len(violations)} architecture guardrail violation(s)")
            recommendations.append("Resolve architectural boundary violations before merging into release branch.")

        # Mention test impact
        f_test = next((f for f in risk_factors if f.factor_id == RiskFactorType.TEST_IMPACT), None)
        if f_test and f_test.details.get("potentially_affected", 0) > 0:
            reasons.append(f"{f_test.details['potentially_affected']} potentially affected test(s)")
            recommendations.append("Execute mandatory directly affected tests and verify regression test suites.")

        if f_test and f_test.details.get("unknown_coverage", 0) > 0:
            recommendations.append(f"Add test assertions for {f_test.details['unknown_coverage']} modified entity/entities lacking coverage.")

        # Mention runtime evidence
        f_runtime = next((f for f in risk_factors if f.factor_id == RiskFactorType.RUNTIME_ACTIVITY), None)
        if f_runtime and f_runtime.status == "OBSERVED" and f_runtime.score >= 50.0:
            reasons.append("active production runtime traffic")
            recommendations.append("Ensure deployment uses canary rollout or staging validation due to active production traffic.")

        # Mention incidents
        f_inc = next((f for f in risk_factors if f.factor_id == RiskFactorType.INCIDENT_HISTORY), None)
        if f_inc and f_inc.status == "OBSERVED" and f_inc.score > 0:
            reasons.append(f"{f_inc.details.get('incident_count', 1)} linked historical incident(s)")
            recommendations.append("Review historical incident postmortems for affected components before shipping.")

        explanation = f"{overall_category.value} — based on {', '.join(reasons)}."
        if unknown_signals:
            explanation += f" Note: {len(unknown_signals)} evidence signal(s) unobserved; assessment confidence is {confidence_level.value}."

        if not recommendations:
            recommendations.append("Standard review and automated continuous integration pipeline execution.")

        return explanation, recommendations


risk_intelligence_engine = RiskIntelligenceEngine()
