import os
import re
from typing import List, Tuple, Dict, Optional
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
from app.services.analysis.parsers.treesitter_adapter import TreeSitterAdapter
from app.services.analysis.parsers.base import SyntaxNode
from app.services.analysis.normalizers.identity import build_artifact_id, build_relationship_id


class TypeScriptStructuralAnalyzer(StructuralAnalyzerBase):
    """Deep structural & semantic AST analyzer for TypeScript & React applications."""

    def __init__(self, parser_lang: str = "typescript"):
        self._parser_lang = parser_lang
        self._ts_parser = TreeSitterAdapter(parser_lang)

    @property
    def name(self) -> str:
        return "typescript_analyzer"

    @property
    def display_name(self) -> str:
        return "TypeScript Deep Structural Analyzer"

    @property
    def supported_languages(self) -> List[str]:
        return ["typescript", "javascript"]

    @property
    def supported_frameworks(self) -> List[str]:
        return ["react", "nextjs", "express", "nestjs"]

    @property
    def capability_level(self) -> int:
        return 4

    def detect(self, inventory: FileInventory) -> bool:
        return any(ext in inventory.files_by_ext for ext in [".ts", ".tsx"])

    def supported_capabilities(self) -> List[str]:
        return [
            "ts_ast_parsing",
            "react_component_extraction",
            "import_export_graph",
            "vitest_test_mapping",
            "express_route_detection",
        ]

    def analyze_repository(
        self,
        context: AnalysisContext,
        inventory: FileInventory
    ) -> Tuple[List[ExtractedArtifact], List[ExtractedRelationship], List[ExtractedEvidence], List[str]]:
        artifacts: List[ExtractedArtifact] = []
        relationships: List[ExtractedRelationship] = []
        evidence_list: List[ExtractedEvidence] = []
        warnings: List[str] = []

        if self._parser_lang == "javascript":
            target_files = (
                inventory.files_by_ext.get(".js", [])
                + inventory.files_by_ext.get(".jsx", [])
                + inventory.files_by_ext.get(".mjs", [])
                + inventory.files_by_ext.get(".cjs", [])
            )
            lang_label = "javascript"
        else:
            target_files = (
                inventory.files_by_ext.get(".ts", [])
                + inventory.files_by_ext.get(".tsx", [])
            )
            lang_label = "typescript"

        for tf in target_files:
            try:
                parse_res = self._ts_parser.parse_file(tf.absolute_path)
                if not parse_res.success or not parse_res.root_node:
                    warnings.extend(parse_res.errors)
                    continue

                module_qual_name = self._to_module_qualname(tf.relative_path)

                # 1. Module Artifact
                mod_id = build_artifact_id(
                    snapshot_id=context.snapshot_id,
                    language=lang_label,
                    file_path=tf.relative_path,
                    artifact_type=ArtifactType.MODULE.value,
                    qualified_name=module_qual_name,
                )
                mod_art = ExtractedArtifact(
                    id=mod_id,
                    artifact_type=ArtifactType.MODULE,
                    language=lang_label,
                    name=tf.file_name,
                    qualified_name=module_qual_name,
                    file_path=tf.relative_path,
                    line_start=1,
                    line_end=tf.line_count,
                    analyzer_source=self.name,
                    confidence=1.0,
                    metadata={"file_size": tf.size_bytes},
                )
                artifacts.append(mod_art)

                evidence_list.append(ExtractedEvidence(
                    source_reference=f"{tf.relative_path}:1-{tf.line_count}",
                    description=f"{lang_label.capitalize()} module: {module_qual_name}",
                    confidence=1.0,
                    payload={"file": tf.relative_path, "type": "module"},
                ))

                # 2. Extract AST items
                self._extract_ts_elements(
                    node=parse_res.root_node,
                    parent_art=mod_art,
                    module_qual_name=module_qual_name,
                    file_path=tf.relative_path,
                    context=context,
                    artifacts=artifacts,
                    relationships=relationships,
                    evidence_list=evidence_list,
                )

            except Exception as exc:
                warnings.append(f"Error parsing {lang_label} file {tf.relative_path}: {str(exc)}")

        return artifacts, relationships, evidence_list, warnings

    def _to_module_qualname(self, rel_path: str) -> str:
        clean = rel_path.replace("\\", "/")
        for ext in [".tsx", ".ts", ".jsx", ".js", ".mjs", ".cjs"]:
            if clean.endswith(ext):
                clean = clean[:-len(ext)]
                break
        return clean.replace("/", ".")

    def _extract_ts_elements(
        self,
        node: SyntaxNode,
        parent_art: ExtractedArtifact,
        module_qual_name: str,
        file_path: str,
        context: AnalysisContext,
        artifacts: List[ExtractedArtifact],
        relationships: List[ExtractedRelationship],
        evidence_list: List[ExtractedEvidence],
    ):
        for child in node.children:
            # Import statement
            if child.node_type == "import_statement":
                self._handle_import(child, parent_art, file_path, context, relationships)

            # Export statement
            elif child.node_type == "export_statement":
                self._handle_export(child, parent_art, module_qual_name, file_path, context, artifacts, relationships)

            # Class declaration
            elif child.node_type == "class_declaration":
                self._handle_class(child, parent_art, module_qual_name, file_path, context, artifacts, relationships)

            # Function declaration
            elif child.node_type == "function_declaration":
                self._handle_function(child, parent_art, module_qual_name, file_path, context, artifacts, relationships)

            # Expression statement (e.g. describe('...', () => { it('...', () => {}) }))
            elif child.node_type == "expression_statement":
                self._handle_test_expression(child, parent_art, module_qual_name, file_path, context, artifacts, relationships)

    def _handle_import(
        self,
        node: SyntaxNode,
        parent_art: ExtractedArtifact,
        file_path: str,
        context: AnalysisContext,
        relationships: List[ExtractedRelationship],
    ):
        string_node = next((c for c in node.children if c.node_type == "string"), None)
        if string_node:
            target_source = string_node.text.strip("'\"")
            rel_id = build_relationship_id(context.snapshot_id, parent_art.id, RelationshipType.IMPORTS.value, target_source)
            relationships.append(ExtractedRelationship(
                id=rel_id,
                source_qualified_name=parent_art.qualified_name,
                target_qualified_name=target_source,
                relationship_type=RelationshipType.IMPORTS,
                confidence=1.0,
                detection_method="typescript_import",
                source_location=f"{file_path}:{node.start_line}",
            ))

    def _handle_export(
        self,
        node: SyntaxNode,
        parent_art: ExtractedArtifact,
        module_qual_name: str,
        file_path: str,
        context: AnalysisContext,
        artifacts: List[ExtractedArtifact],
        relationships: List[ExtractedRelationship],
    ):
        # export const App = ...
        lex_decl = next((c for c in node.children if c.node_type in {"lexical_declaration", "variable_declaration"}), None)
        if lex_decl:
            for decl in lex_decl.children:
                if decl.node_type == "variable_declarator":
                    id_node = next((c for c in decl.children if c.node_type == "identifier"), None)
                    if id_node:
                        var_name = id_node.text
                        qual_name = f"{module_qual_name}.{var_name}"
                        art_id = build_artifact_id(
                            snapshot_id=context.snapshot_id,
                            language="typescript",
                            file_path=file_path,
                            artifact_type=ArtifactType.FUNCTION.value,
                            qualified_name=qual_name,
                        )
                        art = ExtractedArtifact(
                            id=art_id,
                            artifact_type=ArtifactType.FUNCTION,
                            language="typescript",
                            name=var_name,
                            qualified_name=qual_name,
                            file_path=file_path,
                            line_start=node.start_line,
                            line_end=node.end_line,
                            analyzer_source=self.name,
                            confidence=1.0,
                            metadata={"exported": True},
                        )
                        artifacts.append(art)
                        relationships.append(ExtractedRelationship(
                            id=build_relationship_id(context.snapshot_id, parent_art.id, RelationshipType.EXPORTS.value, art_id),
                            source_qualified_name=parent_art.qualified_name,
                            target_qualified_name=qual_name,
                            relationship_type=RelationshipType.EXPORTS,
                            confidence=1.0,
                            detection_method="typescript_named_export",
                            source_location=f"{file_path}:{node.start_line}",
                        ))

    def _handle_class(
        self,
        node: SyntaxNode,
        parent_art: ExtractedArtifact,
        module_qual_name: str,
        file_path: str,
        context: AnalysisContext,
        artifacts: List[ExtractedArtifact],
        relationships: List[ExtractedRelationship],
    ):
        id_node = next((c for c in node.children if c.node_type in {"type_identifier", "identifier"}), None)
        class_name = id_node.text if id_node else "AnonymousClass"
        qual_name = f"{module_qual_name}.{class_name}"
        class_id = build_artifact_id(
            snapshot_id=context.snapshot_id,
            language="typescript",
            file_path=file_path,
            artifact_type=ArtifactType.CLASS.value,
            qualified_name=qual_name,
        )
        class_art = ExtractedArtifact(
            id=class_id,
            artifact_type=ArtifactType.CLASS,
            language="typescript",
            name=class_name,
            qualified_name=qual_name,
            file_path=file_path,
            line_start=node.start_line,
            line_end=node.end_line,
            analyzer_source=self.name,
            confidence=1.0,
            metadata={},
        )
        artifacts.append(class_art)
        relationships.append(ExtractedRelationship(
            id=build_relationship_id(context.snapshot_id, parent_art.id, RelationshipType.CONTAINS.value, class_id),
            source_qualified_name=parent_art.qualified_name,
            target_qualified_name=qual_name,
            relationship_type=RelationshipType.CONTAINS,
            confidence=1.0,
            detection_method="typescript_class_declaration",
            source_location=f"{file_path}:{node.start_line}",
        ))

    def _handle_function(
        self,
        node: SyntaxNode,
        parent_art: ExtractedArtifact,
        module_qual_name: str,
        file_path: str,
        context: AnalysisContext,
        artifacts: List[ExtractedArtifact],
        relationships: List[ExtractedRelationship],
    ):
        id_node = next((c for c in node.children if c.node_type == "identifier"), None)
        fn_name = id_node.text if id_node else "anonymous"
        qual_name = f"{module_qual_name}.{fn_name}"
        fn_id = build_artifact_id(
            snapshot_id=context.snapshot_id,
            language="typescript",
            file_path=file_path,
            artifact_type=ArtifactType.FUNCTION.value,
            qualified_name=qual_name,
        )
        fn_art = ExtractedArtifact(
            id=fn_id,
            artifact_type=ArtifactType.FUNCTION,
            language="typescript",
            name=fn_name,
            qualified_name=qual_name,
            file_path=file_path,
            line_start=node.start_line,
            line_end=node.end_line,
            analyzer_source=self.name,
            confidence=1.0,
            metadata={},
        )
        artifacts.append(fn_art)
        relationships.append(ExtractedRelationship(
            id=build_relationship_id(context.snapshot_id, parent_art.id, RelationshipType.CONTAINS.value, fn_id),
            source_qualified_name=parent_art.qualified_name,
            target_qualified_name=qual_name,
            relationship_type=RelationshipType.CONTAINS,
            confidence=1.0,
            detection_method="typescript_function_declaration",
            source_location=f"{file_path}:{node.start_line}",
        ))

    def _handle_test_expression(
        self,
        node: SyntaxNode,
        parent_art: ExtractedArtifact,
        module_qual_name: str,
        file_path: str,
        context: AnalysisContext,
        artifacts: List[ExtractedArtifact],
        relationships: List[ExtractedRelationship],
    ):
        call_exp = next((c for c in node.children if c.node_type == "call_expression"), None)
        if not call_exp:
            return

        caller = call_exp.children[0] if call_exp.children else None
        if caller and caller.text in {"describe", "it", "test"}:
            args = next((c for c in call_exp.children if c.node_type == "arguments"), None)
            first_arg = args.children[1] if args and len(args.children) > 1 else None
            test_desc = first_arg.text.strip("'\"") if first_arg else f"{caller.text}_case"

            qual_name = f"{module_qual_name}::{caller.text}::{test_desc}"
            test_id = build_artifact_id(
                snapshot_id=context.snapshot_id,
                language="typescript",
                file_path=file_path,
                artifact_type=ArtifactType.TEST_CASE.value,
                qualified_name=qual_name,
            )
            test_art = ExtractedArtifact(
                id=test_id,
                artifact_type=ArtifactType.TEST_CASE,
                language="typescript",
                name=test_desc,
                qualified_name=qual_name,
                file_path=file_path,
                line_start=node.start_line,
                line_end=node.end_line,
                analyzer_source=self.name,
                confidence=1.0,
                metadata={"test_framework": "vitest/jest", "test_type": caller.text},
            )
            artifacts.append(test_art)
            relationships.append(ExtractedRelationship(
                id=build_relationship_id(context.snapshot_id, parent_art.id, RelationshipType.CONTAINS.value, test_id),
                source_qualified_name=parent_art.qualified_name,
                target_qualified_name=qual_name,
                relationship_type=RelationshipType.CONTAINS,
                confidence=1.0,
                detection_method="vitest_test_block",
                source_location=f"{file_path}:{node.start_line}",
            ))
