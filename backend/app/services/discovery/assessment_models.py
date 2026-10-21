"""
Phase 9 — Project Discovery & Technical Assessment Models.
Defines data structures for Discovery Completeness, 9-Dimensional Technical Health,
Structured Evidence Findings, and Advisory Remediation Roadmaps.
"""

from enum import Enum
from typing import List, Dict, Any, Optional, Set
from datetime import datetime
from pydantic import BaseModel, Field


# Canonical source code file extensions supported by AST structural analysis and Twin extraction
SUPPORTED_SOURCE_EXTENSIONS: Set[str] = {
    ".py", ".pyw",
    ".ts", ".tsx",
    ".js", ".jsx", ".mjs", ".cjs",
    ".java",
    ".go",
    ".rs",
    ".c", ".h", ".cpp", ".hpp", ".cc", ".cxx",
}

# Canonical alias for backwards compatibility across assessment engine methods
SUPPORTED_EXTS: Set[str] = SUPPORTED_SOURCE_EXTENSIONS

# Documentation file extensions
DOCUMENTATION_EXTENSIONS: Set[str] = {
    ".md", ".markdown", ".mdown", ".mkdn",
    ".rst",
    ".txt",
    ".adoc", ".asciidoc",
    ".pdf",
    ".doc", ".docx",
}

# Asset / binary / transient artifact extensions to skip from code analysis
SKIPPED_EXTENSIONS: Set[str] = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp", ".bmp", ".tiff",
    ".lock", ".log", ".map",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".mp3", ".mp4", ".wav", ".avi", ".mov",
    ".zip", ".tar", ".gz", ".bz2", ".7z",
    ".bin", ".exe", ".dll", ".so", ".dylib",
}

# Configuration, build manifest, and environment declaration file extensions
CONFIGURATION_EXTENSIONS: Set[str] = {
    ".toml", ".yaml", ".yml", ".json", ".xml", ".ini", ".cfg", ".conf",
    ".properties", ".env", ".gradle",
}


