from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, field_validator
from datetime import datetime


class RuntimeEventType(str, Enum):
    REQUEST = "REQUEST"
    TRACE = "TRACE"
    SPAN = "SPAN"
    LOG = "LOG"
    ERROR = "ERROR"
    EXCEPTION = "EXCEPTION"
    DEPLOYMENT = "DEPLOYMENT"
    STARTUP = "STARTUP"
    SHUTDOWN = "SHUTDOWN"
    HEALTH_CHECK = "HEALTH_CHECK"
    DATABASE_EVENT = "DATABASE_EVENT"
    EXTERNAL_CALL = "EXTERNAL_CALL"
    CUSTOM = "CUSTOM"


class RuntimeSeverity(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


MAX_EVENT_PAYLOAD_BYTES = 100 * 1024  # 100 KB limit per event


class RawRuntimeEvent(BaseModel):
    timestamp: Optional[datetime] = None
    event_type: str = "LOG"
    service: Optional[str] = None
    service_name: Optional[str] = None
    environment: str = "production"
    severity: str = "INFO"
    message: Optional[str] = None
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    request_id: Optional[str] = None
    commit_sha: Optional[str] = None
    snapshot_id: Optional[str] = None
    attributes: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("attributes")
    @classmethod
    def validate_attributes_size(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        import json
        try:
            payload_str = json.dumps(v)
            if len(payload_str.encode("utf-8")) > MAX_EVENT_PAYLOAD_BYTES:
                raise ValueError(f"Event attributes size exceeds {MAX_EVENT_PAYLOAD_BYTES} bytes limit.")
        except (TypeError, OverflowError) as e:
            raise ValueError(f"Invalid JSON serializable attributes: {e}")
        return v

    @field_validator("message")
    @classmethod
    def validate_message_size(cls, v: Optional[str]) -> Optional[str]:
        if v and len(v.encode("utf-8")) > MAX_EVENT_PAYLOAD_BYTES:
            raise ValueError(f"Event message size exceeds {MAX_EVENT_PAYLOAD_BYTES} bytes limit.")
        return v


class NormalizedRuntimeEvent(BaseModel):
    id: str
    project_id: str
    repository_id: Optional[str] = None
    snapshot_id: Optional[str] = None
    incident_id: Optional[str] = None
    service_name: Optional[str] = None
    component_artifact_id: Optional[str] = None
    event_type: str
    severity: str
    environment: str
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    message: Optional[str] = None
    correlation_confidence: float = 0.0
    correlation_method: str = "UNMATCHED"
    payload: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime

    @property
    def confidence(self) -> float:
        """Alias for correlation_confidence for API consistency."""
        return self.correlation_confidence


class RuntimeIngestRequest(BaseModel):
    events: List[RawRuntimeEvent] = Field(..., max_length=5000)
    snapshot_id: Optional[str] = None
    environment: Optional[str] = None


class RuntimeIngestResult(BaseModel):
    repository_id: str
    ingested_count: int
    correlated_count: int
    redacted_count: int
    skipped_count: int
    event_ids: List[str] = Field(default_factory=list)
    execution_time_ms: float = 0.0


class RuntimeEventPage(BaseModel):
    total: int
    limit: int
    offset: int
    events: List[NormalizedRuntimeEvent] = Field(default_factory=list)
