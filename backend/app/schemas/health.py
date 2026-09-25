from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class HealthResponse(BaseModel):
    status: str = Field(default="healthy", description="Application status")
    version: str = Field(..., description="Application version")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    environment: str = Field(..., description="Current environment")


class ReadinessResponse(BaseModel):
    status: str = Field(..., description="Readiness status: ready or not_ready")
    database: str = Field(..., description="Database connectivity status")
    details: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
