from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from app.services.discovery.scanner import FileInventory
from app.services.discovery.models import CapabilitySpec, ProjectProfile


class AnalyzerInterface(ABC):
    """Common contract for all language, framework, and infrastructure analyzers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier (e.g. 'python_analyzer', 'cobol_analyzer')."""
        pass

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable name."""
        pass

    @property
    @abstractmethod
    def supported_languages(self) -> List[str]:
        """List of language identifiers this analyzer supports."""
        pass

    @property
    @abstractmethod
    def supported_frameworks(self) -> List[str]:
        """List of framework identifiers this analyzer supports."""
        pass

    @property
    @abstractmethod
    def capability_level(self) -> int:
        """Supported capability level (0 to 4)."""
        pass

    @abstractmethod
    def detect(self, inventory: FileInventory) -> bool:
        """Return True if this analyzer should be activated for this inventory."""
        pass

    @abstractmethod
    def supported_capabilities(self) -> List[str]:
        """List of fine-grained capability tags supported by this analyzer."""
        pass

    def analyze(self, target_path: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execution hook invoked during Digital Twin building phase."""
        return {
            "analyzer": self.name,
            "status": "planned",
            "message": f"Execution placeholder for {self.display_name} in Phase 3",
        }


# ====================================================================
# BUILT-IN REFERENCE ANALYZER REGISTRATIONS
# ====================================================================

class PythonAnalyzer(AnalyzerInterface):
    @property
    def name(self) -> str:
        return "python_analyzer"

    @property
    def display_name(self) -> str:
        return "Python Structural & Semantic Analyzer"

    @property
    def supported_languages(self) -> List[str]:
        return ["python"]

    @property
    def supported_frameworks(self) -> List[str]:
        return ["fastapi", "flask", "django"]

    @property
    def capability_level(self) -> int:
        return 4  # Level 4: Deep Semantic

    def detect(self, inventory: FileInventory) -> bool:
        return ".py" in inventory.files_by_ext or any(
            f.file_name in {"pyproject.toml", "requirements.txt", "Pipfile", "setup.py"}
            for f in inventory.manifest_files
        )

    def supported_capabilities(self) -> List[str]:
        return [
            "python_ast_parsing",
            "symbol_extraction",
            "dependency_resolution",
            "fastapi_endpoint_extraction",
            "pytest_test_discovery",
            "deep_semantic_callgraph",
        ]


class JavaAnalyzer(AnalyzerInterface):
    @property
    def name(self) -> str:
        return "java_analyzer"

    @property
    def display_name(self) -> str:
        return "Java Enterprise & Spring Analyzer"

    @property
    def supported_languages(self) -> List[str]:
        return ["java"]

    @property
    def supported_frameworks(self) -> List[str]:
        return ["spring", "spring-boot", "jakarta-ee"]

    @property
    def capability_level(self) -> int:
        return 4  # Level 4: Deep Semantic

    def detect(self, inventory: FileInventory) -> bool:
        return ".java" in inventory.files_by_ext or any(
            f.file_name in {"pom.xml", "build.gradle", "settings.gradle"}
            for f in inventory.manifest_files
        )

    def supported_capabilities(self) -> List[str]:
        return [
            "java_ast_parsing",
            "class_method_extraction",
            "maven_dependency_graph",
            "spring_boot_annotation_analysis",
            "junit_test_mapping",
        ]


class TypeScriptAnalyzer(AnalyzerInterface):
    @property
    def name(self) -> str:
        return "typescript_analyzer"

    @property
    def display_name(self) -> str:
        return "TypeScript & Modern JS Analyzer"

    @property
    def supported_languages(self) -> List[str]:
        return ["typescript", "javascript"]

    @property
    def supported_frameworks(self) -> List[str]:
        return ["react", "nextjs", "express", "nestjs", "vue"]

    @property
    def capability_level(self) -> int:
        return 4  # Level 4: Deep Semantic

    def detect(self, inventory: FileInventory) -> bool:
        return any(ext in inventory.files_by_ext for ext in [".ts", ".tsx", ".js", ".jsx"]) or any(
            f.file_name in {"package.json", "tsconfig.json"}
            for f in inventory.manifest_files
        )

    def supported_capabilities(self) -> List[str]:
        return [
            "ts_ast_parsing",
            "export_import_resolution",
            "npm_dependency_tree",
            "react_component_graph",
            "express_route_detection",
            "vitest_jest_discovery",
        ]


