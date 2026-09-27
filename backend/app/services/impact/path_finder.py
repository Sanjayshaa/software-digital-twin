"""
Phase 4 — Impact Path Finder.
Canonicalizes, deduplicates, and deterministically sorts explainable impact paths
from changed roots to affected terminal entities.
"""

from typing import List, Dict, Set, Tuple
from app.services.impact.models import ImpactFinding, ImpactPath


class ImpactPathFinder:
    """
    Extracts and canonicalizes explainable causal paths from ImpactFinding instances.
    Enforces deterministic sorting and duplicate suppression.
    """

    def build_paths(self, findings: List[ImpactFinding]) -> List[ImpactPath]:
        """
        Transforms a list of ImpactFindings into canonical, deduplicated ImpactPaths.
        """
        if not findings:
            return []

        paths_map: Dict[Tuple[str, str, Tuple[str, ...]], ImpactPath] = {}

        for finding in findings:
            nodes = finding.path
            if len(nodes) < 2:
                continue

            root_sym = nodes[0]
            target_sym = nodes[-1]
            depth = len(nodes) - 1

            # Extract relationship list from evidence if possible, or fallback to single relationship
            rel_list = []
            for ev in finding.evidence:
                if "--[" in ev and "]-->" in ev:
                    try:
                        rel = ev.split("--[")[1].split("]-->")[0].strip()
                        rel_list.append(rel)
                    except IndexError:
                        pass
            if not rel_list:
                rel_list = [finding.relationship_type]

            # Determine terminal category
            terminal_type = "COMPONENT"
            tt_lower = finding.target_type.lower()
            if "test" in tt_lower or "test" in target_sym.lower():
                terminal_type = "TEST"
            elif "api" in tt_lower or "endpoint" in tt_lower or "route" in tt_lower:
                terminal_type = "API"
            elif "process" in tt_lower or "workflow" in tt_lower:
                terminal_type = "PROCESS"
            elif "db" in tt_lower or "table" in tt_lower or "entity" in tt_lower:
                terminal_type = "DATABASE"

            dedup_key = (root_sym, target_sym, tuple(nodes))
            if dedup_key not in paths_map or paths_map[dedup_key].confidence < finding.confidence:
                paths_map[dedup_key] = ImpactPath(
                    root_symbol=root_sym,
                    target_symbol=target_sym,
                    nodes=nodes,
                    relationships=rel_list,
                    depth=depth,
                    confidence=finding.confidence,
                    terminal_type=terminal_type,
                )

        # Sort paths deterministically: by depth, root_symbol, target_symbol, and nodes sequence
        sorted_paths = sorted(
            paths_map.values(),
            key=lambda p: (p.depth, p.root_symbol, p.target_symbol, tuple(p.nodes)),
        )
        return sorted_paths


impact_path_finder = ImpactPathFinder()
