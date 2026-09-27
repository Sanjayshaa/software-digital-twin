"""
Phase 4 — Change Detector.
Computes a normalized ChangeSet between baseline Snapshot A and target Snapshot B.
Performs symbol-level change resolution where supported, falling back gracefully to
file-level changes with explicit provenance.
"""

from typing import List, Dict, Any, Optional, Set
from sqlalchemy.orm import Session
from app.models.entities import StructuralArtifact, File
from app.services.impact.models import ChangeSet, ChangeItem, ChangeType


class ChangeDetector:
    """
    Deterministic detector of additions, removals, and modifications between two snapshots.
    """

    def detect_changes(
        self,
        db: Session,
        repository_id: str,
        base_snapshot_id: str,
        target_snapshot_id: str,
    ) -> ChangeSet:
        """
        Builds a normalized ChangeSet between base_snapshot_id and target_snapshot_id.
        """
        change_set = ChangeSet(
            repository_id=repository_id,
            base_snapshot_id=base_snapshot_id,
            target_snapshot_id=target_snapshot_id,
        )

        if base_snapshot_id == target_snapshot_id:
            change_set.summary = {"total_changes": 0, "added": 0, "removed": 0, "modified": 0}
            return change_set

        # Query all structural artifacts for both snapshots
        base_artifacts = (
            db.query(StructuralArtifact)
            .filter_by(snapshot_id=base_snapshot_id)
            .all()
        )
        target_artifacts = (
            db.query(StructuralArtifact)
            .filter_by(snapshot_id=target_snapshot_id)
            .all()
        )

        # Build lookup tables
        base_qual_map: Dict[str, StructuralArtifact] = {a.qualified_name: a for a in base_artifacts}
        target_qual_map: Dict[str, StructuralArtifact] = {a.qualified_name: a for a in target_artifacts}

        base_id_map: Dict[str, StructuralArtifact] = {a.id: a for a in base_artifacts}
        target_id_map: Dict[str, StructuralArtifact] = {a.id: a for a in target_artifacts}

        base_quals = set(base_qual_map.keys())
        target_quals = set(target_qual_map.keys())

        added_quals = target_quals - base_quals
        removed_quals = base_quals - target_quals
        common_quals = base_quals & target_quals

        changes: List[ChangeItem] = []

        # 1. Added Symbols
        for q in sorted(added_quals):
            art = target_qual_map[q]
            is_symbol = art.artifact_type not in ("MODULE", "PACKAGE", "DIRECTORY")
            changes.append(
                ChangeItem(
                    artifact_id=art.id,
                    qualified_name=art.qualified_name,
                    symbol_name=art.name,
                    artifact_type=art.artifact_type,
                    source_file=(art.location or "").split(":")[0],
                    change_type=ChangeType.ADDED,
                    target_location=art.location,
                    target_hash=art.source_hash,
                    line_start=art.line_start,
                    line_end=art.line_end,
                    confidence=1.0,
                    detection_method="structural_symbol_diff" if is_symbol else "file_manifest_diff",
                    is_symbol_level=is_symbol,
                    evidence=[f"Added artifact {art.qualified_name} ({art.artifact_type}) in target snapshot"],
                )
            )

        # 2. Removed Symbols
        for q in sorted(removed_quals):
            art = base_qual_map[q]
            is_symbol = art.artifact_type not in ("MODULE", "PACKAGE", "DIRECTORY")
            changes.append(
                ChangeItem(
                    artifact_id=art.id,
                    qualified_name=art.qualified_name,
                    symbol_name=art.name,
                    artifact_type=art.artifact_type,
                    source_file=(art.location or "").split(":")[0],
                    change_type=ChangeType.REMOVED,
                    base_location=art.location,
                    base_hash=art.source_hash,
                    line_start=art.line_start,
                    line_end=art.line_end,
                    confidence=1.0,
                    detection_method="structural_symbol_diff" if is_symbol else "file_manifest_diff",
                    is_symbol_level=is_symbol,
                    evidence=[f"Removed artifact {art.qualified_name} ({art.artifact_type}) absent in target snapshot"],
                )
            )

        # 3. Modified Symbols
        for q in sorted(common_quals):
            b_art = base_qual_map[q]
            t_art = target_qual_map[q]

            is_modified = False
            mod_reasons = []

            # Check hash difference
            if b_art.source_hash and t_art.source_hash and b_art.source_hash != t_art.source_hash:
                is_modified = True
                mod_reasons.append("source_hash_differs")

            # Check signature difference
            if (b_art.signature or "") != (t_art.signature or ""):
                is_modified = True
                mod_reasons.append(f"signature_changed: '{b_art.signature}' -> '{t_art.signature}'")

            # Check line span shifts
            if (b_art.line_start != t_art.line_start) or (b_art.line_end != t_art.line_end):
                is_modified = True
                mod_reasons.append(f"lines_shifted: {b_art.line_start}-{b_art.line_end} -> {t_art.line_start}-{t_art.line_end}")

            if is_modified:
                is_symbol = t_art.artifact_type not in ("MODULE", "PACKAGE", "DIRECTORY")
                changes.append(
                    ChangeItem(
                        artifact_id=t_art.id,
                        qualified_name=t_art.qualified_name,
                        symbol_name=t_art.name,
                        artifact_type=t_art.artifact_type,
                        source_file=(t_art.location or "").split(":")[0],
                        change_type=ChangeType.MODIFIED,
                        base_location=b_art.location,
                        target_location=t_art.location,
                        base_hash=b_art.source_hash,
                        target_hash=t_art.source_hash,
                        line_start=t_art.line_start,
                        line_end=t_art.line_end,
                        confidence=0.95 if is_symbol else 0.85,
                        detection_method="structural_ast_comparison" if is_symbol else "file_level_fallback",
                        is_symbol_level=is_symbol,
                        evidence=[f"Modified {t_art.qualified_name}: {', '.join(mod_reasons)}"],
                    )
                )

        # Sort deterministically by qualified name
        changes.sort(key=lambda c: (c.change_type.value, c.qualified_name))

        change_set.changes = changes
        change_set.summary = {
            "total_changes": len(changes),
            "added": len(added_quals),
            "removed": len(removed_quals),
            "modified": len([c for c in changes if c.change_type == ChangeType.MODIFIED]),
            "symbol_level_count": len([c for c in changes if c.is_symbol_level]),
            "file_level_count": len([c for c in changes if not c.is_symbol_level]),
        }

        return change_set


change_detector = ChangeDetector()
