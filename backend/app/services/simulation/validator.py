"""
Phase 8 — Scenario Mutation Validator.
Validates proposed mutations against the base Digital Twin state before virtual projection.
Ensures zero hallucinated entities, catches invalid/unknown targets, and surfaces ambiguities.
"""

from typing import List, Dict, Set, Optional, Tuple, Any
from app.models.entities import StructuralArtifact, ArtifactRelationship, APIEndpoint
from app.services.simulation.models import (
    MutationType,
    ProposedMutation,
    ScenarioValidationResult,
)


class ScenarioValidator:
    """
    Validates structural what-if mutations against a repository's baseline Digital Twin.
    """

    def validate_mutations(
        self,
        base_artifacts: List[StructuralArtifact],
        base_rels: List[ArtifactRelationship],
        mutations: List[ProposedMutation],
    ) -> ScenarioValidationResult:
        """
        Validates a list of proposed mutations against existing baseline entities and relationships.
        """
        errors: List[str] = []
        warnings: List[str] = []
        validated: List[ProposedMutation] = []
        unknown_entities: List[str] = []

        if not mutations:
            return ScenarioValidationResult(
                is_valid=True,
                errors=[],
                warnings=["Scenario contains no proposed mutations. Simulation will evaluate unchanged twin."],
                validated_mutations=[],
                unknown_entities=[],
            )

        # Index base artifacts for fast deterministic resolution
        by_id: Dict[str, StructuralArtifact] = {a.id: a for a in base_artifacts}
        by_qual: Dict[str, StructuralArtifact] = {a.qualified_name: a for a in base_artifacts}
        by_name: Dict[str, List[StructuralArtifact]] = {}
        for a in base_artifacts:
            by_name.setdefault(a.name, []).append(a)

        # Index base relationships: (source_id, target_id, rel_type) and (source_qual, target_qual)
        existing_rel_pairs: Set[Tuple[str, str]] = set()
        existing_rel_with_type: Set[Tuple[str, str, str]] = set()
        for r in base_rels:
            existing_rel_pairs.add((r.source_artifact_id, r.target_artifact_id))
            existing_rel_with_type.add((r.source_artifact_id, r.target_artifact_id, (r.relationship_type or "").upper()))

        import re

        def resolve_entity(ident: str) -> Tuple[Optional[StructuralArtifact], Optional[str]]:
            """
            Resolves an entity identifier by ID, qualified_name, unique name, or location stem.
            Returns (artifact, ambiguity_error_if_any).
            """
            if not ident:
                return None, "Empty entity identifier specified."
            if ident in by_id:
                return by_id[ident], None
            if ident in by_qual:
                return by_qual[ident], None
            if ident in by_name:
                matches = by_name[ident]
                if len(matches) == 1:
                    return matches[0], None
                candidates = [m.qualified_name for m in matches[:5]]
                return None, f"Ambiguous entity reference '{ident}'. Matches multiple artifacts: {candidates}. Please use the fully-qualified name."

            ident_lower = ident.lower().strip()
            ident_stem = re.sub(r'\.(?:ts|tsx|js|jsx|py|java|go|json|yml|yaml|css|html)$', '', ident_lower)
            ident_clean = re.sub(r'[^a-zA-Z0-9]', '', ident_lower)
            ident_stem_clean = re.sub(r'[^a-zA-Z0-9]', '', ident_stem)

            # Check case-insensitive / stem match on qualified_name or name
            for qn, art in by_qual.items():
                if qn.lower() in (ident_lower, ident_stem):
                    return art, None
            for nm, arts in by_name.items():
                if nm.lower() in (ident_lower, ident_stem):
                    if len(arts) == 1:
                        return arts[0], None
                nm_clean = re.sub(r'[^a-zA-Z0-9]', '', nm.lower())
                if ident_stem_clean and nm_clean == ident_stem_clean:
                    if len(arts) == 1:
                        return arts[0], None

            # Check file location suffix or filename match
            loc_matches = []
            for art in base_artifacts:
                loc = (art.location or "").lower()
                f_name = loc.split(":")[0].split("/")[-1]
                f_name_stem = re.sub(r'\.(?:ts|tsx|js|jsx|py|java|go|json|yml|yaml|css|html)$', '', f_name)
                if f_name in (ident_lower, ident_stem) or f_name_stem in (ident_lower, ident_stem):
                    loc_matches.append(art)
                elif ident_lower in loc or (ident_stem and ident_stem in loc):
                    loc_matches.append(art)

            if len(loc_matches) == 1:
                return loc_matches[0], None
            elif len(loc_matches) > 1:
                prio = [m for m in loc_matches if m.artifact_type in ("CLASS", "MODULE", "SERVICE", "COMPONENT")]
                if len(prio) == 1:
                    return prio[0], None
                if prio:
                    return prio[0], None
                return loc_matches[0], None

            # Check route/path match for API endpoints
            for art in base_artifacts:
                if art.artifact_type in ("API_ENDPOINT", "ENDPOINT") or "/api/" in (art.location or ""):
                    if ident in (art.name, art.location):
                        return art, None
            return None, None

        for mut in mutations:
            # Check supported mutation type
            if not isinstance(mut.mutation_type, MutationType):
                try:
                    mut.mutation_type = MutationType(mut.mutation_type)
                except ValueError:
                    errors.append(f"Unsupported mutation type: '{mut.mutation_type}'. Must be one of {[m.value for m in MutationType]}.")
                    continue

            # 1. MODIFY_SYMBOL
            if mut.mutation_type == MutationType.MODIFY_SYMBOL:
                art, ambig = resolve_entity(mut.target)
                if ambig:
                    errors.append(ambig)
                elif not art:
                    unknown_entities.append(mut.target)
                    errors.append(f"Unknown symbol target '{mut.target}'. Entity does not exist in the base Digital Twin.")
                else:
                    validated.append(mut)

            # 2. MODIFY_API
            elif mut.mutation_type == MutationType.MODIFY_API:
                art, ambig = resolve_entity(mut.target)
                if ambig:
                    errors.append(ambig)
                elif not art:
                    # Check if target resembles an API route (e.g. POST /payments or /api/v1/checkout)
                    found_api = False
                    target_clean = mut.target.split()[-1].strip().lower()
                    for a in base_artifacts:
                        if a.artifact_type in ("API_ENDPOINT", "ENDPOINT") or "/api" in (a.location or "").lower():
                            if target_clean in (a.location or "").lower() or target_clean in (a.name or "").lower():
                                art = a
                                found_api = True
                                break
                    if found_api:
                        validated.append(mut)
                    else:
                        unknown_entities.append(mut.target)
                        errors.append(f"Unknown API endpoint target '{mut.target}'. Endpoint does not exist in the base Digital Twin.")
                else:
                    validated.append(mut)

            # 3. ADD_DEPENDENCY
            elif mut.mutation_type == MutationType.ADD_DEPENDENCY:
                if not mut.source:
                    errors.append(f"ADD_DEPENDENCY mutation '{mut.mutation_id}' requires a 'source' entity.")
                    continue
                src_art, src_ambig = resolve_entity(mut.source)
                tgt_art, tgt_ambig = resolve_entity(mut.target)

                if src_ambig:
                    errors.append(src_ambig)
                elif not src_art:
                    unknown_entities.append(mut.source)
                    errors.append(f"Unknown dependency source '{mut.source}'. Entity does not exist in the base Digital Twin.")

                if tgt_ambig:
                    errors.append(tgt_ambig)
                elif not tgt_art:
                    unknown_entities.append(mut.target)
                    errors.append(f"Unknown dependency target '{mut.target}'. Entity does not exist in the base Digital Twin.")

                if src_art and tgt_art:
                    if src_art.id == tgt_art.id:
                        warnings.append(f"ADD_DEPENDENCY creates a self-loop on '{src_art.qualified_name}'.")
                    # Check if already exists
                    rel_type = (mut.relationship_type or "DEPENDS_ON").upper()
                    if (src_art.id, tgt_art.id, rel_type) in existing_rel_with_type:
                        warnings.append(f"Dependency already exists between '{src_art.qualified_name}' and '{tgt_art.qualified_name}' ({rel_type}).")
                    validated.append(mut)

            # 4. REMOVE_DEPENDENCY
            elif mut.mutation_type == MutationType.REMOVE_DEPENDENCY:
                if not mut.source:
                    # Single-target decouple / component removal
                    tgt_art, tgt_ambig = resolve_entity(mut.target)
                    if tgt_ambig:
                        errors.append(tgt_ambig)
                    elif not tgt_art:
                        unknown_entities.append(mut.target)
                        errors.append(f"Unknown target entity '{mut.target}' to decouple/remove.")
                    else:
                        validated.append(mut)
                    continue

                src_art, src_ambig = resolve_entity(mut.source)
                tgt_art, tgt_ambig = resolve_entity(mut.target)

                if src_ambig:
                    errors.append(src_ambig)
                elif not src_art:
                    unknown_entities.append(mut.source)
                    errors.append(f"Unknown source entity '{mut.source}' for REMOVE_DEPENDENCY.")

                if tgt_ambig:
                    errors.append(tgt_ambig)
                elif not tgt_art:
                    unknown_entities.append(mut.target)
                    errors.append(f"Unknown target entity '{mut.target}' for REMOVE_DEPENDENCY.")

                if src_art and tgt_art:
                    # Check if relationship exists between them
                    if (src_art.id, tgt_art.id) not in existing_rel_pairs:
                        errors.append(f"Cannot remove non-existent dependency: No relationship exists from '{src_art.qualified_name}' to '{tgt_art.qualified_name}'.")
                    else:
                        validated.append(mut)

            # 5. REMOVE_COMPONENT & SERVICE_OUTAGE
            elif mut.mutation_type in (MutationType.REMOVE_COMPONENT, MutationType.SERVICE_OUTAGE):
                tgt_art, tgt_ambig = resolve_entity(mut.target)
                if tgt_ambig:
                    errors.append(tgt_ambig)
                elif not tgt_art:
                    unknown_entities.append(mut.target)
                    errors.append(f"Unknown target entity '{mut.target}' for {mut.mutation_type.value}. Entity does not exist in the base Digital Twin.")
                else:
                    validated.append(mut)

            # 6. SCHEMA_MIGRATION
            elif mut.mutation_type == MutationType.SCHEMA_MIGRATION:
                tgt_art, tgt_ambig = resolve_entity(mut.target)
                if tgt_ambig:
                    errors.append(tgt_ambig)
                elif not tgt_art:
                    unknown_entities.append(mut.target)
                    errors.append(f"Unknown schema/table entity '{mut.target}'. Entity does not exist in the base Digital Twin.")
                else:
                    validated.append(mut)

            # 5. MODIFY_COMPONENT_RELATIONSHIP
            elif mut.mutation_type == MutationType.MODIFY_COMPONENT_RELATIONSHIP:
                if not mut.source:
                    errors.append(f"MODIFY_COMPONENT_RELATIONSHIP mutation '{mut.mutation_id}' requires a 'source' entity.")
                    continue
                src_art, src_ambig = resolve_entity(mut.source)
                tgt_art, tgt_ambig = resolve_entity(mut.target)

                if src_ambig:
                    errors.append(src_ambig)
                elif not src_art:
                    unknown_entities.append(mut.source)
                    errors.append(f"Unknown component source '{mut.source}'.")

                if tgt_ambig:
                    errors.append(tgt_ambig)
                elif not tgt_art:
                    unknown_entities.append(mut.target)
                    errors.append(f"Unknown component target '{mut.target}'.")

                if src_art and tgt_art:
                    validated.append(mut)

        is_valid = len(errors) == 0
        return ScenarioValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            validated_mutations=validated if is_valid else [],
            unknown_entities=sorted(list(set(unknown_entities))),
        )


scenario_validator = ScenarioValidator()
