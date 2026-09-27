from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class ProcessEvidenceStatus(str, Enum):
    OBSERVED = "OBSERVED"
    DERIVED = "DERIVED"
    INFERRED = "INFERRED"
    UNKNOWN = "UNKNOWN"


class ProcessTransitionType(str, Enum):
    CALLS = "CALLS"
    DEPENDS_ON = "DEPENDS_ON"
    EXPOSES = "EXPOSES"
    CONSUMES = "CONSUMES"
    PERSISTS_TO = "PERSISTS_TO"
    TESTS = "TESTS"
    TRANSITIONS_TO = "TRANSITIONS_TO"


class ProcessStepModel(BaseModel):
    id: str
    process_id: str
    step_order: int
    name: str
    component_artifact_id: Optional[str] = None
    step_type: str = "action"  # entrypoint, action, database_op, external_call, validation
    operation: Optional[str] = None
    source_file: Optional[str] = None
    line_number: Optional[int] = None
    confidence: float = 0.85
    evidence_status: ProcessEvidenceStatus = ProcessEvidenceStatus.INFERRED
    detection_method: str = "STATIC_AST_CALL_CHAIN"
    metadata_payload: Dict[str, Any] = Field(default_factory=dict)


class ProcessTransitionModel(BaseModel):
    id: str
    process_id: str
    from_step_id: str
    to_step_id: str
    transition_type: str = "CALLS"
    transition_condition: Optional[str] = None
    confidence: float = 0.85
    evidence_status: ProcessEvidenceStatus = ProcessEvidenceStatus.INFERRED
    metadata_payload: Dict[str, Any] = Field(default_factory=dict)


class ProcessModel(BaseModel):
    id: str
    project_id: str
    repository_id: str
    snapshot_id: str
    name: str
    description: Optional[str] = None
    process_type: str = "business_process"
    evidence_status: ProcessEvidenceStatus = ProcessEvidenceStatus.INFERRED
    confidence: float = 0.85
    steps_count: int = 0
    transitions_count: int = 0
    steps: List[ProcessStepModel] = Field(default_factory=list)
    transitions: List[ProcessTransitionModel] = Field(default_factory=list)
    metadata_payload: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ProcessDiscoveryResult(BaseModel):
    repository_id: str
    snapshot_id: str
    total_processes: int
    total_steps: int
    total_transitions: int
    processes: List[ProcessModel] = Field(default_factory=list)
    execution_time_ms: float = 0.0