class DiscoveryStatus(str, Enum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    UNSUPPORTED = "UNSUPPORTED"
    NOT_EVALUATED = "NOT_EVALUATED"


class FindingCategory(str, Enum):
    ARCHITECTURE = "ARCHITECTURE"
    COUPLING = "COUPLING"
    API_INTERFACE = "API_INTERFACE"
    TEST_COVERAGE = "TEST_COVERAGE"
    CHANGE_IMPACT = "CHANGE_IMPACT"
    CONFIGURATION = "CONFIGURATION"
    MAINTENANCE = "MAINTENANCE"
    RUNTIME_INCIDENT = "RUNTIME_INCIDENT"


class FindingSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class RoadmapPriority(str, Enum):
    P0_IMMEDIATE = "P0_IMMEDIATE"
    P1_HIGH = "P1_HIGH"
    P2_MEDIUM = "P2_MEDIUM"
    P3_LONG_TERM = "P3_LONG_TERM"


class DiscoveryCompleteness(BaseModel):
    status: DiscoveryStatus = Field(..., description="Overall discovery evaluation status")
    files_discovered: int = Field(0, description="Total files discovered on disk or in repository tree")
    files_analyzed: int = Field(0, description="Files successfully parsed into structural AST artifacts")
    files_skipped: int = Field(0, description="Files intentionally skipped (vendor, dist, generated, binary)")
    files_unsupported: int = Field(0, description="Files in languages without supported AST extraction")
    analysis_failures: int = Field(0, description="Files that encountered errors during parsing")
    symbols_extracted: int = Field(0, description="Total classes, methods, functions, and services extracted")
    relationships_extracted: int = Field(0, description="Total calls, imports, tests, and dependencies indexed")
    tests_discovered: int = Field(0, description="Total test cases and test suites identified")
    tests_linked: int = Field(0, description="Tests deterministically linked to tested source components")
    coverage_percentage: float = Field(0.0, description="Percentage of code files covered by AST analysis")
    unsupported_extensions: List[str] = Field(default_factory=list, description="Extensions of unsupported files")
    explanation: str = Field(..., description="Transparent statement of analysis scope and limitations")

    @property
    def notes(self) -> str:
        return self.explanation


class AssessmentFinding(BaseModel):
    finding_id: str = Field(..., description="Stable unique identifier, e.g. FIND-ARCH-001")
    category: FindingCategory = Field(..., description="Technical assessment dimension")
    severity: FindingSeverity = Field(..., description="Critical, High, Medium, Low, Info")
    title: str = Field(..., description="Concise, actionable finding title")
    description: str = Field(..., description="Detailed technical description of observed condition")
    rationale: str = Field(..., description="Why this finding matters to system stability or maintainability")
    affected_entities: List[str] = Field(default_factory=list, description="Qualified names or IDs of affected entities")
    affected_files: List[str] = Field(default_factory=list, description="Relative paths of affected source files")
    evidence_references: List[Dict[str, Any]] = Field(default_factory=list, description="Explicit proof items")
    detection_method: str = Field(..., description="Method used: ast_inspection, graph_traversal, manifest_audit")
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Confidence in this finding (0.0 to 1.0)")
    known_limitations: str = Field(..., description="Analysis limitations or boundary conditions")
    recommended_action: str = Field(..., description="Concrete, actionable remediation step")

    @property
    def id(self) -> str:
        return self.finding_id

    @property
    def affected_entity(self) -> str:
        return self.affected_entities[0] if self.affected_entities else ""


class DimensionalScore(BaseModel):
    dimension_name: str = Field(..., description="Name of the technical dimension evaluated")
    score: float = Field(..., ge=0.0, le=100.0, description="Deterministic score 0-100 (100 is optimal)")
    status: str = Field(..., description="HEALTHY, ATTENTION, AT_RISK, UNKNOWN")
    summary: str = Field(..., description="Explainable description of dimension findings")
    key_metrics: Dict[str, Any] = Field(default_factory=dict, description="Underlying metric evidence")


class RoadmapRecommendation(BaseModel):
    recommendation_id: str = Field(..., description="Unique recommendation ID, e.g. REC-001")
    priority: RoadmapPriority = Field(..., description="P0_IMMEDIATE, P1_HIGH, P2_MEDIUM, P3_LONG_TERM")
    title: str = Field(..., description="Actionable title for recommendation")
    supporting_finding_ids: List[str] = Field(default_factory=list, description="Finding IDs justifying this item")
    affected_components: List[str] = Field(default_factory=list, description="Components or files targeted")
    technical_rationale: str = Field(..., description="Why this action is recommended")
    expected_benefit: str = Field(..., description="Measurable benefit (e.g. reduce blast radius, close test gap)")
    implementation_considerations: List[str] = Field(default_factory=list, description="Implementation steps and risks")
    dependencies_or_prerequisites: List[str] = Field(default_factory=list, description="Prerequisite changes")
    verification_criteria: str = Field(..., description="How to independently verify remediation success")
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Confidence score")
    known_limitations: str = Field(..., description="Advisory scope limitations")


class TechnicalAssessmentResult(BaseModel):
    assessment_id: str = Field(..., description="Unique assessment ID")
    repository_id: str = Field(..., description="Repository UUID")
    repository_name: str = Field(..., description="Repository name")
    snapshot_id: str = Field(..., description="Snapshot UUID")
    commit_hash: str = Field(..., description="Exact 40-character commit hash")
    assessed_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    completeness: DiscoveryCompleteness
    dimensional_scores: List[DimensionalScore]
    findings: List[AssessmentFinding]
    roadmap: List[RoadmapRecommendation]
    executive_summary: str
    report_markdown: Optional[str] = None
    markdown_content: Optional[str] = None

    @property
    def status(self) -> DiscoveryStatus:
        return self.completeness.status

    @property
    def roadmap_recommendations(self) -> List[RoadmapRecommendation]:
        return self.roadmap
