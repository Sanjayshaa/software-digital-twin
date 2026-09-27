import os
import ast
import yaml
from datetime import datetime
from typing import List, Dict, Tuple, Set, Optional, Any
import networkx as nx

from app.services.architecture.models import (
    ArchitectureBaselineSpec,
    ArchitectureRule,
    ArchitectureDrift,
    ArchitectureConformanceReport,
    DriftCategory,
    DriftSeverity,
    DriftStatus,
    LayerDefinition,
)


class ArchitectureDriftDetector:
    """
    Deterministic, evidence-based architecture drift detector.
    Analyzes concrete repository AST structures, import relationships, and boundary contracts.
    Does NOT guess or hallucinate architectural compliance.
    """

    def __init__(self, baseline_path: Optional[str] = None):
        self.baseline_path = baseline_path
        self._baseline: Optional[ArchitectureBaselineSpec] = None
        if baseline_path and os.path.exists(baseline_path):
            self.load_baseline(baseline_path)

    def load_baseline(self, path: str) -> ArchitectureBaselineSpec:
        """Loads and validates machine-readable architecture baseline YAML."""
        with open(path, "r", encoding="utf-8") as f:
            raw_data = yaml.safe_load(f)

        layers = {}
        for layer_name, layer_data in raw_data.get("layers", {}).items():
            layers[layer_name] = LayerDefinition(
                description=layer_data.get("description"),
                modules=layer_data.get("modules", []),
                allowed_dependencies=layer_data.get("allowed_dependencies", []),
                forbidden_dependencies=layer_data.get("forbidden_dependencies", []),
            )

        rules = []
        for r in raw_data.get("rules", []):
            rules.append(
                ArchitectureRule(
                    id=r.get("id", "RULE-GEN"),
                    name=r.get("name", "Unnamed Rule"),
                    category=DriftCategory(r.get("category", DriftCategory.FORBIDDEN_DEPENDENCY)),
                    severity=DriftSeverity(r.get("severity", DriftSeverity.HIGH)),
                    source=r.get("source"),
                    target=r.get("target"),
                    forbidden=r.get("forbidden", True),
                    forbidden_imports=r.get("forbidden_imports", []),
                    description=r.get("description", ""),
                )
            )

        self._baseline = ArchitectureBaselineSpec(
            version=str(raw_data.get("version", "1.0.0")),
            project=raw_data.get("project", ""),
            description=raw_data.get("description", ""),
            layers=layers,
            rules=rules,
        )
        return self._baseline

    def detect_drift(
        self,
        repository_path: str,
        snapshot_id: Optional[str] = None,
        baseline: Optional[ArchitectureBaselineSpec] = None,
    ) -> ArchitectureConformanceReport:
        """
        Scans a repository codebase, extracts concrete import relationships via AST,
        and evaluates every boundary against the architecture baseline.
        """
        spec = baseline or self._baseline
        if not spec:
            raise ValueError("No architecture baseline provided or loaded.")

        # 1. Parse repository imports
        import_records, file_lines_map = self._extract_imports(repository_path)

        # 2. Build dependency graph for cycle detection and path validation
        dep_graph = nx.DiGraph()
        for rec in import_records:
            dep_graph.add_edge(rec["source_module"], rec["target_module"])

        drifts: List[ArchitectureDrift] = []
        validated_boundaries_count = 0
        expected_boundaries_count = 0

        # Calculate expected boundary checks
        for layer_name, l_def in spec.layers.items():
            expected_boundaries_count += len(l_def.allowed_dependencies)
            expected_boundaries_count += len(l_def.forbidden_dependencies)
        expected_boundaries_count += len(spec.rules)
        expected_boundaries_count = max(expected_boundaries_count, 1)

        # 3. Check Explicit Rules
        for rule in spec.rules:
            validated_boundaries_count += 1
            if rule.forbidden_imports:
                for rec in import_records:
                    target_pkg = rec["target_module"].split(".")[0]
                    if target_pkg in rule.forbidden_imports:
                        drifts.append(
                            ArchitectureDrift(
                                category=rule.category,
                                severity=rule.severity,
                                source=rec["source_module"],
                                target=rec["target_module"],
                                relationship="import",
                                expected_rule=f"{rule.name}: {rule.description}",
                                actual_evidence=f"{rec['relative_file']}:{rec['line']} -> {rec['code_snippet']}",
                                file=rec["relative_file"],
                                line=rec["line"],
                                snapshot=snapshot_id,
                                confidence=0.98,
                                status=DriftStatus.DETECTED,
                            )
                        )

            if rule.source and rule.target and rule.forbidden:
                for rec in import_records:
                    if self._matches_pattern(rec["source_module"], rule.source) and self._matches_pattern(rec["target_module"], rule.target):
                        drifts.append(
                            ArchitectureDrift(
                                category=rule.category,
                                severity=rule.severity,
                                source=rec["source_module"],
                                target=rec["target_module"],
                                relationship="import",
                                expected_rule=f"{rule.name}: {rule.description}",
                                actual_evidence=f"{rec['relative_file']}:{rec['line']} -> {rec['code_snippet']}",
                                file=rec["relative_file"],
                                line=rec["line"],
                                snapshot=snapshot_id,
                                confidence=0.98,
                                status=DriftStatus.DETECTED,
                            )
                        )

        # 4. Check Layer Boundary Definitions
        for rec in import_records:
            source_layer = self._resolve_layer(rec["source_module"], spec.layers)
            target_layer = self._resolve_layer(rec["target_module"], spec.layers)

            if source_layer and target_layer and source_layer != target_layer:
                layer_def = spec.layers.get(source_layer)
                if layer_def:
                    # Check forbidden list
                    if target_layer in layer_def.forbidden_dependencies or any(
                        self._matches_pattern(rec["target_module"], forbidden) for forbidden in layer_def.forbidden_dependencies
                    ):
                        drifts.append(
                            ArchitectureDrift(
                                category=DriftCategory.FORBIDDEN_DEPENDENCY,
                                severity=DriftSeverity.HIGH,
                                source=rec["source_module"],
                                target=rec["target_module"],
                                relationship="import",
                                expected_rule=f"Layer '{source_layer}' is strictly forbidden from depending on '{target_layer}'.",
                                actual_evidence=f"{rec['relative_file']}:{rec['line']} -> {rec['code_snippet']}",
                                file=rec["relative_file"],
                                line=rec["line"],
                                snapshot=snapshot_id,
                                confidence=0.98,
                                status=DriftStatus.DETECTED,
                            )
                        )
                    # Check allowed list (if explicitly constrained)
                    elif layer_def.allowed_dependencies and not (
                        target_layer in layer_def.allowed_dependencies or any(
                            self._matches_pattern(rec["target_module"], allowed) for allowed in layer_def.allowed_dependencies
                        )
                    ):
                        drifts.append(
                            ArchitectureDrift(
                                category=DriftCategory.LAYER_VIOLATION,
                                severity=DriftSeverity.MEDIUM,
                                source=rec["source_module"],
                                target=rec["target_module"],
                                relationship="import",
                                expected_rule=f"Layer '{source_layer}' may only depend on {layer_def.allowed_dependencies}; target '{target_layer}' is not permitted.",
                                actual_evidence=f"{rec['relative_file']}:{rec['line']} -> {rec['code_snippet']}",
                                file=rec["relative_file"],
                                line=rec["line"],
                                snapshot=snapshot_id,
                                confidence=0.95,
                                status=DriftStatus.DETECTED,
                            )
                        )

        # 5. Check Circular Dependencies
        cycles = list(nx.simple_cycles(dep_graph))
        circular_count = len(cycles)
        for cycle in cycles:
            cycle_str = " -> ".join(cycle) + f" -> {cycle[0]}"
            # Find representative import for cycle
            first_src = cycle[0]
            first_target = cycle[1] if len(cycle) > 1 else cycle[0]
            matching_rec = next(
                (r for r in import_records if r["source_module"] == first_src and r["target_module"].startswith(first_target)),
                {"relative_file": "module", "line": 1, "code_snippet": cycle_str}
            )
            drifts.append(
                ArchitectureDrift(
                    category=DriftCategory.CIRCULAR_DEPENDENCY,
                    severity=DriftSeverity.CRITICAL,
                    source=first_src,
                    target=first_target,
                    relationship="circular_cycle",
                    expected_rule="Circular dependencies violate layered architecture and create tight coupling.",
                    actual_evidence=f"Cycle: {cycle_str}",
                    file=matching_rec["relative_file"],
                    line=matching_rec["line"],
                    snapshot=snapshot_id,
                    confidence=1.0,
                    status=DriftStatus.DETECTED,
                )
            )

        # Deduplicate drifts by (file, line, category, target)
        unique_drifts: List[ArchitectureDrift] = []
        seen_keys = set()
        for d in drifts:
            cat_str = str(getattr(d.category, "value", d.category))
            k = (d.file, d.line, cat_str, d.target)
            if k not in seen_keys:
                seen_keys.add(k)
                unique_drifts.append(d)

        # 6. Conformance Calculation (Evidence-based structural measurement)
        violations = len(unique_drifts)
        unexpected_dependencies = sum(
            1 for d in unique_drifts if str(getattr(d.category, "value", d.category)) in (DriftCategory.UNEXPECTED_EXTERNAL_DEPENDENCY.value, "UNEXPECTED_EXTERNAL_DEPENDENCY")
        )
        
        # Conformance calculation formula:
        total_evaluations = max(expected_boundaries_count, len(import_records), 1)
        conformance_val = 100.0 if violations == 0 else round(max(0.0, (1.0 - (violations / total_evaluations)) * 100.0), 2)

        summary = (
            f"Evaluated {len(import_records)} import relationships across {expected_boundaries_count} expected boundary rules. "
            f"Found {violations} architectural violations ({circular_count} cycles, {unexpected_dependencies} unexpected externals). "
            f"Architecture Conformance: {conformance_val}%."
        )

        return ArchitectureConformanceReport(
            snapshot_id=snapshot_id,
            expected_boundaries=expected_boundaries_count,
            validated_boundaries=validated_boundaries_count,
            violations=violations,
            circular_dependencies=circular_count,
            unexpected_dependencies=unexpected_dependencies,
            conformance_percentage=conformance_val,
            drifts=unique_drifts,
            baseline_version=spec.version,
            summary=summary,
            evaluated_at=datetime.utcnow().isoformat(),
        )

    def _extract_imports(self, repo_path: str) -> Tuple[List[Dict[str, Any]], Dict[str, List[str]]]:
        """Scans python and common source files extracting concrete imports."""
        records: List[Dict[str, Any]] = []
        file_lines: Dict[str, List[str]] = {}

        ignore_dirs = {".git", ".venv", "venv", "__pycache__", "node_modules", "build", "dist"}

        for root, dirs, files in os.walk(repo_path):
            dirs[:] = [d for d in dirs if d not in ignore_dirs]
            for file in sorted(files):
                if file.endswith(".py"):
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, repo_path)
                    source_mod = self._path_to_module(rel_path)

                    try:
                        with open(full_path, "r", encoding="utf-8") as f:
                            lines = f.readlines()
                            file_lines[rel_path] = lines
                            content = "".join(lines)
                            tree = ast.parse(content, filename=full_path)

                        for node in ast.walk(tree):
                            if isinstance(node, ast.Import):
                                for alias in node.names:
                                    snippet = lines[node.lineno - 1].strip() if node.lineno <= len(lines) else alias.name
                                    records.append({
                                        "source_module": source_mod,
                                        "target_module": alias.name,
                                        "line": node.lineno,
                                        "code_snippet": snippet,
                                        "relative_file": rel_path,
                                    })
                            elif isinstance(node, ast.ImportFrom):
                                target_pkg = node.module or ""
                                snippet = lines[node.lineno - 1].strip() if node.lineno <= len(lines) else target_pkg
                                records.append({
                                    "source_module": source_mod,
                                    "target_module": target_pkg,
                                    "line": node.lineno,
                                    "code_snippet": snippet,
                                    "relative_file": rel_path,
                                })
                    except Exception:
                        pass

        return records, file_lines

    def _path_to_module(self, rel_path: str) -> str:
        """Converts a relative file path to a python dotted module name."""
        clean = rel_path.replace(".py", "").replace("/", ".").replace("\\", ".")
        # Strip backend/ prefix if scanned from root
        if clean.startswith("backend."):
            clean = clean[len("backend."):]
        if clean.endswith(".__init__"):
            clean = clean[:-9]
        return clean

    def _resolve_layer(self, module_name: str, layers: Dict[str, LayerDefinition]) -> Optional[str]:
        """Resolves which defined layer a given module belongs to (picks most specific match)."""
        best_layer: Optional[str] = None
        best_len = 0
        for layer_name, layer_def in layers.items():
            for m in layer_def.modules:
                if self._matches_pattern(module_name, m):
                    if len(m) > best_len:
                        best_layer = layer_name
                        best_len = len(m)
        return best_layer

    def _matches_pattern(self, name: str, pattern: str) -> bool:
        """Checks if a module matches a layer module definition or prefix."""
        if name == pattern:
            return True
        if name.startswith(pattern + "."):
            return True
        if pattern.endswith(".*") and name.startswith(pattern[:-2]):
            return True
        return False


architecture_drift_detector = ArchitectureDriftDetector()