class GoAnalyzer(AnalyzerInterface):
    @property
    def name(self) -> str:
        return "go_analyzer"

    @property
    def display_name(self) -> str:
        return "Go System Analyzer"

    @property
    def supported_languages(self) -> List[str]:
        return ["go"]

    @property
    def supported_frameworks(self) -> List[str]:
        return ["gin", "fiber", "echo"]

    @property
    def capability_level(self) -> int:
        return 3  # Level 3: Framework / API / Test

    def detect(self, inventory: FileInventory) -> bool:
        return ".go" in inventory.files_by_ext or any(
            f.file_name == "go.mod" for f in inventory.manifest_files
        )

    def supported_capabilities(self) -> List[str]:
        return [
            "go_ast_parsing",
            "package_symbol_extraction",
            "go_mod_dependency_graph",
            "go_test_discovery",
        ]


class CppAnalyzer(AnalyzerInterface):
    @property
    def name(self) -> str:
        return "cpp_analyzer"

    @property
    def display_name(self) -> str:
        return "C / C++ Native Code Analyzer"

    @property
    def supported_languages(self) -> List[str]:
        return ["c", "cpp"]

    @property
    def supported_frameworks(self) -> List[str]:
        return []

    @property
    def capability_level(self) -> int:
        return 2  # Level 2: Dependency & Structure

    def detect(self, inventory: FileInventory) -> bool:
        return any(ext in inventory.files_by_ext for ext in [".c", ".cpp", ".cc", ".cxx", ".h", ".hpp"]) or any(
            f.file_name.lower() in {"cmakelists.txt", "makefile"} for f in inventory.manifest_files
        )

    def supported_capabilities(self) -> List[str]:
        return [
            "c_header_include_graph",
            "cmake_target_resolution",
            "native_symbol_index",
        ]


class CobolAnalyzer(AnalyzerInterface):
    @property
    def name(self) -> str:
        return "cobol_analyzer"

    @property
    def display_name(self) -> str:
        return "COBOL Mainframe Legacy Analyzer"

    @property
    def supported_languages(self) -> List[str]:
        return ["cobol"]

    @property
    def supported_frameworks(self) -> List[str]:
        return []

    @property
    def capability_level(self) -> int:
        return 1  # Level 1: Structural analysis

    def detect(self, inventory: FileInventory) -> bool:
        return any(ext in inventory.files_by_ext for ext in [".cob", ".cbl", ".cpy", ".cobol"])

    def supported_capabilities(self) -> List[str]:
        return [
            "cobol_division_scanning",
            "copybook_inclusion_graph",
            "data_division_record_mapping",
        ]


class DockerAnalyzer(AnalyzerInterface):
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
        return 2  # Level 2: Dependency / Architecture

    def detect(self, inventory: FileInventory) -> bool:
        return len(inventory.docker_files) > 0

    def supported_capabilities(self) -> List[str]:
        return [
            "dockerfile_stage_extraction",
            "compose_service_topology",
            "port_network_mapping",
        ]


class DatabaseAnalyzer(AnalyzerInterface):
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
        return ["alembic", "flyway", "liquibase"]

    @property
    def capability_level(self) -> int:
        return 2  # Level 2: Architecture entity

    def detect(self, inventory: FileInventory) -> bool:
        return ".sql" in inventory.files_by_ext or any(
            "postgres" in f.relative_path.lower() or "mysql" in f.relative_path.lower() or "schema" in f.relative_path.lower()
            for f in inventory.files
        )

    def supported_capabilities(self) -> List[str]:
        return [
            "sql_table_ddl_extraction",
            "database_entity_graph",
            "migration_timeline_analysis",
        ]


class RESTApiAnalyzer(AnalyzerInterface):
    @property
    def name(self) -> str:
        return "rest_api_analyzer"

    @property
    def display_name(self) -> str:
        return "REST & OpenAPI Endpoint Analyzer"

    @property
    def supported_languages(self) -> List[str]:
        return ["json", "yaml", "python", "java", "typescript", "go"]

    @property
    def supported_frameworks(self) -> List[str]:
        return ["openapi", "swagger", "fastapi", "spring-boot", "express"]

    @property
    def capability_level(self) -> int:
        return 3  # Level 3: API analysis

    def detect(self, inventory: FileInventory) -> bool:
        return any(
            "openapi" in f.file_name.lower() or "swagger" in f.file_name.lower()
            for f in inventory.files
        )

    def supported_capabilities(self) -> List[str]:
        return [
            "openapi_specification_parsing",
            "endpoint_route_inventory",
            "schema_contract_mapping",
        ]


