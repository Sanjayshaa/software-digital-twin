import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


# ====================================================================
# 1. CORE REPOSITORY & PROJECT ENTITIES
# ====================================================================

class Project(Base):
    __tablename__ = "projects"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    repositories = relationship("Repository", back_populates="project", cascade="all, delete-orphan")
    services = relationship("Service", back_populates="project", cascade="all, delete-orphan")
    tests = relationship("Test", back_populates="project", cascade="all, delete-orphan")
    changes = relationship("Change", back_populates="project", cascade="all, delete-orphan")
    scenarios = relationship("Scenario", back_populates="project", cascade="all, delete-orphan")
    risk_assessments = relationship("RiskAssessment", back_populates="project", cascade="all, delete-orphan")
    analysis_runs = relationship("AnalysisRun", back_populates="project", cascade="all, delete-orphan")
    evidence_items = relationship("Evidence", back_populates="project", cascade="all, delete-orphan")


class Repository(Base):
    __tablename__ = "repositories"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    vcs_type = Column(String(50), default="git", nullable=False)
    remote_url = Column(String(1024), nullable=True)
    local_path = Column(String(1024), nullable=False)
    default_branch = Column(String(100), default="main", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    project = relationship("Project", back_populates="repositories")
    branches = relationship("Branch", back_populates="repository", cascade="all, delete-orphan")
    commits = relationship("Commit", back_populates="repository", cascade="all, delete-orphan")
    snapshots = relationship("RepositorySnapshot", back_populates="repository", cascade="all, delete-orphan")
    files = relationship("File", back_populates="repository", cascade="all, delete-orphan")


class RepositorySnapshot(Base):
    __tablename__ = "repository_snapshots"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    repository_id = Column(String(36), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    commit_hash = Column(String(64), nullable=False, index=True)
    branch_name = Column(String(100), nullable=False)
    total_files = Column(Integer, default=0, nullable=False)
    total_symbols = Column(Integer, default=0, nullable=False)
    snapshot_metadata = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    repository = relationship("Repository", back_populates="snapshots")
    files = relationship("File", back_populates="snapshot", cascade="all, delete-orphan")


class Branch(Base):
    __tablename__ = "branches"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    repository_id = Column(String(36), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    head_commit_hash = Column(String(64), nullable=True)
    is_default = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    repository = relationship("Repository", back_populates="branches")


class Commit(Base):
    __tablename__ = "commits"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    repository_id = Column(String(36), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    commit_hash = Column(String(64), nullable=False, index=True)
    author = Column(String(255), nullable=True)
    message = Column(Text, nullable=True)
    committed_at = Column(DateTime, nullable=True)
    parent_hashes = Column(JSON, default=list, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    repository = relationship("Repository", back_populates="commits")
    changes = relationship("Change", back_populates="commit")
    test_executions = relationship("TestExecution", back_populates="commit")


class Change(Base):
    __tablename__ = "changes"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    repository_id = Column(String(36), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=True, index=True)
    commit_id = Column(String(36), ForeignKey("commits.id", ondelete="SET NULL"), nullable=True, index=True)
    change_type = Column(String(50), default="diff", nullable=False)  # commit, pr, diff, manual
    status = Column(String(50), default="analyzed", nullable=False)
    description = Column(Text, nullable=True)
    change_payload = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    project = relationship("Project", back_populates="changes")
    commit = relationship("Commit", back_populates="changes")
    risk_assessments = relationship("RiskAssessment", back_populates="change")
    analysis_runs = relationship("AnalysisRun", back_populates="change")


# ====================================================================
# 2. CODE LEVEL ENTITIES (LEVEL 1 ARTIFACT)
# ====================================================================

class File(Base):
    __tablename__ = "files"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    repository_id = Column(String(36), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    snapshot_id = Column(String(36), ForeignKey("repository_snapshots.id", ondelete="SET NULL"), nullable=True, index=True)
    path = Column(String(1024), nullable=False, index=True)
    file_name = Column(String(255), nullable=False)
    extension = Column(String(50), nullable=True)
    language = Column(String(50), nullable=True, index=True)
    line_count = Column(Integer, default=0, nullable=False)
    file_hash = Column(String(64), nullable=True)
    is_test = Column(Boolean, default=False, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    repository = relationship("Repository", back_populates="files")
    snapshot = relationship("RepositorySnapshot", back_populates="files")
    symbols = relationship("CodeSymbol", back_populates="file", cascade="all, delete-orphan")
    tests = relationship("Test", back_populates="file")


class CodeSymbol(Base):
    __tablename__ = "code_symbols"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    file_id = Column(String(36), ForeignKey("files.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False, index=True)
    symbol_type = Column(String(50), nullable=False, index=True)  # function, class, method, module
    signature = Column(Text, nullable=True)
    docstring = Column(Text, nullable=True)
    start_line = Column(Integer, nullable=True)
    end_line = Column(Integer, nullable=True)
    is_exported = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    file = relationship("File", back_populates="symbols")
    api_endpoints = relationship("APIEndpoint", back_populates="symbol")
    tests = relationship("Test", back_populates="symbol")


# ====================================================================
# 3. ARCHITECTURE LEVEL ENTITIES (LEVEL 2 ARCHITECTURE)
# ====================================================================

class Service(Base):
    __tablename__ = "services"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    service_type = Column(String(50), default="backend_service", nullable=False)
    runtime = Column(String(50), nullable=True)
    root_directory = Column(String(1024), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    project = relationship("Project", back_populates="services")
    api_endpoints = relationship("APIEndpoint", back_populates="service", cascade="all, delete-orphan")
    database_entities = relationship("DatabaseEntity", back_populates="service", cascade="all, delete-orphan")
    configurations = relationship("Configuration", back_populates="service")
    runtime_events = relationship("RuntimeEvent", back_populates="service")


class APIEndpoint(Base):
    __tablename__ = "api_endpoints"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    service_id = Column(String(36), ForeignKey("services.id", ondelete="CASCADE"), nullable=False, index=True)
    file_id = Column(String(36), ForeignKey("files.id", ondelete="SET NULL"), nullable=True, index=True)
    symbol_id = Column(String(36), ForeignKey("code_symbols.id", ondelete="SET NULL"), nullable=True, index=True)
    route_path = Column(String(512), nullable=False, index=True)
    http_method = Column(String(20), nullable=False, index=True)  # GET, POST, PUT, DELETE, etc.
    request_schema = Column(JSON, default=dict, nullable=False)
    response_schema = Column(JSON, default=dict, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    service = relationship("Service", back_populates="api_endpoints")
    symbol = relationship("CodeSymbol", back_populates="api_endpoints")


class DatabaseEntity(Base):
    __tablename__ = "database_entities"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    service_id = Column(String(36), ForeignKey("services.id", ondelete="SET NULL"), nullable=True, index=True)
    entity_name = Column(String(255), nullable=False, index=True)
    table_name = Column(String(255), nullable=True)
    schema_definition = Column(JSON, default=dict, nullable=False)
    entity_type = Column(String(50), default="table", nullable=False)  # table, collection, queue
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    project = relationship("Project")
    service = relationship("Service", back_populates="database_entities")


class Dependency(Base):
    __tablename__ = "dependencies"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    source_type = Column(String(50), nullable=False, index=True)  # service, file, symbol, api, database, test
    source_id = Column(String(64), nullable=False, index=True)
    target_type = Column(String(50), nullable=False, index=True)
    target_id = Column(String(64), nullable=False, index=True)
    relation_type = Column(String(50), nullable=False, index=True)  # CONTAINS, IMPORTS, CALLS, DEPENDS_ON, EXPOSES, etc.
    weight = Column(Float, default=1.0, nullable=False)
    metadata_payload = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("idx_dep_source", "source_type", "source_id"),
        Index("idx_dep_target", "target_type", "target_id"),
        Index("idx_dep_relation", "relation_type"),
    )


class Configuration(Base):
    __tablename__ = "configurations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    service_id = Column(String(36), ForeignKey("services.id", ondelete="SET NULL"), nullable=True, index=True)
    config_key = Column(String(255), nullable=False, index=True)
    config_value = Column(Text, nullable=True)
    config_format = Column(String(50), default="env", nullable=False)
    file_path = Column(String(1024), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    service = relationship("Service", back_populates="configurations")


class Environment(Base):
    __tablename__ = "environments"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    env_type = Column(String(50), default="dev", nullable=False)
    host = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


# ====================================================================
# 4. RUNTIME & TEST ENTITIES (LEVEL 3 RUNTIME)
# ====================================================================

class Test(Base):
    __tablename__ = "tests"
    __test__ = False  # Instruct pytest not to discover this SQLAlchemy model as a test case


    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    repository_id = Column(String(36), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    file_id = Column(String(36), ForeignKey("files.id", ondelete="SET NULL"), nullable=True, index=True)
    symbol_id = Column(String(36), ForeignKey("code_symbols.id", ondelete="SET NULL"), nullable=True, index=True)
    test_name = Column(String(255), nullable=False, index=True)
    test_type = Column(String(50), default="unit", nullable=False)  # unit, integration, e2e
    target_component = Column(String(255), nullable=True)
    file_path = Column(String(1024), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    project = relationship("Project", back_populates="tests")
    file = relationship("File", back_populates="tests")
    symbol = relationship("CodeSymbol", back_populates="tests")
    executions = relationship("TestExecution", back_populates="test", cascade="all, delete-orphan")


class TestExecution(Base):
    __tablename__ = "test_executions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    test_id = Column(String(36), ForeignKey("tests.id", ondelete="CASCADE"), nullable=False, index=True)
    commit_id = Column(String(36), ForeignKey("commits.id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(String(50), nullable=False)  # PASSED, FAILED, SKIPPED
    duration_ms = Column(Integer, default=0, nullable=False)
    error_message = Column(Text, nullable=True)
    stdout = Column(Text, nullable=True)
    executed_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    test = relationship("Test", back_populates="executions")
    commit = relationship("Commit", back_populates="test_executions")


class Incident(Base):
    __tablename__ = "incidents"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    severity = Column(String(50), default="medium", nullable=False)
    status = Column(String(50), default="open", nullable=False)
    root_cause_component_id = Column(String(64), nullable=True)
    detected_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    resolved_at = Column(DateTime, nullable=True)


class RuntimeEvent(Base):
    __tablename__ = "runtime_events"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    service_id = Column(String(36), ForeignKey("services.id", ondelete="SET NULL"), nullable=True, index=True)
    event_type = Column(String(100), nullable=False, index=True)
    payload = Column(JSON, default=dict, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    service = relationship("Service", back_populates="runtime_events")


# ====================================================================
# 5. SIMULATION & RISK ENTITIES
# ====================================================================

class Scenario(Base):
    __tablename__ = "scenarios"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    scenario_type = Column(String(100), nullable=False)  # service_failure, latency_spike, network_partition
    parameters = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    project = relationship("Project", back_populates="scenarios")
    results = relationship("ScenarioResult", back_populates="scenario", cascade="all, delete-orphan")


class ScenarioResult(Base):
    __tablename__ = "scenario_results"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    scenario_id = Column(String(36), ForeignKey("scenarios.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(50), default="completed", nullable=False)
    impacted_nodes = Column(JSON, default=list, nullable=False)
    propagation_paths = Column(JSON, default=list, nullable=False)
    risk_impact_score = Column(Float, default=0.0, nullable=False)
    result_payload = Column(JSON, default=dict, nullable=False)
    simulated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    scenario = relationship("Scenario", back_populates="results")


# ====================================================================
# 6. ANALYSIS, AGENTS & EVIDENCE ENTITIES
# ====================================================================

class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    change_id = Column(String(36), ForeignKey("changes.id", ondelete="SET NULL"), nullable=True, index=True)
    run_type = Column(String(100), default="full_analysis", nullable=False)
    status = Column(String(50), default="running", nullable=False)
    summary = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    project = relationship("Project", back_populates="analysis_runs")
    change = relationship("Change", back_populates="analysis_runs")
    risk_assessments = relationship("RiskAssessment", back_populates="analysis_run")
    agent_runs = relationship("AgentRun", back_populates="analysis_run", cascade="all, delete-orphan")
    evidence_items = relationship("Evidence", back_populates="analysis_run", cascade="all, delete-orphan")


class RiskAssessment(Base):
    __tablename__ = "risk_assessments"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    change_id = Column(String(36), ForeignKey("changes.id", ondelete="SET NULL"), nullable=True, index=True)
    analysis_run_id = Column(String(36), ForeignKey("analysis_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    overall_score = Column(Float, nullable=False)  # 0 to 100
    factor_breakdown = Column(JSON, default=dict, nullable=False)
    severity_level = Column(String(50), nullable=False)  # LOW, MEDIUM, HIGH, CRITICAL
    confidence = Column(Float, default=1.0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    project = relationship("Project", back_populates="risk_assessments")
    change = relationship("Change", back_populates="risk_assessments")
    analysis_run = relationship("AnalysisRun", back_populates="risk_assessments")


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    analysis_run_id = Column(String(36), ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_name = Column(String(100), nullable=False, index=True)
    prompt_tokens = Column(Integer, default=0, nullable=False)
    completion_tokens = Column(Integer, default=0, nullable=False)
    input_data = Column(JSON, default=dict, nullable=False)
    output_data = Column(JSON, default=dict, nullable=False)
    status = Column(String(50), default="completed", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    analysis_run = relationship("AnalysisRun", back_populates="agent_runs")


class Evidence(Base):
    __tablename__ = "evidence"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    analysis_run_id = Column(String(36), ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=True, index=True)
    source_type = Column(String(50), nullable=False, index=True)  # DIRECT, DERIVED, AI_INTERPRETATION
    source_reference = Column(String(512), nullable=False)
    description = Column(Text, nullable=False)
    confidence = Column(Float, default=1.0, nullable=False)
    payload = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    project = relationship("Project", back_populates="evidence_items")
    analysis_run = relationship("AnalysisRun", back_populates="evidence_items")
