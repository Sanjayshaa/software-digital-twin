from abc import ABC, abstractmethod
from typing import List, Tuple, Optional
from app.services.discovery.scanner import FileInventory, ScannedFile
from app.services.analysis.runtime.context import AnalysisContext
from app.services.analysis.runtime.result import (
    ExtractedArtifact,
    ExtractedRelationship,
    ExtractedEvidence,
)
from app.services.discovery.registry import AnalyzerInterface


class StructuralAnalyzerBase(AnalyzerInterface, ABC):
    """Base class for all Phase 3 structural intelligence analyzers."""

    @abstractmethod
    def analyze_repository(
        self,
        context: AnalysisContext,
        inventory: FileInventory
    ) -> Tuple[List[ExtractedArtifact], List[ExtractedRelationship], List[ExtractedEvidence], List[str]]:
        """
        Execute deterministic structural extraction across relevant files in the inventory.
        Returns (artifacts, relationships, evidence, warnings).
        """
        pass
