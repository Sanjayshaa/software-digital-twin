from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime


import json

MAX_INCIDENT_PAYLOAD_BYTES = 100 * 1024  # 100 KB max for incident metadata


class IncidentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=5000)
    severity: str = Field("medium", max_length=32)  # low, medium, high, critical
    environment: str = Field("production", max_length=64)
    affected_component_id: Optional[str] = Field(None, max_length=255)
    affected_component_name: Optional[str] = Field(None, max_length=255)
    snapshot_id: Optional[str] = Field(None, max_length=255)
    detected_at: Optional[datetime] = None
    event_ids: List[str] = Field(default_factory=list, max_length=1000)
    metadata_payload: Dict[str, Any] = Field(default_factory=dict)

    def validate_payload_size(self):
        try:
            dumped = json.dumps(self.metadata_payload)
            if len(dumped.encode("utf-8")) > MAX_INCIDENT_PAYLOAD_BYTES:
                raise ValueError(f"Incident metadata_payload exceeds maximum {MAX_INCIDENT_PAYLOAD_BYTES} bytes.")
        except (TypeError, OverflowError) as exc:
            raise ValueError(f"Invalid JSON metadata payload: {exc}")



class IncidentEvidenceLinkModel(BaseModel):
    id: str
    incident_id: str
    link_type: str
    target_id: str
    target_type: str
    confidence: float
    explanation: Optional[str] = None
    created_at: datetime


class IncidentResponse(BaseModel):
    id: str
    project_id: str
    repository_id: Optional[str] = None
    snapshot_id: Optional[str] = None
    title: str
    description: Optional[str] = None
    severity: str
    status: str
    environment: str
    affected_component_id: Optional[str] = None
    affected_component_name: Optional[str] = None
    detected_at: datetime
    resolved_at: Optional[datetime] = None
    evidence_links_count: int = 0
    evidence_ids: List[str] = Field(default_factory=list)  # IDs of linked RuntimeEvent records
    metadata_payload: Dict[str, Any] = Field(default_factory=dict)


class CandidateCausalPath(BaseModel):
    path_id: str
    changed_artifact_id: str
    changed_artifact_name: str
    change_type: str  # MODIFIED, ADDED, REMOVED
    target_incident_artifact_id: str
    hop_count: int
    path_nodes: List[Dict[str, Any]] = Field(default_factory=list)
    confidence: float
    explanation: str
    evidence_status: str = "DERIVED"
    # Convenience fields for the affected/target component
    component_id: Optional[str] = None   # Alias for target_incident_artifact_id
    component_name: Optional[str] = None  # Name of the affected incident component
    relationship: Optional[str] = None   # Relationship type (e.g., CALLS, DIRECT)


class InvestigationResult(BaseModel):
    incident_id: str
    incident_title: str
    severity: str
    environment: str
    # Full incident response object for callers that need it
    incident: Optional["IncidentResponse"] = None
    affected_component: Optional[Dict[str, Any]] = None
    # observed_evidence is the primary name; observed_runtime_events is kept as an alias
    observed_evidence: List[Dict[str, Any]] = Field(default_factory=list)
    observed_runtime_events: List[Dict[str, Any]] = Field(default_factory=list)
    # affected_entities contains structural artifact info for affected components
    affected_entities: List[Dict[str, Any]] = Field(default_factory=list)
    affected_processes: List[Dict[str, Any]] = Field(default_factory=list)
    candidate_recent_changes: List[Dict[str, Any]] = Field(default_factory=list)
    candidate_causal_paths: List[CandidateCausalPath] = Field(default_factory=list)
    related_tests: List[Dict[str, Any]] = Field(default_factory=list)
    # uncertainties lists gaps/caveats in the investigation
    uncertainties: List[str] = Field(default_factory=list)
    supporting_evidence_summary: Dict[str, Any] = Field(default_factory=dict)
    investigation_timestamp: datetime
    disclaimer: str = (
        "Candidate causal paths represent evidence-backed hypotheses derived from structural and runtime correlations. "
        "They do not constitute deterministic proof of operational causality."
    )
