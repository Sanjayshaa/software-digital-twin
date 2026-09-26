import os
import yaml
import uuid
import hashlib
import networkx as nx
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from datetime import datetime

from app.models.entities import (
    StructuralArtifact,
    ArtifactRelationship,
    ArchitectureReportEntity,
    ArchitectureDriftEntity,
    RepositorySnapshot,
)
from app.services.architecture.models import (
    ArchitectureBaseline,
    BaselineLayer,
    BaselineRule,
    ArchitectureDriftItem,
    ArchitectureConformanceReport,
    SnapshotArchitectureComparison,
)

DEFAULT_BASELINE_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "docs", "architecture-baseline.yaml")
)


class ArchitectureDriftDetector:
    """
    Deterministic Architecture Drift & Boundary Conformance Engine.
    Detects when actual implementation differs from intended architecture.
    Zero LLM dependencies.
    """

    def load_baseline(self, baseline_path: Optional[str] = None) -> ArchitectureBaseline:
        path = baseline_path or DEFAULT_BASELINE_PATH
        if not os.path.exists(path):
            raise FileNotFoundError(f"Architecture baseline YAML not found at: {path}")

        with open(path, "r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}

        layers: Dict[str, BaselineLayer] = {}
        for l_key, l_val in raw.get("layers", {}).items():
            layers[l_key] = BaselineLayer(
                name=l_key,
                description=l_val.get("description", ""),
                modules=l_val.get("modules", []),
                allowed_dependencies=l_val.get("allowed_dependencies", []),
                forbidden_dependencies=l_val.get("forbidden_dependencies", []),
            )

        rules: List[BaselineRule] = []
        for r_val in raw.get("rules", []):
            rules.append(BaselineRule(
                id=r_val.get("id", str(uuid.uuid4())[:8]),
                name=r_val.get("name", ""),
                category=r_val.get("category", "LAYER_VIOLATION"),
                severity=r_val.get("severity", "HIGH"),
                source=r_val.get("source"),
                target=r_val.get("target"),
                forbidden=r_val.get("forbidden", True),
                forbidden_imports=r_val.get("forbidden_imports", []),
                description=r_val.get("description", ""),
            ))

        return ArchitectureBaseline(
            version=raw.get("version", "1.0.0"),
            project=raw.get("project", ""),
            description=raw.get("description", ""),
            layers=layers,
            rules=rules,
        )

    def _resolve_layer(self, module_name: str, baseline: ArchitectureBaseline) -> Optional[str]:
        """Resolves a module string or file path to its architectural layer."""
        clean = module_name.replace("/", ".").replace("\\", ".").strip(".")
        # Strip common prefixes
        for prefix in ["backend.", "src.", "services."]:
            if clean.startswith(prefix):
                clean = clean[len(prefix):]

        best_layer: Optional[str] = None
        best_len = 0

        for layer_name, layer in baseline.layers.items():
            # Direct match by layer name
            if clean == layer_name or clean.startswith(f"{layer_name}."):
                if len(layer_name) > best_len:
                    best_layer = layer_name
                    best_len = len(layer_name)

            for pattern in layer.modules:
                pattern_clean = pattern.strip(".")
                if clean == pattern_clean or clean.startswith(f"{pattern_clean}."):
                    if len(pattern_clean) > best_len:
                        best_layer = layer_name
                        best_len = len(pattern_clean)

        return best_layer

    def detect_drift_for_snapshot(
        self,
        db: Session,
        repository_id: str,
        snapshot_id: str,
        baseline_path: Optional[str] = None,
        persist: bool = True,
    ) -> ArchitectureConformanceReport:
        """
        Executes deterministic drift analysis on a given repository snapshot.
        """
        baseline = self.load_baseline(baseline_path)

        artifacts = db.query(StructuralArtifact).filter_by(snapshot_id=snapshot_id).all()
        relationships = db.query(ArtifactRelationship).filter_by(snapshot_id=snapshot_id).all()

        art_map = {a.id: a for a in artifacts}
        qual_to_art = {a.qualified_name: a for a in artifacts}

        # Build module-level dependency graph
        dep_graph = nx.DiGraph()
        edge_evidence_map: Dict[Tuple[str, str], List[ArtifactRelationship]] = {}

        drifts: List[ArchitectureDriftItem] = []
        validated_boundaries = 0
        violations_count = 0
        circular_count = 0
        unexpected_count = 0

        # 1. Inspect Explicit Prohibited External Imports (Rule-06 style)
        for rule in baseline.rules:
            if rule.forbidden_imports:
                for rel in relationships:
                    if rel.relationship_type in {"IMPORTS", "REFERENCES"}:
                        target_qual = rel.target_artifact.qualified_name if rel.target_artifact else ""
                        for prohibited in rule.forbidden_imports:
                            if target_qual == prohibited or target_qual.startswith(f"{prohibited}."):
                                src_art = art_map.get(rel.source_artifact_id)
                                src_name = src_art.qualified_name if src_art else "Unknown"
                                file_loc = rel.source_location or (src_art.location if src_art else "unknown:1")
                                parts = file_loc.split(":")
                                f_path = parts[0]
                                f_line = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1

                                drift_id = f"drift_{hashlib.sha256(f'{snapshot_id}:{src_name}:{target_qual}:{rule.id}'.encode('utf-8')).hexdigest()[:16]}"
                                drifts.append(ArchitectureDriftItem(
                                    id=drift_id,
                                    category="UNEXPECTED_EXTERNAL_DEPENDENCY",
                                    severity=rule.severity,
                                    source=src_name,
                                    target=target_qual,
                                    relationship_type=rel.relationship_type,
                                    expected_rule=rule.description or f"Prohibited vendor import: {prohibited}",
                                    actual_evidence=f"Direct import of '{target_qual}' detected in {file_loc}",
                                    file_path=f_path,
                                    line_number=f_line,
                                    confidence=1.0,
                                ))
                                unexpected_count += 1
                                violations_count += 1

        # 2. Inspect Structural Relationships against Layer Boundaries & Rules
        for rel in relationships:
            if rel.relationship_type not in {"IMPORTS", "DEPENDS_ON", "CALLS", "REFERENCES"}:
                continue

            src_art = art_map.get(rel.source_artifact_id)
            tgt_art = art_map.get(rel.target_artifact_id)
            if not src_art or not tgt_art:
                continue

            src_qual = src_art.qualified_name
            tgt_qual = tgt_art.qualified_name

            # Add to module graph for cycle detection
            dep_graph.add_edge(src_qual, tgt_qual)
            edge_evidence_map.setdefault((src_qual, tgt_qual), []).append(rel)

            src_layer = self._resolve_layer(src_art.location.split(":")[0], baseline) or self._resolve_layer(src_qual, baseline)
            tgt_layer = self._resolve_layer(tgt_art.location.split(":")[0], baseline) or self._resolve_layer(tgt_qual, baseline)

            if src_layer and tgt_layer and src_layer != tgt_layer:
                validated_boundaries += 1
                layer_def = baseline.layers.get(src_layer)
                if layer_def:
                    is_forbidden = False
                    reason = ""

                    # Check explicit forbidden
                    if any(tgt_layer == fb or tgt_qual.startswith(fb) for fb in layer_def.forbidden_dependencies):
                        is_forbidden = True
                        reason = f"Layer '{src_layer}' is explicitly forbidden from depending on '{tgt_layer}'"

                    # Check if allowed_dependencies list is defined and tgt_layer not in it
                    elif layer_def.allowed_dependencies and tgt_layer not in layer_def.allowed_dependencies:
                        is_forbidden = True
                        reason = f"Layer '{src_layer}' is not allowed to depend on '{tgt_layer}'. Allowed: {layer_def.allowed_dependencies}"

                    if is_forbidden:
                        parts = (rel.source_location or src_art.location).split(":")
                        f_path = parts[0]
                        f_line = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1

                        drift_id = f"drift_{hashlib.sha256(f'{snapshot_id}:{src_qual}:{tgt_qual}:layer'.encode('utf-8')).hexdigest()[:16]}"
                        drifts.append(ArchitectureDriftItem(
                            id=drift_id,
                            category="LAYER_VIOLATION",
                            severity="HIGH",
                            source=src_qual,
                            target=tgt_qual,
                            relationship_type=rel.relationship_type,
                            expected_rule=reason,
                            actual_evidence=f"Cross-layer {rel.relationship_type} from {src_layer} to {tgt_layer} at {f_path}:{f_line}",
                            file_path=f_path,
                            line_number=f_line,
                            confidence=0.98,
                        ))
                        violations_count += 1

            # Check explicit individual rules
            for rule in baseline.rules:
                if rule.source and rule.target and rule.forbidden:
                    if (src_qual == rule.source or src_qual.startswith(f"{rule.source}.")) and (
                        tgt_qual == rule.target or tgt_qual.startswith(f"{rule.target}.")
                    ):
                        parts = (rel.source_location or src_art.location).split(":")
                        f_path = parts[0]
                        f_line = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1

                        drift_id = f"drift_{hashlib.sha256(f'{snapshot_id}:{src_qual}:{tgt_qual}:{rule.id}'.encode('utf-8')).hexdigest()[:16]}"
                        # Avoid duplicates
                        if not any(d.id == drift_id for d in drifts):
                            drifts.append(ArchitectureDriftItem(
                                id=drift_id,
                                category=rule.category,
                                severity=rule.severity,
                                source=src_qual,
                                target=tgt_qual,
                                relationship_type=rel.relationship_type,
                                expected_rule=rule.description or f"Rule {rule.id} forbids {rule.source} -> {rule.target}",
                                actual_evidence=f"Relationship {rel.relationship_type} violates rule {rule.id} at {f_path}:{f_line}",
                                file_path=f_path,
                                line_number=f_line,
                                confidence=1.0,
                            ))
                            violations_count += 1

        # 3. Detect Circular Dependencies (Rule-05)
        try:
            cycles = list(nx.simple_cycles(dep_graph))
            for cycle in cycles:
                if len(cycle) > 1:
                    cycle_str = " -> ".join(cycle) + f" -> {cycle[0]}"
                    first_node = cycle[0]
                    first_art = qual_to_art.get(first_node)
                    parts = (first_art.location if first_art else "unknown:1").split(":")
                    f_path = parts[0]
                    f_line = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1

                    drift_id = f"drift_{hashlib.sha256(f'{snapshot_id}:cycle:{cycle_str}'.encode('utf-8')).hexdigest()[:16]}"
                    if not any(d.id == drift_id for d in drifts):
                        drifts.append(ArchitectureDriftItem(
                            id=drift_id,
                            category="CIRCULAR_DEPENDENCY",
                            severity="CRITICAL",
                            source=cycle[0],
                            target=cycle[1],
                            relationship_type="CIRCULAR",
                            expected_rule="Circular dependencies are strictly forbidden across module boundaries.",
                            actual_evidence=f"Detected dependency cycle: {cycle_str}",
                            file_path=f_path,
                            line_number=f_line,
                            confidence=1.0,
                        ))
                        circular_count += 1
                        violations_count += 1
        except Exception:
            pass

        # 4. Compute Conformance Metrics
        expected_boundaries = len(baseline.layers) * 3 + len(baseline.rules)
        total_eval = max(validated_boundaries, expected_boundaries)
        if total_eval > 0:
            conformance = max(0.0, round(((total_eval - violations_count) / total_eval) * 100.0, 2))
        else:
            conformance = 100.0

        report_id = f"arch_rep_{hashlib.sha256(f'{repository_id}:{snapshot_id}'.encode('utf-8')).hexdigest()[:16]}"
        summary_text = (
            f"Architecture Conformance: {conformance}%. "
            f"Validated Boundaries: {validated_boundaries}. "
            f"Violations: {violations_count} (Layer: {violations_count - circular_count - unexpected_count}, "
            f"Cycles: {circular_count}, Prohibited Imports: {unexpected_count})."
        )

        report = ArchitectureConformanceReport(
            id=report_id,
            repository_id=repository_id,
            snapshot_id=snapshot_id,
            baseline_version=baseline.version,
            expected_boundaries=expected_boundaries,
            validated_boundaries=validated_boundaries,
            violations_count=violations_count,
            circular_count=circular_count,
            unexpected_count=unexpected_count,
            conformance_percentage=conformance,
            summary=summary_text,
            drifts=drifts,
        )

        # 5. Persist to PostgreSQL if requested
        if persist:
            existing_rep = db.query(ArchitectureReportEntity).filter_by(id=report_id).first()
            if not existing_rep:
                rep_entity = ArchitectureReportEntity(
                    id=report.id,
                    repository_id=repository_id,
                    snapshot_id=snapshot_id,
                    baseline_version=report.baseline_version,
                    expected_boundaries=report.expected_boundaries,
                    validated_boundaries=report.validated_boundaries,
                    violations_count=report.violations_count,
                    circular_count=report.circular_count,
                    unexpected_count=report.unexpected_count,
                    conformance_percentage=report.conformance_percentage,
                    summary=report.summary,
                )
                db.add(rep_entity)
                db.flush()

                for d in drifts:
                    drift_entity = ArchitectureDriftEntity(
                        id=d.id,
                        report_id=rep_entity.id,
                        repository_id=repository_id,
                        snapshot_id=snapshot_id,
                        category=d.category,
                        severity=d.severity,
                        source=d.source,
                        target=d.target,
                        relationship_type=d.relationship_type,
                        expected_rule=d.expected_rule,
                        actual_evidence=d.actual_evidence,
                        file_path=d.file_path,
                        line_number=d.line_number,
                        confidence=d.confidence,
                        status=d.status,
                    )
                    db.add(drift_entity)
                db.commit()
            else:
                existing_rep.conformance_percentage = report.conformance_percentage
                existing_rep.violations_count = report.violations_count
                existing_rep.summary = report.summary
                db.commit()

        return report

    def compare_snapshots(
        self,
        db: Session,
        repository_id: str,
        from_snapshot_id: str,
        to_snapshot_id: str,
        baseline_path: Optional[str] = None,
    ) -> SnapshotArchitectureComparison:
        """Compares architecture states between two snapshots, identifying new vs resolved drifts."""
        report_from = self.detect_drift_for_snapshot(db, repository_id, from_snapshot_id, baseline_path, persist=False)
        report_to = self.detect_drift_for_snapshot(db, repository_id, to_snapshot_id, baseline_path, persist=False)

        from_drifts_by_key = {f"{d.category}:{d.source}:{d.target}": d for d in report_from.drifts}
        to_drifts_by_key = {f"{d.category}:{d.source}:{d.target}": d for d in report_to.drifts}

        new_drifts: List[ArchitectureDriftItem] = []
        persistent_drifts: List[ArchitectureDriftItem] = []
        resolved_drifts: List[ArchitectureDriftItem] = []

        for key, d in to_drifts_by_key.items():
            if key in from_drifts_by_key:
                persistent_drifts.append(d)
            else:
                new_drifts.append(d)

        for key, d in from_drifts_by_key.items():
            if key not in to_drifts_by_key:
                resolved_item = d.model_copy()
                resolved_item.status = "RESOLVED"
                resolved_drifts.append(resolved_item)

        delta = round(report_to.conformance_percentage - report_from.conformance_percentage, 2)
        summary = (
            f"Snapshot {from_snapshot_id[:8]} -> {to_snapshot_id[:8]}: "
            f"Conformance {report_from.conformance_percentage}% -> {report_to.conformance_percentage}% (delta {delta:+.2f}%). "
            f"New Drifts: {len(new_drifts)}, Resolved: {len(resolved_drifts)}, Persistent: {len(persistent_drifts)}."
        )

        return SnapshotArchitectureComparison(
            repository_id=repository_id,
            from_snapshot_id=from_snapshot_id,
            to_snapshot_id=to_snapshot_id,
            conformance_before=report_from.conformance_percentage,
            conformance_after=report_to.conformance_percentage,
            conformance_delta=delta,
            new_drifts=new_drifts,
            resolved_drifts=resolved_drifts,
            persistent_drifts=persistent_drifts,
            summary=summary,
        )


architecture_drift_detector = ArchitectureDriftDetector()
