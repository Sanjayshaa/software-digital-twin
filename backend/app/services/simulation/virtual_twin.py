"""
Phase 8 — Virtual Digital Twin Model.
Constructs an isolated, in-memory clone of a snapshot's Digital Twin, applies hypothetical mutations,
and generates a virtual ChangeSet for deterministic engine consumption.
Guarantees 100% isolation from PostgreSQL persistence and git repositories.
"""

import uuid
from typing import List, Dict, Set, Tuple, Optional, Any
from app.models.entities import StructuralArtifact, ArtifactRelationship
from app.services.impact.models import ChangeSet, ChangeItem, ChangeType
from app.services.simulation.models import (
    MutationType,
    ProposedMutation,
    VirtualTwinComparison,
)


class VirtualTwinModel:
    """
    In-memory isolated projection of a baseline Digital Twin with applied hypothetical mutations.
    """

    def __init__(
        self,
        repository_id: str,
        base_snapshot_id: str,
        base_artifacts: List[StructuralArtifact],
        base_rels: List[ArtifactRelationship],
    ):
        self.repository_id = repository_id
        self.base_snapshot_id = base_snapshot_id
        self.virtual_snapshot_id = f"virt_snap_{uuid.uuid4().hex[:10]}"

        # Base snapshot references (kept strictly read-only for comparison)
        self.base_artifacts = base_artifacts
        self.base_rels = base_rels

        # Clone in-memory artifacts and relationships
        # Note: We keep original IDs so existing relationships correctly link
        self.virtual_artifacts: List[StructuralArtifact] = [
            StructuralArtifact(
                id=a.id,
                repository_id=a.repository_id,
                snapshot_id=self.virtual_snapshot_id,
                name=a.name,
                qualified_name=a.qualified_name,
                artifact_type=a.artifact_type,
                location=a.location,
                signature=a.signature,
                docstring=a.docstring,
                source_hash=a.source_hash,
                language=a.language,
                metadata_payload=dict(a.metadata_payload or {}),
            )
            for a in base_artifacts
        ]

        self.virtual_rels: List[ArtifactRelationship] = [
            ArtifactRelationship(
                id=f"virt_rel_{r.id}",
                repository_id=r.repository_id,
                snapshot_id=self.virtual_snapshot_id,
                source_artifact_id=r.source_artifact_id,
                target_artifact_id=r.target_artifact_id,
                relationship_type=r.relationship_type,
                confidence=r.confidence,
                detection_method=r.detection_method,
                source_location=r.source_location,
                metadata_payload=dict(r.metadata_payload or {}),
            )
            for r in base_rels
        ]

        # Lookups for fast matching
        self.art_by_id: Dict[str, StructuralArtifact] = {a.id: a for a in self.virtual_artifacts}
        self.art_by_qual: Dict[str, StructuralArtifact] = {a.qualified_name: a for a in self.virtual_artifacts}
        self.art_by_name: Dict[str, List[StructuralArtifact]] = {}
        for a in self.virtual_artifacts:
            self.art_by_name.setdefault(a.name, []).append(a)

        # Track mutations and differences
        self.virtual_changes: List[ChangeItem] = []
        self.added_relationships: List[Dict[str, Any]] = []
        self.removed_relationships: List[Dict[str, Any]] = []

    def _resolve(self, ident: str) -> Optional[StructuralArtifact]:
        if not ident:
            return None
        if ident in self.art_by_id:
            return self.art_by_id[ident]
        if ident in self.art_by_qual:
            return self.art_by_qual[ident]
        if ident in self.art_by_name and len(self.art_by_name[ident]) == 1:
            return self.art_by_name[ident][0]
        ident_lower = ident.lower()
        for qn, a in self.art_by_qual.items():
            if qn.lower() == ident_lower:
                return a
        # Route fallback for APIs
        for a in self.virtual_artifacts:
            if ident in (a.name, a.location):
                return a
            if "/api" in (a.location or "").lower() and ident.split()[-1].strip().lower() in (a.location or "").lower():
                return a
        return None

    def apply_mutation(self, mut: ProposedMutation) -> None:
        """
        Applies a validated mutation into the in-memory virtual graph.
        """
        if mut.mutation_type == MutationType.MODIFY_SYMBOL:
            art = self._resolve(mut.target)
            if art:
                art.source_hash = f"{art.source_hash or 'hash'}_virt_mutated"
                art.signature = mut.parameters.get("new_signature", art.signature)
                self.virtual_changes.append(
                    ChangeItem(
                        change_type=ChangeType.MODIFIED,
                        artifact_id=art.id,
                        symbol_name=art.name,
                        qualified_name=art.qualified_name,
                        artifact_type=art.artifact_type,
                        source_file=(art.location or art.name).split(":")[0],
                        evidence=[mut.description or f"Proposed modification to symbol '{art.qualified_name}'"],
                    )
                )

        elif mut.mutation_type == MutationType.MODIFY_API:
            art = self._resolve(mut.target)
            if art:
                art.source_hash = f"{art.source_hash or 'hash'}_api_mutated"
                self.virtual_changes.append(
                    ChangeItem(
                        change_type=ChangeType.MODIFIED,
                        artifact_id=art.id,
                        symbol_name=art.name,
                        qualified_name=art.qualified_name,
                        artifact_type=art.artifact_type,
                        source_file=(art.location or art.name).split(":")[0],
                        evidence=[mut.description or f"Proposed modification to API contract '{art.name}'"],
                    )
                )

        elif mut.mutation_type == MutationType.ADD_DEPENDENCY:
            src = self._resolve(mut.source)
            tgt = self._resolve(mut.target)
            if src and tgt:
                rel_type = (mut.relationship_type or "DEPENDS_ON").upper()
                new_rel = ArtifactRelationship(
                    id=f"virt_rel_add_{uuid.uuid4().hex[:8]}",
                    repository_id=self.repository_id,
                    snapshot_id=self.virtual_snapshot_id,
                    source_artifact_id=src.id,
                    target_artifact_id=tgt.id,
                    relationship_type=rel_type,
                    confidence=1.0,
                    detection_method="scenario_simulation",
                    source_location=src.location or f"{src.name}:1",
                    metadata_payload={"simulated": True, "mutation_id": mut.mutation_id},
                )
                self.virtual_rels.append(new_rel)
                self.added_relationships.append({
                    "source": src.qualified_name,
                    "target": tgt.qualified_name,
                    "relationship_type": rel_type,
                    "mutation_id": mut.mutation_id,
                })
                # Source entity has changed dependencies
                self.virtual_changes.append(
                    ChangeItem(
                        change_type=ChangeType.MODIFIED,
                        artifact_id=src.id,
                        symbol_name=src.name,
                        qualified_name=src.qualified_name,
                        artifact_type=src.artifact_type,
                        source_file=(src.location or src.name).split(":")[0],
                        evidence=[f"Proposed added dependency to '{tgt.qualified_name}' ({rel_type})"],
                    )
                )

        elif mut.mutation_type == MutationType.REMOVE_DEPENDENCY:
            src = self._resolve(mut.source)
            tgt = self._resolve(mut.target)
            if src and tgt:
                # Find matching relationships in virtual_rels
                target_rel_type = (mut.relationship_type or "").upper()
                rels_to_remove = [
                    r for r in self.virtual_rels
                    if r.source_artifact_id == src.id and r.target_artifact_id == tgt.id
                    and (not target_rel_type or (r.relationship_type or "").upper() == target_rel_type)
                ]
                for r in rels_to_remove:
                    self.virtual_rels.remove(r)
                    self.removed_relationships.append({
                        "source": src.qualified_name,
                        "target": tgt.qualified_name,
                        "relationship_type": r.relationship_type,
                        "mutation_id": mut.mutation_id,
                    })

                self.virtual_changes.append(
                    ChangeItem(
                        change_type=ChangeType.MODIFIED,
                        artifact_id=src.id,
                        symbol_name=src.name,
                        qualified_name=src.qualified_name,
                        artifact_type=src.artifact_type,
                        source_file=(src.location or src.name).split(":")[0],
                        evidence=[f"Proposed removed dependency from '{tgt.qualified_name}'"],
                    )
                )

        elif mut.mutation_type == MutationType.MODIFY_COMPONENT_RELATIONSHIP:
            src = self._resolve(mut.source)
            tgt = self._resolve(mut.target)
            if src and tgt:
                new_type = (mut.relationship_type or "CALLS").upper()
                # Update existing or add new
                found = False
                for r in self.virtual_rels:
                    if r.source_artifact_id == src.id and r.target_artifact_id == tgt.id:
                        r.relationship_type = new_type
                        found = True
                        break
                if not found:
                    self.virtual_rels.append(
                        ArtifactRelationship(
                            id=f"virt_rel_mod_{uuid.uuid4().hex[:8]}",
                            repository_id=self.repository_id,
                            snapshot_id=self.virtual_snapshot_id,
                            source_artifact_id=src.id,
                            target_artifact_id=tgt.id,
                            relationship_type=new_type,
                            confidence=1.0,
                            detection_method="scenario_simulation",
                            source_location=src.location or f"{src.name}:1",
                            metadata_payload={"simulated": True, "mutation_id": mut.mutation_id},
                        )
                    )
                self.virtual_changes.append(
                    ChangeItem(
                        change_type=ChangeType.MODIFIED,
                        artifact_id=src.id,
                        symbol_name=src.name,
                        qualified_name=src.qualified_name,
                        artifact_type=src.artifact_type,
                        source_file=(src.location or src.name).split(":")[0],
                        evidence=[f"Proposed modified relationship to '{tgt.qualified_name}' ({new_type})"],
                    )
                )

    def build_change_set(self) -> ChangeSet:
        """
        Returns a ChangeSet representing the virtual changes.
        """
        # Deduplicate changes by artifact_id and qualified_name
        unique_changes: Dict[str, ChangeItem] = {}
        for c in self.virtual_changes:
            unique_changes[c.artifact_id] = c

        return ChangeSet(
            repository_id=self.repository_id,
            base_snapshot_id=self.base_snapshot_id,
            target_snapshot_id=self.virtual_snapshot_id,
            changes=list(unique_changes.values()),
        )
