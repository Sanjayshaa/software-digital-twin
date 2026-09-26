from typing import List, Tuple
from app.services.discovery.scanner import FileInventory
from app.services.analysis.runtime.context import AnalysisContext
from app.services.analysis.runtime.result import (
    ExtractedArtifact,
    ExtractedRelationship,
    ExtractedEvidence,
)
from app.services.analysis.analyzers.typescript_analyzer import TypeScriptStructuralAnalyzer


class JavaScriptStructuralAnalyzer(TypeScriptStructuralAnalyzer):
    """Deep structural AST analyzer for Node.js & modern JavaScript projects."""

    def __init__(self):
        super().__init__(parser_lang="javascript")

    @property
    def name(self) -> str:
        return "javascript_analyzer"

    @property
    def display_name(self) -> str:
        return "JavaScript Deep Structural Analyzer"

    @property
    def supported_languages(self) -> List[str]:
        return ["javascript"]

    def detect(self, inventory: FileInventory) -> bool:
        return any(ext in inventory.files_by_ext for ext in [".js", ".jsx", ".mjs", ".cjs"])
