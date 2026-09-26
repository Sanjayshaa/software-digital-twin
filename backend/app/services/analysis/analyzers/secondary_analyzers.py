import re
from typing import List, Tuple, Dict, Any, Optional
from app.services.discovery.scanner import FileInventory, ScannedFile
from app.services.analysis.runtime.context import AnalysisContext
from app.services.analysis.runtime.result import (
    ArtifactType,
    RelationshipType,
    ExtractedArtifact,
    ExtractedRelationship,
    ExtractedEvidence,
)
from app.services.analysis.analyzers.base import StructuralAnalyzerBase
from app.services.analysis.normalizers.identity import build_artifact_id, build_relationship_id


# ====================================================================
# 1. COBOL STRUCTURAL ANALYZER (LEVEL 1)
# ====================================================================

class CobolStructuralAnalyzer(StructuralAnalyzerBase):
    """Reliable structural analyzer for COBOL divisions, copybooks, and paragraphs."""

    @property
    def name(self) -> str:
        return "cobol_analyzer"

    @property
    def display_name(self) -> str:
        return "COBOL Mainframe Structural Analyzer"

    @property
    def supported_languages(self) -> List[str]:
        return ["cobol"]

    @property
    def supported_frameworks(self) -> List[str]:
        return []

    @property
    def capability_level(self) -> int:
        return 1  # Level 1: Structure

    def detect(self, inventory: FileInventory) -> bool:
        return any(ext in inventory.files_by_ext for ext in [".cbl", ".cob", ".cpy"])

    def supported_capabilities(self) -> List[str]:
        return ["cobol_division_scanning", "copybook_inclusion_graph"]

    def analyze_repository(
        self,
        context: AnalysisContext,
        inventory: FileInventory
    ) -> Tuple[List[ExtractedArtifact], List[ExtractedRelationship], List[ExtractedEvidence], List[str]]:
        artifacts: List[ExtractedArtifact] = []
        relationships: List[ExtractedRelationship] = []
        evidence_list: List[ExtractedEvidence] = []
        warnings: List[str] = []

        cobol_files = []
        for ext in [".cbl", ".cob", ".cpy"]:
            cobol_files.extend(inventory.files_by_ext.get(ext, []))

        for f in cobol_files:
            try:
                with open(f.absolute_path, "r", encoding="utf-8", errors="ignore") as fh:
                    lines = fh.readlines()

                program_name = f.file_name
                prog_id = build_artifact_id(
                    snapshot_id=context.snapshot_id,
                    language="cobol",
                    file_path=f.relative_path,
                    artifact_type=ArtifactType.MODULE.value,
                    qualified_name=f.file_name,
                )
                prog_art = ExtractedArtifact(
                    id=prog_id,
                    artifact_type=ArtifactType.MODULE,
                    language="cobol",
                    name=program_name,
                    qualified_name=f.file_name,
                    file_path=f.relative_path,
                    line_start=1,
                    line_end=len(lines),
                    analyzer_source=self.name,
                    confidence=1.0,
                    metadata={"is_copybook": f.extension == ".cpy"},
                )
                artifacts.append(prog_art)

                # Scan line by line for divisions & COPY statements
                for idx, line in enumerate(lines, 1):
                    upper = line.upper()

                    # Division match
                    div_match = re.search(r"\b(IDENTIFICATION|ENVIRONMENT|DATA|PROCEDURE)\s+DIVISION\b", upper)
                    if div_match:
                        div_name = f"{div_match.group(1)}_DIVISION"
                        qual = f"{f.file_name}::{div_name}"
                        div_id = build_artifact_id(
                            snapshot_id=context.snapshot_id,
                            language="cobol",
                            file_path=f.relative_path,
                            artifact_type=ArtifactType.COBOL_DIVISION.value,
                            qualified_name=qual,
                        )
                        div_art = ExtractedArtifact(
                            id=div_id,
                            artifact_type=ArtifactType.COBOL_DIVISION,
                            language="cobol",
                            name=div_name,
                            qualified_name=qual,
                            file_path=f.relative_path,
                            line_start=idx,
                            line_end=idx,
                            analyzer_source=self.name,
                            confidence=1.0,
                            metadata={"division": div_name},
                        )
                        artifacts.append(div_art)
                        relationships.append(ExtractedRelationship(
                            id=build_relationship_id(context.snapshot_id, prog_id, RelationshipType.CONTAINS.value, div_id),
                            source_qualified_name=f.file_name,
                            target_qualified_name=qual,
                            relationship_type=RelationshipType.CONTAINS,
                            confidence=1.0,
                            detection_method="cobol_division_declaration",
                            source_location=f"{f.relative_path}:{idx}",
                        ))

                    # COPY statement match
                    copy_match = re.search(r"\bCOPY\s+([A-Z0-9_\-]+)", upper)
                    if copy_match:
                        copybook_target = copy_match.group(1)
                        relationships.append(ExtractedRelationship(
                            id=build_relationship_id(context.snapshot_id, prog_id, RelationshipType.COPY_DEPENDS_ON.value, copybook_target),
                            source_qualified_name=f.file_name,
                            target_qualified_name=copybook_target,
                            relationship_type=RelationshipType.COPY_DEPENDS_ON,
                            confidence=0.95,
                            detection_method="cobol_copy_statement",
                            source_location=f"{f.relative_path}:{idx}",
                        ))

                evidence_list.append(ExtractedEvidence(
                    source_reference=f.relative_path,
                    description=f"COBOL source structure analyzed for {f.file_name}",
                    confidence=1.0,
                    payload={"file": f.relative_path},
                ))

            except Exception as exc:
                warnings.append(f"Error in COBOL analysis for {f.relative_path}: {str(exc)}")

        return artifacts, relationships, evidence_list, warnings


