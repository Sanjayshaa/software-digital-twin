from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class AnalysisContext(BaseModel):
    """Execution context passed through the Analyzer Runtime."""

    repository_id: str
    repository_path: str
    snapshot_id: str
    commit_hash: str = "HEAD"
    branch_name: str = "main"
    project_id: Optional[str] = None
    options: Dict[str, Any] = Field(default_factory=dict)
    run_id: Optional[str] = None
