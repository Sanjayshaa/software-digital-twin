"""
Phase 7 — Architecture Guardrail Evaluator.
Evaluates code changes and snapshot relationships against architectural rules and boundaries:
- FORBIDDEN_DEPENDENCY
- LAYER_VIOLATION
- BOUNDARY_VIOLATION
- CIRCULAR_DEPENDENCY
- UNEXPECTED_EXTERNAL_DEPENDENCY
- UNEXPECTED_COUPLING
- ARCHITECTURE_BYPASS
Zero LLM dependencies. 100% deterministic graph evaluation.
"""

import os
import yaml
import hashlib
from typing import List, Dict, Set, Optional, Tuple, Any
from sqlalchemy.orm import Session
import networkx as nx

from app.models.entities import StructuralArtifact, ArtifactRelationship, RepositorySnapshot
from app.services.architecture.drift_detector import architecture_drift_detector
from app.services.architecture.models import ArchitectureBaseline, BaselineRule, BaselineLayer
from app.services.risk.models import (
    GuardrailResult,
    GuardrailStatus,
    GuardrailSeverity,
    GuardrailType,
)

DEFAULT_BASELINE_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "docs", "architecture-baseline.yaml")
)


class ArchitectureGuardrailEvaluator:
    """
    Evaluates architecture guardrails deterministically for a target snapshot,
    specifically highlighting guardrails relevant to or violated by the changed entities.
    """

    def __init__(self, baseline_path: Optional[str] = None):
        self.baseline_path = baseline_path or DEFAULT_BASELINE_PATH

    def evaluate_guardrails(
        self,
        db: Session,
        repository_id: str,
        snapshot_id: str,
        changed_artifact_ids: Optional[Set[str]] = None,
        impacted_artifact_ids: Optional[Set[str]] = None,
        baseline_path: Optional[str] = None,
        artifacts: Optional[List[StructuralArtifact]] = None,
        relationships: Optional[List[ArtifactRelationship]] = None,
    ) -> List[GuardrailResult]:
        """
        Evaluates architecture rules and produces structured GuardrailResult items.
        If baseline is missing or cannot be loaded, returns an UNKNOWN guardrail result.
        """
        target_path = baseline_path or self.baseline_path
        if not target_path or not os.path.exists(target_path):
            return [
                GuardrailResult(
                    rule_id="GUARD-UNKNOWN",
                    rule_name="Architecture Baseline Status",
                    guardrail_type=GuardrailType.BOUNDARY_VIOLATION,
                    status=GuardrailStatus.UNKNOWN,
                    severity=GuardrailSeverity.MEDIUM,
                    affected_entities=[],
                    source="system",
                    target=None,
                    evidence=["Architecture baseline specification YAML file not found or not configured."],
                    explanation="Architecture status unknown: No machine-readable baseline defined for repository.",
                )
            ]

        try:
            baseline = architecture_drift_detector.load_baseline(target_path)
        except Exception as e:
            return [
                GuardrailResult(
                    rule_id="GUARD-ERROR",
                    rule_name="Architecture Baseline Loading",
                    guardrail_type=GuardrailType.BOUNDARY_VIOLATION,
                    status=GuardrailStatus.UNKNOWN,
                    severity=GuardrailSeverity.MEDIUM,
                    affected_entities=[],
                    source="system",
                    target=None,
                    evidence=[f"Failed to parse architecture baseline: {str(e)}"],
                    explanation="Architecture status unknown: Baseline configuration could not be loaded.",
                )
            ]

        # Load artifacts and relationships for snapshot (or use in-memory collections)
        if artifacts is None:
            artifacts = db.query(StructuralArtifact).filter_by(snapshot_id=snapshot_id).all()
        if relationships is None:
            relationships = db.query(ArtifactRelationship).filter_by(snapshot_id=snapshot_id).all()

        art_map = {a.id: a for a in artifacts}
        qual_to_art = {a.qualified_name: a for a in artifacts}

        relevant_art_ids = set()
        if changed_artifact_ids:
            relevant_art_ids.update(changed_artifact_ids)
        if impacted_artifact_ids:
            relevant_art_ids.update(impacted_artifact_ids)

        guardrail_results: List[GuardrailResult] = []

        # 1. Evaluate Explicit Baseline Rules
        for rule in baseline.rules:
            res = self._evaluate_single_rule(
                rule=rule,
                baseline=baseline,
                artifacts=artifacts,
                relationships=relationships,
                art_map=art_map,
                relevant_art_ids=relevant_art_ids,
            )
            if res:
                guardrail_results.append(res)

        # 2. Evaluate Layer Definitions for Forbidden Cross-Layer Dependencies
        layer_results = self._evaluate_layer_boundaries(
            baseline=baseline,
            relationships=relationships,
            art_map=art_map,
            relevant_art_ids=relevant_art_ids,
        )
        guardrail_results.extend(layer_results)

        # 3. Evaluate Unexpected High Coupling Guardrail
        coupling_res = self._evaluate_unexpected_coupling(
            artifacts=artifacts,
            relationships=relationships,
            art_map=art_map,
            changed_artifact_ids=changed_artifact_ids,
        )
        if coupling_res:
            guardrail_results.append(coupling_res)

        # 4. Evaluate Circular Dependencies
        cycle_res = self._evaluate_circular_dependencies(
            relationships=relationships,
            art_map=art_map,
            relevant_art_ids=relevant_art_ids,
        )
        if cycle_res:
            guardrail_results.append(cycle_res)

        return guardrail_results

    def _evaluate_single_rule(
        self,
        rule: BaselineRule,
        baseline: ArchitectureBaseline,
        artifacts: List[StructuralArtifact],
        relationships: List[ArtifactRelationship],
        art_map: Dict[str, StructuralArtifact],
        relevant_art_ids: Set[str],
    ) -> Optional[GuardrailResult]:
        """Evaluates an explicit rule from baseline.rules."""
        category_str = rule.category.upper() if isinstance(rule.category, str) else rule.category.name
        rule_type = self._map_category_to_guardrail_type(category_str)

        # External prohibited imports (e.g. Rule-06)
        if rule.forbidden_imports:
            violating_rels = []
            for rel in relationships:
                if rel.relationship_type in {"IMPORTS", "REFERENCES"}:
                    target_name = ""
                    if rel.target_artifact:
                        target_name = rel.target_artifact.qualified_name
                    elif rel.target_artifact_id in art_map:
                        target_name = art_map[rel.target_artifact_id].qualified_name

                    for prohibited in rule.forbidden_imports:
                        if target_name == prohibited or target_name.startswith(f"{prohibited}."):
                            violating_rels.append((rel, target_name))

            if violating_rels:
                affected = []
                evidence = []
                is_touched_by_change = False
                for r, tgt in violating_rels:
                    src_art = art_map.get(r.source_artifact_id)
                    src_name = src_art.qualified_name if src_art else "Unknown"
                    loc = r.source_location or (src_art.location if src_art else "unknown:1")
                    affected.append(src_name)
                    evidence.append(f"Prohibited import of '{tgt}' in {src_name} ({loc})")
                    if relevant_art_ids and (r.source_artifact_id in relevant_art_ids or r.target_artifact_id in relevant_art_ids):
                        is_touched_by_change = True

                sev = GuardrailSeverity.CRITICAL if rule.severity == "CRITICAL" else GuardrailSeverity.HIGH
                status = GuardrailStatus.VIOLATION
                explanation = f"Detected prohibited external dependency import violating {rule.name}."
                if is_touched_by_change:
                    explanation += " This violation directly involves code modified or impacted by the change."

                return GuardrailResult(
                    rule_id=rule.id,
                    rule_name=rule.name,
                    guardrail_type=GuardrailType.UNEXPECTED_EXTERNAL_DEPENDENCY,
                    status=status,
                    severity=sev,
                    affected_entities=list(set(affected)),
                    source=rule.source or "codebase",
                    target=", ".join(rule.forbidden_imports),
                    evidence=evidence,
                    explanation=explanation,
                )
            else:
                return GuardrailResult(
                    rule_id=rule.id,
                    rule_name=rule.name,
                    guardrail_type=GuardrailType.UNEXPECTED_EXTERNAL_DEPENDENCY,
                    status=GuardrailStatus.PASS,
                    severity=GuardrailSeverity.INFO,
                    affected_entities=[],
                    source=rule.source or "codebase",
                    target=", ".join(rule.forbidden_imports),
                    evidence=[f"No prohibited imports of {rule.forbidden_imports} detected."],
                    explanation=f"Passed: Zero prohibited external imports violating {rule.name}.",
                )

        # Source -> Target forbidden dependency rules
        if rule.source and rule.target and rule.forbidden:
            violating_rels = []
            for rel in relationships:
                src_art = art_map.get(rel.source_artifact_id)
                tgt_art = art_map.get(rel.target_artifact_id)
                if not src_art or not tgt_art:
                    continue

                src_qual = src_art.qualified_name
                tgt_qual = tgt_art.qualified_name

                if (src_qual == rule.source or src_qual.startswith(f"{rule.source}.")) and (
                    tgt_qual == rule.target or tgt_qual.startswith(f"{rule.target}.")
                ):
                    violating_rels.append((rel, src_qual, tgt_qual))

            if violating_rels:
                affected = []
                evidence = []
                is_touched = False
                for r, s, t in violating_rels:
                    loc = r.source_location or (art_map[r.source_artifact_id].location if r.source_artifact_id in art_map else "unknown:1")
                    affected.extend([s, t])
                    evidence.append(f"Forbidden {r.relationship_type}: '{s}' -> '{t}' ({loc})")
                    if relevant_art_ids and (r.source_artifact_id in relevant_art_ids or r.target_artifact_id in relevant_art_ids):
                        is_touched = True

                sev = GuardrailSeverity.CRITICAL if rule.severity == "CRITICAL" else GuardrailSeverity.HIGH
                expl = f"Violation of rule '{rule.name}': {rule.description or 'Dependency from source to target is forbidden.'}"
                if is_touched:
                    expl += " This guardrail is breached by the current change."

                return GuardrailResult(
                    rule_id=rule.id,
                    rule_name=rule.name,
                    guardrail_type=rule_type,
                    status=GuardrailStatus.VIOLATION,
                    severity=sev,
                    affected_entities=list(set(affected)),
                    source=rule.source,
                    target=rule.target,
                    evidence=evidence,
                    explanation=expl,
                )
            else:
                return GuardrailResult(
                    rule_id=rule.id,
                    rule_name=rule.name,
                    guardrail_type=rule_type,
                    status=GuardrailStatus.PASS,
                    severity=GuardrailSeverity.INFO,
                    affected_entities=[],
                    source=rule.source,
                    target=rule.target,
                    evidence=[f"No forbidden dependencies observed between '{rule.source}' and '{rule.target}'."],
                    explanation=f"Passed: Conforms to rule '{rule.name}'.",
                )

        return None

    def _evaluate_layer_boundaries(
        self,
        baseline: ArchitectureBaseline,
        relationships: List[ArtifactRelationship],
        art_map: Dict[str, StructuralArtifact],
        relevant_art_ids: Set[str],
    ) -> List[GuardrailResult]:
        """Evaluates layer boundary contracts defined in baseline.layers."""
        results: List[GuardrailResult] = []
        layer_violations: Dict[Tuple[str, str], List[Tuple[ArtifactRelationship, str, str]]] = {}

        for rel in relationships:
            if rel.relationship_type not in {"IMPORTS", "DEPENDS_ON", "CALLS", "REFERENCES", "EXTENDS", "IMPLEMENTS"}:
                continue

            src_art = art_map.get(rel.source_artifact_id)
            tgt_art = art_map.get(rel.target_artifact_id)
            if not src_art or not tgt_art:
                continue

            src_qual = src_art.qualified_name
            tgt_qual = tgt_art.qualified_name

            src_layer = architecture_drift_detector._resolve_layer(src_art.location.split(":")[0], baseline) or architecture_drift_detector._resolve_layer(src_qual, baseline)
            tgt_layer = architecture_drift_detector._resolve_layer(tgt_art.location.split(":")[0], baseline) or architecture_drift_detector._resolve_layer(tgt_qual, baseline)

            if src_layer and tgt_layer and src_layer != tgt_layer:
                layer_def = baseline.layers.get(src_layer)
                if layer_def:
                    is_forbidden = False
                    if any(tgt_layer == fb or tgt_qual.startswith(fb) for fb in layer_def.forbidden_dependencies):
                        is_forbidden = True
                    elif layer_def.allowed_dependencies and tgt_layer not in layer_def.allowed_dependencies:
                        is_forbidden = True

                    if is_forbidden:
                        layer_violations.setdefault((src_layer, tgt_layer), []).append((rel, src_qual, tgt_qual))

        for (src_layer, tgt_layer), items in layer_violations.items():
            affected = []
            evidence = []
            is_touched = False
            for r, sq, tq in items:
                loc = r.source_location or "unknown:1"
                affected.extend([sq, tq])
                evidence.append(f"Forbidden cross-layer {r.relationship_type} from {src_layer} to {tgt_layer}: {sq} -> {tq} ({loc})")
                if relevant_art_ids and (r.source_artifact_id in relevant_art_ids or r.target_artifact_id in relevant_art_ids):
                    is_touched = True

            rule_id = f"GUARD-LAYER-{src_layer.upper()}-{tgt_layer.upper()}"
            expl = f"Layer boundary violation: Code in layer '{src_layer}' directly depends on forbidden layer '{tgt_layer}'."
            if is_touched:
                expl += " Directly involved in current change set."

            results.append(
                GuardrailResult(
                    rule_id=rule_id,
                    rule_name=f"Layer Boundary ({src_layer} -> {tgt_layer})",
                    guardrail_type=GuardrailType.LAYER_VIOLATION,
                    status=GuardrailStatus.VIOLATION,
                    severity=GuardrailSeverity.HIGH,
                    affected_entities=list(set(affected)),
                    source=src_layer,
                    target=tgt_layer,
                    evidence=evidence[:10],
                    explanation=expl,
                )
            )

        return results

    def _evaluate_unexpected_coupling(
        self,
        artifacts: List[StructuralArtifact],
        relationships: List[ArtifactRelationship],
        art_map: Dict[str, StructuralArtifact],
        changed_artifact_ids: Optional[Set[str]],
    ) -> Optional[GuardrailResult]:
        """Detects unexpected high fan-out coupling from changed artifacts."""
        if not changed_artifact_ids:
            return None

        # Build out-degrees for changed entities
        out_targets: Dict[str, Set[str]] = {}
        for r in relationships:
            if r.source_artifact_id in changed_artifact_ids:
                tgt_art = art_map.get(r.target_artifact_id)
                if tgt_art:
                    out_targets.setdefault(r.source_artifact_id, set()).add(tgt_art.qualified_name)

        high_fanout = []
        evidence = []
        for art_id, targets in out_targets.items():
            if len(targets) >= 8:  # Significant coupling threshold
                art_name = art_map[art_id].qualified_name if art_id in art_map else art_id
                high_fanout.append(art_name)
                evidence.append(f"Changed entity '{art_name}' has unusually high coupling: {len(targets)} outbound dependencies.")

        if high_fanout:
            return GuardrailResult(
                rule_id="GUARD-COUPLING-01",
                rule_name="Coupling Boundary Guardrail",
                guardrail_type=GuardrailType.UNEXPECTED_COUPLING,
                status=GuardrailStatus.WARN,
                severity=GuardrailSeverity.MEDIUM,
                affected_entities=high_fanout,
                source="changed_entities",
                target=None,
                evidence=evidence,
                explanation="High unexpected coupling detected: modified entities depend on a broad set of downstream modules, increasing systemic blast radius.",
            )
        return None

    def _evaluate_circular_dependencies(
        self,
        relationships: List[ArtifactRelationship],
        art_map: Dict[str, StructuralArtifact],
        relevant_art_ids: Set[str],
    ) -> Optional[GuardrailResult]:
        """Evaluates circular dependencies across structural relationships."""
        dep_graph = nx.DiGraph()
        for r in relationships:
            if r.relationship_type in {"IMPORTS", "DEPENDS_ON", "CALLS", "REFERENCES"}:
                s_art = art_map.get(r.source_artifact_id)
                t_art = art_map.get(r.target_artifact_id)
                if s_art and t_art:
                    dep_graph.add_edge(s_art.qualified_name, t_art.qualified_name)

        try:
            cycles = list(nx.simple_cycles(dep_graph))
            valid_cycles = [c for c in cycles if len(c) > 1]
            if not valid_cycles:
                return GuardrailResult(
                    rule_id="RULE-05",
                    rule_name="Circular Dependency Ban",
                    guardrail_type=GuardrailType.CIRCULAR_DEPENDENCY,
                    status=GuardrailStatus.PASS,
                    severity=GuardrailSeverity.INFO,
                    affected_entities=[],
                    source="codebase",
                    target=None,
                    evidence=["No dependency cycles detected in architecture graph."],
                    explanation="Passed: Architectural graph is an acyclic dependency structure.",
                )

            evidence = []
            affected = []
            is_touched = False
            for c in valid_cycles[:5]:
                c_str = " -> ".join(c) + f" -> {c[0]}"
                evidence.append(f"Dependency cycle: {c_str}")
                affected.extend(c)
                # Check if cycle touches relevant arts
                c_set = set(c)
                for r_id in relevant_art_ids:
                    r_art = art_map.get(r_id)
                    if r_art and r_art.qualified_name in c_set:
                        is_touched = True

            expl = "Critical circular dependency detected violating architectural hierarchy."
            if is_touched:
                expl += " Current change touches components participating in the cycle."

            return GuardrailResult(
                rule_id="RULE-05",
                rule_name="Circular Dependency Ban",
                guardrail_type=GuardrailType.CIRCULAR_DEPENDENCY,
                status=GuardrailStatus.VIOLATION,
                severity=GuardrailSeverity.CRITICAL,
                affected_entities=list(set(affected)),
                source="architecture_graph",
                target=None,
                evidence=evidence,
                explanation=expl,
            )
        except Exception:
            return None

    def _map_category_to_guardrail_type(self, category_str: str) -> GuardrailType:
        try:
            return GuardrailType(category_str)
        except Exception:
            if "LAYER" in category_str:
                return GuardrailType.LAYER_VIOLATION
            if "CIRCULAR" in category_str:
                return GuardrailType.CIRCULAR_DEPENDENCY
            if "EXTERNAL" in category_str:
                return GuardrailType.UNEXPECTED_EXTERNAL_DEPENDENCY
            if "BYPASS" in category_str:
                return GuardrailType.ARCHITECTURE_BYPASS
            if "COUPLING" in category_str:
                return GuardrailType.UNEXPECTED_COUPLING
            return GuardrailType.FORBIDDEN_DEPENDENCY


guardrail_evaluator = ArchitectureGuardrailEvaluator()
