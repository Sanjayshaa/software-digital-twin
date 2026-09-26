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


class JavaStructuralAnalyzer(StructuralAnalyzerBase):
    """Deep structural & semantic AST analyzer for Java Enterprise & Spring projects."""

    def __init__(self):
        self._parser = TreeSitterAdapter("java")

    @property
    def name(self) -> str:
        return "java_analyzer"

    @property
    def display_name(self) -> str:
        return "Java Enterprise Deep Structural Analyzer"

    @property
    def supported_languages(self) -> List[str]:
        return ["java"]

    @property
    def supported_frameworks(self) -> List[str]:
        return ["spring", "spring-boot", "jakarta-ee"]

    @property
    def capability_level(self) -> int:
        return 4

    def detect(self, inventory: FileInventory) -> bool:
        return ".java" in inventory.files_by_ext

    def supported_capabilities(self) -> List[str]:
        return [
            "java_ast_parsing",
            "class_and_method_extraction",
            "spring_boot_route_mapping",
            "junit_test_detection",
            "interface_and_inheritance_graph",
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

        java_files = inventory.files_by_ext.get(".java", [])

        for jf in java_files:
            try:
                parse_res = self._parser.parse_file(jf.absolute_path)
                if not parse_res.success or not parse_res.root_node:
                    warnings.extend(parse_res.errors)
                    continue

                package_name = self._extract_package(parse_res.root_node)
                if package_name != "default":
                    pkg_id = build_artifact_id(
                        snapshot_id=context.snapshot_id,
                        language="java",
                        file_path=jf.relative_path,
                        artifact_type=ArtifactType.PACKAGE.value,
                        qualified_name=package_name,
                    )
                    if not any(a.id == pkg_id for a in artifacts):
                        pkg_art = ExtractedArtifact(
                            id=pkg_id,
                            artifact_type=ArtifactType.PACKAGE,
                            language="java",
                            name=package_name.split(".")[-1],
                            qualified_name=package_name,
                            file_path=jf.relative_path,
                            line_start=1,
                            line_end=1,
                            analyzer_source=self.name,
                            confidence=1.0,
                            metadata={"package": package_name},
                        )
                        artifacts.append(pkg_art)

                self._extract_java_elements(
                    node=parse_res.root_node,
                    package_name=package_name,
                    file_path=jf.relative_path,
                    context=context,
                    artifacts=artifacts,
                    relationships=relationships,
                    evidence_list=evidence_list,
                )
            except Exception as exc:
                warnings.append(f"Error analyzing Java file {jf.relative_path}: {str(exc)}")

        return artifacts, relationships, evidence_list, warnings

    def _extract_package(self, root: SyntaxNode) -> str:
        for child in root.children:
            if child.node_type == "package_declaration":
                scoped = next((c for c in child.children if c.node_type in {"scoped_identifier", "identifier"}), None)
                if scoped:
                    return scoped.text
        return "default"

    def _extract_java_elements(
        self,
        node: SyntaxNode,
        package_name: str,
        file_path: str,
        context: AnalysisContext,
        artifacts: List[ExtractedArtifact],
        relationships: List[ExtractedRelationship],
        evidence_list: List[ExtractedEvidence],
    ):
        for child in node.children:
            # Import declarations
            if child.node_type == "import_declaration":
                imp_id = next((c for c in child.children if c.node_type in {"scoped_identifier", "identifier"}), None)
                if imp_id:
                    imported_name = imp_id.text
                    relationships.append(ExtractedRelationship(
                        id=build_relationship_id(context.snapshot_id, package_name, RelationshipType.IMPORTS.value, imported_name),
                        source_qualified_name=package_name,
                        target_qualified_name=imported_name,
                        relationship_type=RelationshipType.IMPORTS,
                        confidence=1.0,
                        detection_method="java_import_statement",
                        source_location=f"{file_path}:{child.start_line}",
                    ))

            # Class declarations
            elif child.node_type in {"class_declaration", "interface_declaration"}:
                self._handle_class_or_interface(
                    node=child,
                    package_name=package_name,
                    file_path=file_path,
                    context=context,
                    artifacts=artifacts,
                    relationships=relationships,
                    evidence_list=evidence_list,
                )

    def _handle_class_or_interface(
        self,
        node: SyntaxNode,
        package_name: str,
        file_path: str,
        context: AnalysisContext,
        artifacts: List[ExtractedArtifact],
        relationships: List[ExtractedRelationship],
        evidence_list: List[ExtractedEvidence],
    ):
        is_interface = (node.node_type == "interface_declaration")
        name_node = next((c for c in node.children if c.node_type == "identifier"), None)
        class_name = name_node.text if name_node else "AnonymousClass"
        qual_name = f"{package_name}.{class_name}" if package_name != "default" else class_name

        art_type = ArtifactType.INTERFACE if is_interface else ArtifactType.CLASS
        class_id = build_artifact_id(
            snapshot_id=context.snapshot_id,
            language="java",
            file_path=file_path,
            artifact_type=art_type.value,
            qualified_name=qual_name,
        )

        # Check annotations on class (e.g. @RestController)
        annotations = self._collect_annotations(node)

        class_art = ExtractedArtifact(
            id=class_id,
            artifact_type=art_type,
            language="java",
            name=class_name,
            qualified_name=qual_name,
            file_path=file_path,
            line_start=node.start_line,
            line_end=node.end_line,
            analyzer_source=self.name,
            confidence=1.0,
            metadata={"annotations": annotations},
        )
        artifacts.append(class_art)

        # Check extends
        super_class = next((c for c in node.children if c.node_type == "superclass"), None)
        if super_class:
            type_id = next((c for c in super_class.children if c.node_type == "type_identifier"), None)
            if type_id:
                relationships.append(ExtractedRelationship(
                    id=build_relationship_id(context.snapshot_id, class_id, RelationshipType.EXTENDS.value, type_id.text),
                    source_qualified_name=qual_name,
                    target_qualified_name=type_id.text,
                    relationship_type=RelationshipType.EXTENDS,
                    confidence=0.95,
                    detection_method="java_superclass",
                    source_location=f"{file_path}:{super_class.start_line}",
                ))

        # Check class body
        body = next((c for c in node.children if c.node_type in {"class_body", "interface_body"}), None)
        if body:
            for member in body.children:
                if member.node_type == "method_declaration":
                    self._handle_method(
                        node=member,
                        class_art=class_art,
                        package_name=package_name,
                        file_path=file_path,
                        context=context,
                        artifacts=artifacts,
                        relationships=relationships,
                    )

    def _collect_annotations(self, node: SyntaxNode) -> List[str]:
        annotations = []
        for c in node.children:
            if c.node_type in {"annotation", "marker_annotation"}:
                annotations.append(c.text)
            elif c.node_type == "modifiers":
                for mc in c.children:
                    if mc.node_type in {"annotation", "marker_annotation"}:
                        annotations.append(mc.text)
        return annotations

    def _handle_method(
        self,
        node: SyntaxNode,
        class_art: ExtractedArtifact,
        package_name: str,
        file_path: str,
        context: AnalysisContext,
        artifacts: List[ExtractedArtifact],
        relationships: List[ExtractedRelationship],
    ):
        name_node = next((c for c in node.children if c.node_type == "identifier"), None)
        method_name = name_node.text if name_node else "anonymousMethod"
        qual_name = f"{class_art.qualified_name}.{method_name}"

        # Collect annotations (e.g. @GetMapping("/payments"), @Test)
        annotations = self._collect_annotations(node)

        is_test = any("@Test" in a for a in annotations) or method_name.startswith("test")
        art_type = ArtifactType.TEST_CASE if is_test else ArtifactType.METHOD

        method_id = build_artifact_id(
            snapshot_id=context.snapshot_id,
            language="java",
            file_path=file_path,
            artifact_type=art_type.value,
            qualified_name=qual_name,
        )

        params_node = next((c for c in node.children if c.node_type == "formal_parameters"), None)
        sig = f"{method_name}{params_node.text if params_node else '()'}"

        method_art = ExtractedArtifact(
            id=method_id,
            artifact_type=art_type,
            language="java",
            name=method_name,
            qualified_name=qual_name,
            file_path=file_path,
            signature=sig,
            line_start=node.start_line,
            line_end=node.end_line,
            analyzer_source=self.name,
            confidence=1.0,
            metadata={"annotations": annotations},
        )
        artifacts.append(method_art)

        # Class CONTAINS Method
        relationships.append(ExtractedRelationship(
            id=build_relationship_id(context.snapshot_id, class_art.id, RelationshipType.CONTAINS.value, method_id),
            source_qualified_name=class_art.qualified_name,
            target_qualified_name=qual_name,
            relationship_type=RelationshipType.CONTAINS,
            confidence=1.0,
            detection_method="java_method_declaration",
            source_location=f"{file_path}:{node.start_line}",
        ))

        # Check Spring REST Annotations (@GetMapping, @PostMapping, etc.)
        for ann in annotations:
            ann_clean = ann.replace(" ", "")
            route_match = re.search(r"@(Get|Post|Put|Delete|Patch)Mapping\((?:value=)?[\"']([^\"']+)[\"']\)", ann)
            if route_match:
                http_method = route_match.group(1).upper()
                route_path = route_match.group(2)
                api_qual = f"{http_method} {route_path}"
                api_id = build_artifact_id(
                    snapshot_id=context.snapshot_id,
                    language="java",
                    file_path=file_path,
                    artifact_type=ArtifactType.API_ENDPOINT.value,
                    qualified_name=api_qual,
                )
                api_art = ExtractedArtifact(
                    id=api_id,
                    artifact_type=ArtifactType.API_ENDPOINT,
                    language="java",
                    name=api_qual,
                    qualified_name=api_qual,
                    file_path=file_path,
                    line_start=node.start_line,
                    line_end=node.end_line,
                    analyzer_source=self.name,
                    confidence=0.99,
                    metadata={"http_method": http_method, "route_path": route_path},
                )
                artifacts.append(api_art)

                # Method EXPOSES API_ENDPOINT
                relationships.append(ExtractedRelationship(
                    id=build_relationship_id(context.snapshot_id, method_id, RelationshipType.EXPOSES.value, api_id),
                    source_qualified_name=qual_name,
                    target_qualified_name=api_qual,
                    relationship_type=RelationshipType.EXPOSES,
                    confidence=0.99,
                    detection_method="spring_request_mapping",
                    source_location=f"{file_path}:{node.start_line}",
                ))

        # Test to Target Linkage (e.g. testPaymentProcessing TESTS Payment)
        if is_test:
            target_guess = method_name.replace("test", "").replace("Test", "")
            if target_guess:
                relationships.append(ExtractedRelationship(
                    id=build_relationship_id(context.snapshot_id, method_id, RelationshipType.TESTS.value, target_guess),
                    source_qualified_name=qual_name,
                    target_qualified_name=target_guess,
                    relationship_type=RelationshipType.TESTS,
                    confidence=0.85,
                    detection_method="junit_naming_heuristic",
                    source_location=f"{file_path}:{node.start_line}",
                ))
