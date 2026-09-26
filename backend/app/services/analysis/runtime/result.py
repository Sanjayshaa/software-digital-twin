from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class ArtifactType(str, Enum):
    MODULE = "MODULE"
    PACKAGE = "PACKAGE"
    CLASS = "CLASS"
    INTERFACE = "INTERFACE"
    FUNCTION = "FUNCTION"
    METHOD = "METHOD"
    CONSTRUCTOR = "CONSTRUCTOR"
    API_ENDPOINT = "API_ENDPOINT"
    DATABASE_ENTITY = "DATABASE_ENTITY"
    CONFIG_ENTITY = "CONFIG_ENTITY"
    TEST_CASE = "TEST_CASE"
    COBOL_DIVISION = "COBOL_DIVISION"
    DOCKER_STAGE = "DOCKER_STAGE"
    CPP_STRUCT = "CPP_STRUCT"
    CPP_NAMESPACE = "CPP_NAMESPACE"
    SQL_TABLE = "SQL_TABLE"
    SQL_VIEW = "SQL_VIEW"
    EXTERNAL_DEPENDENCY = "EXTERNAL_DEPENDENCY"
    SYMBOL = "SYMBOL"


class RelationshipType(str, Enum):
    CONTAINS = "CONTAINS"
    IMPORTS = "IMPORTS"
    EXPORTS = "EXPORTS"
    CALLS = "CALLS"
    EXTENDS = "EXTENDS"
    IMPLEMENTS = "IMPLEMENTS"
    REFERENCES = "REFERENCES"
    DEPENDS_ON = "DEPENDS_ON"
    EXPOSES = "EXPOSES"
    CONSUMES = "CONSUMES"
    PERSISTS_TO = "PERSISTS_TO"
    CONFIGURES = "CONFIGURES"
    TESTS = "TESTS"
    PART_OF = "PART_OF"
    INCLUDES = "INCLUDES"
    COPY_DEPENDS_ON = "COPY_DEPENDS_ON"
    USES = "USES"


class ExtractedArtifact(BaseModel):
    id: str = Field(..., description="Stable deterministic identifier")
    artifact_type: ArtifactType
    language: str
    name: str
    qualified_name: str
    file_path: str
    signature: Optional[str] = None
    docstring: Optional[str] = None
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    source_hash: Optional[str] = None
    analyzer_source: str
    confidence: float = 1.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ExtractedRelationship(BaseModel):
    id: str = Field(..., description="Stable deterministic identifier")
    source_qualified_name: str
    target_qualified_name: str
    relationship_type: RelationshipType
    confidence: float = 1.0
    detection_method: str
    source_location: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ExtractedEvidence(BaseModel):
    source_reference: str
    description: str
    confidence: float = 1.0
    payload: Dict[str, Any] = Field(default_factory=dict)


class AnalysisRunResult(BaseModel):
    run_id: str
    repository_id: str
    snapshot_id: str
    status: str = "COMPLETED"  # PENDING, RUNNING, COMPLETED, PARTIAL, FAILED
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    analyzer_names: List[str] = Field(default_factory=list)
    files_scanned: int = 0
    artifacts: List[ExtractedArtifact] = Field(default_factory=list)
    relationships: List[ExtractedRelationship] = Field(default_factory=list)
    evidence_items: List[ExtractedEvidence] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)

    @property
    def evidence(self) -> List[ExtractedEvidence]:
        return self.evidence_items
