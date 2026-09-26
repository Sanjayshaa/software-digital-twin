from typing import List, Dict, Optional
from app.services.discovery.models import AnalysisPlanResult
from app.services.discovery.scanner import FileInventory
from app.services.analysis.analyzers.base import StructuralAnalyzerBase
from app.services.analysis.analyzers.python_analyzer import PythonStructuralAnalyzer
from app.services.analysis.analyzers.java_analyzer import JavaStructuralAnalyzer
from app.services.analysis.analyzers.typescript_analyzer import TypeScriptStructuralAnalyzer
from app.services.analysis.analyzers.javascript_analyzer import JavaScriptStructuralAnalyzer
from app.services.analysis.analyzers.secondary_analyzers import (
    CobolStructuralAnalyzer,
    CppStructuralAnalyzer,
    DatabaseStructuralAnalyzer,
    DockerStructuralAnalyzer,
)


class AnalyzerDispatcher:
    """Dispatches analysis execution to registered structural analyzers matching the plan."""

    def __init__(self):
        self._analyzers: Dict[str, StructuralAnalyzerBase] = {}
        self._register_default_analyzers()

    def _register_default_analyzers(self):
        analyzers = [
            PythonStructuralAnalyzer(),
            JavaStructuralAnalyzer(),
            TypeScriptStructuralAnalyzer(),
            JavaScriptStructuralAnalyzer(),
            CobolStructuralAnalyzer(),
            CppStructuralAnalyzer(),
            DatabaseStructuralAnalyzer(),
            DockerStructuralAnalyzer(),
        ]
        for a in analyzers:
            self._analyzers[a.name] = a

    def get_analyzer(self, name: str) -> Optional[StructuralAnalyzerBase]:
        return self._analyzers.get(name)

    def select_analyzers_for_plan(
        self,
        plan: AnalysisPlanResult,
        inventory: FileInventory
    ) -> List[StructuralAnalyzerBase]:
        """Selects uniquely matched analyzers from the planned steps and inventory."""
        selected: Dict[str, StructuralAnalyzerBase] = {}

        # 1. Check analyzers directly referenced in the analysis plan steps
        for step in plan.steps:
            an_name = step.analyzer_name
            # Direct match
            if an_name in self._analyzers:
                selected[an_name] = self._analyzers[an_name]
            # Mappings for generic step names
            elif "python" in an_name and "python_analyzer" in self._analyzers:
                selected["python_analyzer"] = self._analyzers["python_analyzer"]
            elif "java" in an_name and "java_analyzer" in self._analyzers:
                selected["java_analyzer"] = self._analyzers["java_analyzer"]
            elif "typescript" in an_name and "typescript_analyzer" in self._analyzers:
                selected["typescript_analyzer"] = self._analyzers["typescript_analyzer"]
            elif "cobol" in an_name and "cobol_analyzer" in self._analyzers:
                selected["cobol_analyzer"] = self._analyzers["cobol_analyzer"]
            elif ("cpp" in an_name or "c_" in an_name) and "cpp_analyzer" in self._analyzers:
                selected["cpp_analyzer"] = self._analyzers["cpp_analyzer"]
            elif ("database" in an_name or "sql" in an_name) and "database_analyzer" in self._analyzers:
                selected["database_analyzer"] = self._analyzers["database_analyzer"]
            elif "docker" in an_name and "docker_analyzer" in self._analyzers:
                selected["docker_analyzer"] = self._analyzers["docker_analyzer"]

        # 2. Also verify against inventory detection
        for an in self._analyzers.values():
            if an.detect(inventory) and an.name not in selected:
                selected[an.name] = an

        return list(selected.values())


analyzer_dispatcher = AnalyzerDispatcher()