# ====================================================================
# CAPABILITY REGISTRY
# ====================================================================

class CapabilityRegistry:
    """Central registry for discovering capabilities and matching analyzers."""

    def __init__(self):
        self._analyzers: Dict[str, AnalyzerInterface] = {}
        self._register_default_analyzers()

    def _register_default_analyzers(self):
        self.register(PythonAnalyzer())
        self.register(JavaAnalyzer())
        self.register(TypeScriptAnalyzer())
        self.register(GoAnalyzer())
        self.register(CppAnalyzer())
        self.register(CobolAnalyzer())
        self.register(DockerAnalyzer())
        self.register(DatabaseAnalyzer())
        self.register(RESTApiAnalyzer())

    def register(self, analyzer: AnalyzerInterface) -> None:
        self._analyzers[analyzer.name] = analyzer

    def get_analyzer(self, name: str) -> Optional[AnalyzerInterface]:
        return self._analyzers.get(name)

    def list_analyzers(self) -> List[AnalyzerInterface]:
        return list(self._analyzers.values())

    def match_analyzers(self, inventory: FileInventory) -> List[AnalyzerInterface]:
        """Deterministically match which analyzers apply to this file inventory."""
        matched = []
        for analyzer in self._analyzers.values():
            if analyzer.detect(inventory):
                matched.append(analyzer)
        return matched

    def get_capabilities_for_language(self, language: str) -> CapabilitySpec:
        lang_lower = language.lower()
        level_map = {
            "python": (4, "SUPPORTED", "python_analyzer", "Deep semantic AST, callgraph, dependencies, tests"),
            "java": (4, "SUPPORTED", "java_analyzer", "Deep semantic AST, Maven/Gradle, Spring, JUnit"),
            "typescript": (4, "SUPPORTED", "typescript_analyzer", "Deep semantic AST, npm/pnpm, React/Express/Nest"),
            "javascript": (4, "SUPPORTED", "typescript_analyzer", "AST parsing, npm dependencies, route detection"),
            "go": (3, "SUPPORTED", "go_analyzer", "AST parsing, go.mod dependencies, Go test discovery"),
            "c": (2, "SUPPORTED", "cpp_analyzer", "Header include graph, Makefile target resolution"),
            "cpp": (2, "SUPPORTED", "cpp_analyzer", "Header include graph, CMake target resolution"),
            "cobol": (1, "SUPPORTED", "cobol_analyzer", "Division parsing, copybook inclusion graph"),
            "fortran": (1, "PARTIAL", None, "Structural module and subroutine detection"),
            "rust": (2, "PARTIAL", None, "Cargo manifest parsing, struct/function structure"),
            "csharp": (2, "PARTIAL", None, "C# project solution scanning"),
            "php": (2, "PARTIAL", None, "Composer manifest and script structure"),
            "ruby": (2, "PARTIAL", None, "Gemfile and class/module structure"),
            "sql": (2, "SUPPORTED", "database_analyzer", "DDL table definitions and entity mapping"),
            "dockerfile": (2, "SUPPORTED", "docker_analyzer", "Multi-stage build and image topology"),
            "yaml": (2, "SUPPORTED", "docker_analyzer", "Configuration and compose service topology"),
            "json": (1, "SUPPORTED", None, "Configuration and schema extraction"),
        }
        if lang_lower in level_map:
            level, status, analyzer, desc = level_map[lang_lower]
            return CapabilitySpec(
                capability_name=f"{lang_lower}_analysis",
                category="language",
                level=level,
                status=status,
                analyzer_name=analyzer,
                description=desc,
            )
        return CapabilitySpec(
            capability_name=f"{lang_lower}_analysis",
            category="language",
            level=0,
            status="UNSUPPORTED",
            analyzer_name=None,
            description=f"Detection only for {language}. Structural analyzer pending registration.",
        )


capability_registry = CapabilityRegistry()