# ====================================================================
# 2. C / C++ STRUCTURAL ANALYZER (LEVEL 2)
# ====================================================================

class CppStructuralAnalyzer(StructuralAnalyzerBase):
    """Reliable structural analyzer for C/C++ includes, functions, and structs."""

    @property
    def name(self) -> str:
        return "cpp_analyzer"

    @property
    def display_name(self) -> str:
        return "C / C++ Native Structural Analyzer"

    @property
    def supported_languages(self) -> List[str]:
        return ["c", "cpp"]

    @property
    def supported_frameworks(self) -> List[str]:
        return []

    @property
    def capability_level(self) -> int:
        return 2  # Level 2: Includes & Structure

    def detect(self, inventory: FileInventory) -> bool:
        return any(ext in inventory.files_by_ext for ext in [".c", ".h", ".cpp", ".hpp", ".cc", ".cxx"])

    def supported_capabilities(self) -> List[str]:
        return ["c_header_include_graph", "cmake_target_resolution"]

    def analyze_repository(
        self,
        context: AnalysisContext,
        inventory: FileInventory
    ) -> Tuple[List[ExtractedArtifact], List[ExtractedRelationship], List[ExtractedEvidence], List[str]]:
        artifacts: List[ExtractedArtifact] = []
        relationships: List[ExtractedRelationship] = []
        evidence_list: List[ExtractedEvidence] = []
        warnings: List[str] = []

        cpp_files = []
        for ext in [".c", ".h", ".cpp", ".hpp", ".cc", ".cxx"]:
            cpp_files.extend(inventory.files_by_ext.get(ext, []))

        for f in cpp_files:
            try:
                with open(f.absolute_path, "r", encoding="utf-8", errors="ignore") as fh:
                    lines = fh.readlines()

                file_id = build_artifact_id(
                    snapshot_id=context.snapshot_id,
                    language="cpp",
                    file_path=f.relative_path,
                    artifact_type=ArtifactType.MODULE.value,
                    qualified_name=f.relative_path,
                )
                mod_art = ExtractedArtifact(
                    id=file_id,
                    artifact_type=ArtifactType.MODULE,
                    language="cpp",
                    name=f.file_name,
                    qualified_name=f.relative_path,
                    file_path=f.relative_path,
                    line_start=1,
                    line_end=len(lines),
                    analyzer_source=self.name,
                    confidence=1.0,
                    metadata={"header": f.extension in {".h", ".hpp"}},
                )
                artifacts.append(mod_art)

                for idx, line in enumerate(lines, 1):
                    # #include <...> or #include "..."
                    inc_match = re.search(r'#include\s+["<]([^">]+)[">]', line)
                    if inc_match:
                        inc_target = inc_match.group(1)
                        relationships.append(ExtractedRelationship(
                            id=build_relationship_id(context.snapshot_id, file_id, RelationshipType.INCLUDES.value, inc_target),
                            source_qualified_name=f.relative_path,
                            target_qualified_name=inc_target,
                            relationship_type=RelationshipType.INCLUDES,
                            confidence=1.0,
                            detection_method="c_preprocessor_include",
                            source_location=f"{f.relative_path}:{idx}",
                        ))

                    # struct / class declarations
                    struct_match = re.search(r'\b(class|struct)\s+([a-zA-Z0-9_]+)\b', line)
                    if struct_match and not line.strip().startswith("//"):
                        kind = struct_match.group(1)
                        name = struct_match.group(2)
                        qual = f"{f.relative_path}::{name}"
                        st_id = build_artifact_id(
                            snapshot_id=context.snapshot_id,
                            language="cpp",
                            file_path=f.relative_path,
                            artifact_type=ArtifactType.CPP_STRUCT.value,
                            qualified_name=qual,
                        )
                        st_art = ExtractedArtifact(
                            id=st_id,
                            artifact_type=ArtifactType.CPP_STRUCT,
                            language="cpp",
                            name=name,
                            qualified_name=qual,
                            file_path=f.relative_path,
                            line_start=idx,
                            line_end=idx,
                            analyzer_source=self.name,
                            confidence=0.95,
                            metadata={"kind": kind},
                        )
                        artifacts.append(st_art)
                        relationships.append(ExtractedRelationship(
                            id=build_relationship_id(context.snapshot_id, file_id, RelationshipType.CONTAINS.value, st_id),
                            source_qualified_name=f.relative_path,
                            target_qualified_name=qual,
                            relationship_type=RelationshipType.CONTAINS,
                            confidence=1.0,
                            detection_method="cpp_struct_declaration",
                            source_location=f"{f.relative_path}:{idx}",
                        ))

            except Exception as exc:
                warnings.append(f"Error analyzing C/C++ file {f.relative_path}: {str(exc)}")

        return artifacts, relationships, evidence_list, warnings


