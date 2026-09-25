from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class EvidenceType(str, Enum):
    OBSERVED = "OBSERVED"
    INFERRED = "INFERRED"
    UNKNOWN = "UNKNOWN"


class EvidenceItem(BaseModel):
    evidence_type: EvidenceType = Field(..., description="OBSERVED, INFERRED, or UNKNOWN")
    file_path: Optional[str] = Field(None, description="Relative path to file providing evidence")
    line_number: Optional[int] = Field(None, description="Line number if applicable")
    snippet: Optional[str] = Field(None, description="Code or config snippet")
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Confidence score 0.0 to 1.0")
    detection_rule: str = Field(..., description="Rule or detector identifier that found this")


class LanguageStat(BaseModel):
    name: str = Field(..., description="Normalized language name")
    percentage: float = Field(..., ge=0.0, le=100.0, description="Percentage of codebase lines")
    confidence: float = Field(..., ge=0.0, le=1.0)
    line_count: int = Field(default=0)
    file_count: int = Field(default=0)
    capability_level: int = Field(default=0, ge=0, le=4, description="Current supported capability level (0-4)")
    evidence: List[EvidenceItem] = Field(default_factory=list)


class FrameworkStat(BaseModel):
    name: str = Field(..., description="Framework name (e.g. spring-boot, fastapi, react)")
    version: Optional[str] = Field(None, description="Detected version if available")
    confidence: float = Field(..., ge=0.0, le=1.0)
    detection_status: EvidenceType = Field(default=EvidenceType.OBSERVED)
    evidence: List[EvidenceItem] = Field(default_factory=list)


class BuildSystemStat(BaseModel):
    name: str = Field(..., description="Build system (e.g. maven, gradle, npm, cargo, cmake)")
    build_file: Optional[str] = None
    confidence: float = Field(1.0, ge=0.0, le=1.0)
    evidence: List[EvidenceItem] = Field(default_factory=list)


class PackageManagerStat(BaseModel):
    name: str = Field(..., description="Package manager (e.g. pip, npm, yarn, pnpm, cargo, maven)")
    manifest_file: Optional[str] = None
    confidence: float = Field(1.0, ge=0.0, le=1.0)
    evidence: List[EvidenceItem] = Field(default_factory=list)


class DatabaseStat(BaseModel):
    name: str = Field(..., description="Database name (e.g. postgresql, mysql, mongodb, redis)")
    category: str = Field("sql", description="sql, nosql, cache, timeseries")
    confidence: float = Field(..., ge=0.0, le=1.0)
    detection_status: EvidenceType = Field(default=EvidenceType.OBSERVED)
    evidence: List[EvidenceItem] = Field(default_factory=list)


class APITechnologyStat(BaseModel):
    name: str = Field(..., description="API technology (e.g. rest, openapi, graphql, grpc, soap)")
    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence: List[EvidenceItem] = Field(default_factory=list)


class TestingFrameworkStat(BaseModel):
    name: str = Field(..., description="Testing framework (e.g. junit, pytest, vitest, jest, gotest)")
    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence: List[EvidenceItem] = Field(default_factory=list)


class InfrastructureStat(BaseModel):
    name: str = Field(..., description="Infrastructure tech (e.g. docker, docker-compose, k8s, github-actions, terraform)")
    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence: List[EvidenceItem] = Field(default_factory=list)


class ArchitectureSignal(BaseModel):
    signal: str = Field(..., description="Architecture pattern signal")
    confidence: float = Field(..., ge=0.0, le=1.0)
    summary: str = Field(..., description="Transparent evidence-based explanation")
    evidence: List[EvidenceItem] = Field(default_factory=list)


class ProjectProfile(BaseModel):
    repository_path: str
    scan_timestamp: datetime = Field(default_factory=datetime.utcnow)
    total_files_scanned: int = 0
    total_lines_of_code: int = 0
    languages: List[LanguageStat] = Field(default_factory=list)
    frameworks: List[FrameworkStat] = Field(default_factory=list)
    build_systems: List[BuildSystemStat] = Field(default_factory=list)
    package_managers: List[PackageManagerStat] = Field(default_factory=list)
    databases: List[DatabaseStat] = Field(default_factory=list)
    api_technologies: List[APITechnologyStat] = Field(default_factory=list)
    testing_frameworks: List[TestingFrameworkStat] = Field(default_factory=list)
    infrastructure: List[InfrastructureStat] = Field(default_factory=list)
    architecture_signals: List[ArchitectureSignal] = Field(default_factory=list)
    raw_inventory: Dict[str, Any] = Field(default_factory=dict)


class CapabilitySpec(BaseModel):
    capability_name: str
    category: str
    level: int = Field(ge=0, le=4)
    status: str = Field(..., description="SUPPORTED, PARTIAL, UNSUPPORTED")
    analyzer_name: Optional[str] = None
    description: str


class AnalysisPlanStep(BaseModel):
    step_number: int
    step_name: str
    analyzer_name: str
    target_technology: str
    capability_level: int
    description: str
    prerequisites: List[str] = Field(default_factory=list)
    evidence_required: List[str] = Field(default_factory=list)


class AnalysisPlanResult(BaseModel):
    repository_path: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    project_profile_summary: Dict[str, Any]
    total_steps: int
    steps: List[AnalysisPlanStep] = Field(default_factory=list)
    supported_capabilities: List[CapabilitySpec] = Field(default_factory=list)
    unsupported_capabilities: List[CapabilitySpec] = Field(default_factory=list)
