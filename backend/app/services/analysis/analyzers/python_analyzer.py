import os
import re
from typing import List, Tuple, Dict, Set, Optional
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


class PythonStructuralAnalyzer(StructuralAnalyzerBase):
    """Deep structural & semantic AST analyzer for Python."""

    def __init__(self):
        self._parser = TreeSitterAdapter("python")

    @property
    def name(self) -> str:
        return "python_analyzer"

    @property
    def display_name(self) -> str:
        return "Python Deep Structural Analyzer"

    @property
    def supported_languages(self) -> List[str]:
        return ["python"]

    @property
    def supported_frameworks(self) -> List[str]:
        return ["fastapi", "flask", "django"]

    @property
    def capability_level(self) -> int:
        return 4

    def detect(self, inventory: FileInventory) -> bool:
        return ".py" in inventory.files_by_ext

    def supported_capabilities(self) -> List[str]:
        return [
            "python_ast_parsing",
            "class_and_function_extraction",
            "import_resolution",
            "call_graph_derivation",
            "fastapi_endpoint_extraction",
            "pytest_target_mapping",
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

        py_files = inventory.files_by_ext.get(".py", [])
        known_symbols: Dict[str, ExtractedArtifact] = {}

        for sf in py_files:
            try:
                parse_res = self._parser.parse_file(sf.absolute_path)
                if not parse_res.success or not parse_res.root_node:
                    warnings.extend(parse_res.errors)
                    continue

                module_qual_name = self._to_module_qualname(sf.relative_path)

                # 1. Module Artifact
                mod_id = build_artifact_id(
                    snapshot_id=context.snapshot_id,
                    language="python",
                    file_path=sf.relative_path,
                    artifact_type=ArtifactType.MODULE.value,
                    qualified_name=module_qual_name,
                )
                mod_art = ExtractedArtifact(
                    id=mod_id,
                    artifact_type=ArtifactType.MODULE,
                    language="python",
                    name=sf.file_name,
                    qualified_name=module_qual_name,
                    file_path=sf.relative_path,
                    line_start=1,
                    line_end=sf.line_count,
                    analyzer_source=self.name,
                    confidence=1.0,
                    metadata={"file_size": sf.size_bytes},
                )
                artifacts.append(mod_art)
                known_symbols[module_qual_name] = mod_art

                evidence_list.append(ExtractedEvidence(
                    source_reference=f"{sf.relative_path}:1-{sf.line_count}",
                    description=f"Python module: {module_qual_name}",
                    confidence=1.0,
                    payload={"file": sf.relative_path, "type": "module"},
                ))

                # 2. Extract AST elements from root node
                self._extract_node_elements(
                    node=parse_res.root_node,
                    parent_art=mod_art,
                    module_qual_name=module_qual_name,
                    file_path=sf.relative_path,
                    context=context,
                    artifacts=artifacts,
                    relationships=relationships,
                    evidence_list=evidence_list,
                    known_symbols=known_symbols,
                )

            except Exception as exc:
                warnings.append(f"Error parsing Python file {sf.relative_path}: {str(exc)}")

        return artifacts, relationships, evidence_list, warnings

    def _to_module_qualname(self, rel_path: str) -> str:
        clean = rel_path.replace("\\", "/")
        if clean.endswith(".py"):
            clean = clean[:-3]
        return clean.replace("/", ".")

    def _extract_node_elements(
        self,
        node: SyntaxNode,
        parent_art: ExtractedArtifact,
        module_qual_name: str,
        file_path: str,
        context: AnalysisContext,
        artifacts: List[ExtractedArtifact],
        relationships: List[ExtractedRelationship],
        evidence_list: List[ExtractedEvidence],
        known_symbols: Dict[str, ExtractedArtifact],
    ):
        for child in node.children:
            # Classes
            if child.node_type == "class_definition":
                self._handle_class(
                    node=child,
                    parent_art=parent_art,
                    module_qual_name=module_qual_name,
                    file_path=file_path,
                    context=context,
                    artifacts=artifacts,
                    relationships=relationships,
                    evidence_list=evidence_list,
                    known_symbols=known_symbols,
                )

            # Functions / Standalone methods
            elif child.node_type == "function_definition":
                self._handle_function(
                    node=child,
                    parent_art=parent_art,
                    module_qual_name=module_qual_name,
                    file_path=file_path,
                    context=context,
                    artifacts=artifacts,
                    relationships=relationships,
                    evidence_list=evidence_list,
                    known_symbols=known_symbols,
                    is_method=False,
                )

            # Imports
            elif child.node_type in {"import_statement", "import_from_statement"}:
                self._handle_import(
                    node=child,
                    parent_art=parent_art,
                    file_path=file_path,
                    context=context,
                    relationships=relationships,
                    evidence_list=evidence_list,
                )

            # Decorated functions/classes
            elif child.node_type == "decorated_definition":
                self._handle_decorated(
                    node=child,
                    parent_art=parent_art,
                    module_qual_name=module_qual_name,
                    file_path=file_path,
                    context=context,
                    artifacts=artifacts,
                    relationships=relationships,
                    evidence_list=evidence_list,
                    known_symbols=known_symbols,
                )

    def _handle_class(
        self,
        node: SyntaxNode,
        parent_art: ExtractedArtifact,
        module_qual_name: str,
        file_path: str,
        context: AnalysisContext,
        artifacts: List[ExtractedArtifact],
        relationships: List[ExtractedRelationship],
        evidence_list: List[ExtractedEvidence],
        known_symbols: Dict[str, ExtractedArtifact],
    ):
        name_node = next((c for c in node.children if c.node_type == "identifier"), None)
        class_name = name_node.text if name_node else "AnonymousClass"
        qual_name = f"{module_qual_name}.{class_name}"

        class_id = build_artifact_id(
            snapshot_id=context.snapshot_id,
            language="python",
            file_path=file_path,
            artifact_type=ArtifactType.CLASS.value,
            qualified_name=qual_name,
        )

        class_art = ExtractedArtifact(
            id=class_id,
            artifact_type=ArtifactType.CLASS,
            language="python",
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
        known_symbols[qual_name] = class_art

        # Module CONTAINS Class
        rel_id = build_relationship_id(context.snapshot_id, parent_art.id, RelationshipType.CONTAINS.value, class_id)
        relationships.append(ExtractedRelationship(
            id=rel_id,
            source_qualified_name=parent_art.qualified_name,
            target_qualified_name=qual_name,
            relationship_type=RelationshipType.CONTAINS,
            confidence=1.0,
            detection_method="ast_nesting",
            source_location=f"{file_path}:{node.start_line}",
        ))

        # Check inheritance (argument_list in class definition)
        arg_list = next((c for c in node.children if c.node_type == "argument_list"), None)
        if arg_list:
            for arg in arg_list.children:
                if arg.node_type == "identifier":
                    base_name = arg.text
                    relationships.append(ExtractedRelationship(
                        id=build_relationship_id(context.snapshot_id, class_id, RelationshipType.EXTENDS.value, f"base_{base_name}"),
                        source_qualified_name=qual_name,
                        target_qualified_name=base_name,
                        relationship_type=RelationshipType.EXTENDS,
                        confidence=0.95,
                        detection_method="ast_class_inheritance",
                        source_location=f"{file_path}:{arg.start_line}",
                    ))

        # Extract methods inside class body
        body = next((c for c in node.children if c.node_type == "block"), None)
        if body:
            for child in body.children:
                if child.node_type == "function_definition":
                    self._handle_function(
                        node=child,
                        parent_art=class_art,
                        module_qual_name=qual_name,
                        file_path=file_path,
                        context=context,
                        artifacts=artifacts,
                        relationships=relationships,
                        evidence_list=evidence_list,
                        known_symbols=known_symbols,
                        is_method=True,
                    )
                elif child.node_type == "decorated_definition":
                    self._handle_decorated(
                        node=child,
                        parent_art=class_art,
                        module_qual_name=qual_name,
                        file_path=file_path,
                        context=context,
                        artifacts=artifacts,
                        relationships=relationships,
                        evidence_list=evidence_list,
                        known_symbols=known_symbols,
                    )

    def _handle_function(
        self,
        node: SyntaxNode,
        parent_art: ExtractedArtifact,
        module_qual_name: str,
        file_path: str,
        context: AnalysisContext,
        artifacts: List[ExtractedArtifact],
        relationships: List[ExtractedRelationship],
        evidence_list: List[ExtractedEvidence],
        known_symbols: Dict[str, ExtractedArtifact],
        is_method: bool = False,
        decorators: Optional[List[str]] = None,
    ):
        name_node = next((c for c in node.children if c.node_type == "identifier"), None)
        fn_name = name_node.text if name_node else "anonymous"
        qual_name = f"{module_qual_name}.{fn_name}"

        is_test = fn_name.startswith("test_") or "test" in file_path.lower()
        art_type = ArtifactType.TEST_CASE if is_test else (ArtifactType.METHOD if is_method else ArtifactType.FUNCTION)

        fn_id = build_artifact_id(
            snapshot_id=context.snapshot_id,
            language="python",
            file_path=file_path,
            artifact_type=art_type.value,
            qualified_name=qual_name,
        )

        params_node = next((c for c in node.children if c.node_type == "parameters"), None)
        sig = f"def {fn_name}{params_node.text if params_node else '()'}"

        fn_art = ExtractedArtifact(
            id=fn_id,
            artifact_type=art_type,
            language="python",
            name=fn_name,
            qualified_name=qual_name,
            file_path=file_path,
            signature=sig,
            line_start=node.start_line,
            line_end=node.end_line,
            analyzer_source=self.name,
            confidence=1.0,
            metadata={"decorators": decorators or []},
        )
        artifacts.append(fn_art)
        known_symbols[qual_name] = fn_art

        # Parent CONTAINS Function/Method
        rel_id = build_relationship_id(context.snapshot_id, parent_art.id, RelationshipType.CONTAINS.value, fn_id)
        relationships.append(ExtractedRelationship(
            id=rel_id,
            source_qualified_name=parent_art.qualified_name,
            target_qualified_name=qual_name,
            relationship_type=RelationshipType.CONTAINS,
            confidence=1.0,
            detection_method="ast_nesting",
            source_location=f"{file_path}:{node.start_line}",
        ))

        # Check API Endpoint decorators (e.g. @app.get("/items"), @router.post("/items"))
        if decorators:
            for deco in decorators:
                route_match = re.search(r"@(app|router)\.(get|post|put|delete|patch)\(\s*['\"]([^'\"]+)['\"]", deco)
                if route_match:
                    http_method = route_match.group(2).upper()
                    route_path = route_match.group(3)
                    api_qual = f"{http_method} {route_path}"
                    api_id = build_artifact_id(
                        snapshot_id=context.snapshot_id,
                        language="python",
                        file_path=file_path,
                        artifact_type=ArtifactType.API_ENDPOINT.value,
                        qualified_name=api_qual,
                    )
                    api_art = ExtractedArtifact(
                        id=api_id,
                        artifact_type=ArtifactType.API_ENDPOINT,
                        language="python",
                        name=f"{http_method} {route_path}",
                        qualified_name=api_qual,
                        file_path=file_path,
                        line_start=node.start_line,
                        line_end=node.end_line,
                        analyzer_source=self.name,
                        confidence=0.99,
                        metadata={"http_method": http_method, "route_path": route_path},
                    )
                    artifacts.append(api_art)

                    # Function EXPOSES API_ENDPOINT
                    relationships.append(ExtractedRelationship(
                        id=build_relationship_id(context.snapshot_id, fn_id, RelationshipType.EXPOSES.value, api_id),
                        source_qualified_name=qual_name,
                        target_qualified_name=api_qual,
                        relationship_type=RelationshipType.EXPOSES,
                        confidence=0.99,
                        detection_method="fastapi_route_decorator",
                        source_location=f"{file_path}:{node.start_line}",
                    ))

        # Test to Target Linkage (e.g. test_create_order TESTS create_order)
        if is_test:
            target_name = fn_name.replace("test_", "")
            relationships.append(ExtractedRelationship(
                id=build_relationship_id(context.snapshot_id, fn_id, RelationshipType.TESTS.value, target_name),
                source_qualified_name=qual_name,
                target_qualified_name=target_name,
                relationship_type=RelationshipType.TESTS,
                confidence=0.90,
                detection_method="test_naming_convention",
                source_location=f"{file_path}:{node.start_line}",
            ))

        # Extract function call expressions within the body
        self._extract_calls(node, fn_art, file_path, context, relationships)

    def _handle_decorated(
        self,
        node: SyntaxNode,
        parent_art: ExtractedArtifact,
        module_qual_name: str,
        file_path: str,
        context: AnalysisContext,
        artifacts: List[ExtractedArtifact],
        relationships: List[ExtractedRelationship],
        evidence_list: List[ExtractedEvidence],
        known_symbols: Dict[str, ExtractedArtifact],
    ):
        decorators = []
        fn_or_class = None

        for child in node.children:
            if child.node_type == "decorator":
                decorators.append(child.text)
            elif child.node_type in {"function_definition", "class_definition"}:
                fn_or_class = child

        if fn_or_class:
            if fn_or_class.node_type == "function_definition":
                self._handle_function(
                    node=fn_or_class,
                    parent_art=parent_art,
                    module_qual_name=module_qual_name,
                    file_path=file_path,
                    context=context,
                    artifacts=artifacts,
                    relationships=relationships,
                    evidence_list=evidence_list,
                    known_symbols=known_symbols,
                    is_method=(parent_art.artifact_type == ArtifactType.CLASS),
                    decorators=decorators,
                )
            elif fn_or_class.node_type == "class_definition":
                self._handle_class(
                    node=fn_or_class,
                    parent_art=parent_art,
                    module_qual_name=module_qual_name,
                    file_path=file_path,
                    context=context,
                    artifacts=artifacts,
                    relationships=relationships,
                    evidence_list=evidence_list,
                    known_symbols=known_symbols,
                )

    def _handle_import(
        self,
        node: SyntaxNode,
        parent_art: ExtractedArtifact,
        file_path: str,
        context: AnalysisContext,
        relationships: List[ExtractedRelationship],
        evidence_list: List[ExtractedEvidence],
    ):
        raw_text = node.text
        # from X import Y
        from_match = re.search(r"from\s+([a-zA-Z0-9_.]+)\s+import\s+([a-zA-Z0-9_, ]+)", raw_text)
        if from_match:
            source_mod = from_match.group(1)
            imported_items = [i.strip() for i in from_match.group(2).split(",")]
            for item in imported_items:
                target_qual = f"{source_mod}.{item}"
                rel_id = build_relationship_id(context.snapshot_id, parent_art.id, RelationshipType.IMPORTS.value, target_qual)
                relationships.append(ExtractedRelationship(
                    id=rel_id,
                    source_qualified_name=parent_art.qualified_name,
                    target_qualified_name=target_qual,
                    relationship_type=RelationshipType.IMPORTS,
                    confidence=1.0,
                    detection_method="python_import_from",
                    source_location=f"{file_path}:{node.start_line}",
                ))
            return

        # import X
        import_match = re.search(r"import\s+([a-zA-Z0-9_.]+)", raw_text)
        if import_match:
            target_mod = import_match.group(1)
            rel_id = build_relationship_id(context.snapshot_id, parent_art.id, RelationshipType.IMPORTS.value, target_mod)
            relationships.append(ExtractedRelationship(
                id=rel_id,
                source_qualified_name=parent_art.qualified_name,
                target_qualified_name=target_mod,
                relationship_type=RelationshipType.IMPORTS,
                confidence=1.0,
                detection_method="python_import",
                source_location=f"{file_path}:{node.start_line}",
            ))

    def _extract_calls(
        self,
        node: SyntaxNode,
        fn_art: ExtractedArtifact,
        file_path: str,
        context: AnalysisContext,
        relationships: List[ExtractedRelationship],
    ):
        for desc in node.walk():
            if desc.node_type == "call":
                func_node = desc.children[0] if desc.children else None
                if func_node:
                    called_name = func_node.text
                    # Avoid trivial builtin calls like print, len, range
                    if called_name not in {"print", "len", "range", "str", "int", "float", "dict", "list", "set"}:
                        rel_id = build_relationship_id(context.snapshot_id, fn_art.id, RelationshipType.CALLS.value, called_name)
                        relationships.append(ExtractedRelationship(
                            id=rel_id,
                            source_qualified_name=fn_art.qualified_name,
                            target_qualified_name=called_name,
                            relationship_type=RelationshipType.CALLS,
                            confidence=0.85,
                            detection_method="ast_call_expression",
                            source_location=f"{file_path}:{desc.start_line}",
                        ))