# ====================================================================
# 3. SQL / DATABASE STRUCTURAL ANALYZER (LEVEL 2)
# ====================================================================

class DatabaseStructuralAnalyzer(StructuralAnalyzerBase):
    """Structural analyzer for SQL DDL tables, views, and schemas."""

    @property
    def name(self) -> str:
        return "database_analyzer"

    @property
    def display_name(self) -> str:
        return "Database Schema & Entity Analyzer"

    @property
    def supported_languages(self) -> List[str]:
        return ["sql"]

    @property
    def supported_frameworks(self) -> List[str]:
        return ["postgresql", "mysql", "alembic"]

    @property
    def capability_level(self) -> int:
        return 2

    def detect(self, inventory: FileInventory) -> bool:
        return ".sql" in inventory.files_by_ext

    def supported_capabilities(self) -> List[str]:
        return ["sql_table_ddl_extraction", "database_entity_graph"]

    def analyze_repository(
        self,
        context: AnalysisContext,
        inventory: FileInventory
    ) -> Tuple[List[ExtractedArtifact], List[ExtractedRelationship], List[ExtractedEvidence], List[str]]:
        artifacts: List[ExtractedArtifact] = []
        relationships: List[ExtractedRelationship] = []
        evidence_list: List[ExtractedEvidence] = []
        warnings: List[str] = []

        sql_files = inventory.files_by_ext.get(".sql", [])

        for f in sql_files:
            try:
                with open(f.absolute_path, "r", encoding="utf-8", errors="ignore") as fh:
                    content = fh.read()

                # Table extraction
                table_matches = re.finditer(r"CREATE\s+TABLE(?:\s+IF\s+NOT\s+EXISTS)?\s+([a-zA-Z0-9_\.\"]+)", content, re.IGNORECASE)
                for tm in table_matches:
                    tbl_name = tm.group(1).replace('"', '')
                    qual = f"db::table::{tbl_name}"
                    tbl_id = build_artifact_id(
                        snapshot_id=context.snapshot_id,
                        language="sql",
                        file_path=f.relative_path,
                        artifact_type=ArtifactType.SQL_TABLE.value,
                        qualified_name=qual,
                    )
                    artifacts.append(ExtractedArtifact(
                        id=tbl_id,
                        artifact_type=ArtifactType.SQL_TABLE,
                        language="sql",
                        name=tbl_name,
                        qualified_name=qual,
                        file_path=f.relative_path,
                        analyzer_source=self.name,
                        confidence=1.0,
                        metadata={"table_name": tbl_name},
                    ))
                    evidence_list.append(ExtractedEvidence(
                        source_reference=f"{f.relative_path}",
                        description=f"SQL DDL table created: {tbl_name}",
                        confidence=1.0,
                        payload={"table": tbl_name},
                    ))

            except Exception as exc:
                warnings.append(f"Error parsing SQL file {f.relative_path}: {str(exc)}")

        return artifacts, relationships, evidence_list, warnings


# ====================================================================
# 4. DOCKER & CONTAINER ANALYZER (LEVEL 2)
# ====================================================================

class DockerStructuralAnalyzer(StructuralAnalyzerBase):
    """Structural analyzer for Dockerfiles and Docker Compose service topology."""

    @property
    def name(self) -> str:
        return "docker_analyzer"

    @property
    def display_name(self) -> str:
        return "Docker & Container Infrastructure Analyzer"

    @property
    def supported_languages(self) -> List[str]:
        return ["dockerfile", "yaml"]

    @property
    def supported_frameworks(self) -> List[str]:
        return ["docker-compose"]

    @property
    def capability_level(self) -> int:
        return 2

    def detect(self, inventory: FileInventory) -> bool:
        return len(inventory.docker_files) > 0

    def supported_capabilities(self) -> List[str]:
        return ["dockerfile_stage_extraction", "compose_service_topology"]

    def analyze_repository(
        self,
        context: AnalysisContext,
        inventory: FileInventory
    ) -> Tuple[List[ExtractedArtifact], List[ExtractedRelationship], List[ExtractedEvidence], List[str]]:
        artifacts: List[ExtractedArtifact] = []
        relationships: List[ExtractedRelationship] = []
        evidence_list: List[ExtractedEvidence] = []
        warnings: List[str] = []

        for df in inventory.docker_files:
            try:
                with open(df.absolute_path, "r", encoding="utf-8", errors="ignore") as fh:
                    lines = fh.readlines()

                is_compose = "compose" in df.file_name.lower() or df.file_name.lower() in {"compose.yaml", "compose.yml"}
                if is_compose:
                    # Parse docker-compose service topology
                    current_service = None
                    for idx, line in enumerate(lines, 1):
                        svc_match = re.match(r"^  ([a-zA-Z0-9_\-]+):", line)
                        if svc_match:
                            current_service = svc_match.group(1)
                            qual = f"service::{current_service}"
                            art_id = build_artifact_id(
                                snapshot_id=context.snapshot_id,
                                language="yaml",
                                file_path=df.relative_path,
                                artifact_type=ArtifactType.DOCKER_STAGE.value,
                                qualified_name=qual,
                            )
                            artifacts.append(ExtractedArtifact(
                                id=art_id,
                                artifact_type=ArtifactType.DOCKER_STAGE,
                                language="yaml",
                                name=current_service,
                                qualified_name=qual,
                                file_path=df.relative_path,
                                line_start=idx,
                                line_end=idx,
                                analyzer_source=self.name,
                                confidence=1.0,
                                metadata={"service_name": current_service},
                            ))
                else:
                    # Dockerfile base image & stages
                    for idx, line in enumerate(lines, 1):
                        from_match = re.match(r"^FROM\s+([^\s]+)(?:\s+AS\s+([^\s]+))?", line, re.IGNORECASE)
                        if from_match:
                            base_img = from_match.group(1)
                            stage_name = from_match.group(2) or "base"
                            qual = f"{df.relative_path}::{stage_name}"
                            art_id = build_artifact_id(
                                snapshot_id=context.snapshot_id,
                                language="dockerfile",
                                file_path=df.relative_path,
                                artifact_type=ArtifactType.DOCKER_STAGE.value,
                                qualified_name=qual,
                            )
                            artifacts.append(ExtractedArtifact(
                                id=art_id,
                                artifact_type=ArtifactType.DOCKER_STAGE,
                                language="dockerfile",
                                name=stage_name,
                                qualified_name=qual,
                                file_path=df.relative_path,
                                line_start=idx,
                                line_end=idx,
                                analyzer_source=self.name,
                                confidence=1.0,
                                metadata={"base_image": base_img},
                            ))

            except Exception as exc:
                warnings.append(f"Error analyzing container file {df.relative_path}: {str(exc)}")

        return artifacts, relationships, evidence_list, warnings
