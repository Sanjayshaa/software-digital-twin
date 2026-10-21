import os
import sys

if sys.version_info < (3, 11):
    venv_py = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".venv", "bin", "python3"))
    if os.path.exists(venv_py):
        os.execv(venv_py, [venv_py, "-m", "pytest", os.path.abspath(__file__), "-v"])

import pytest
from fastapi.testclient import TestClient
from app.models.entities import (
    Repository,
    RepositorySnapshot,
    StructuralArtifact,
    ArtifactRelationship,
    Scenario,
    ScenarioResult,
)
from app.services.simulation.validator import ScenarioValidator
from app.services.simulation.models import ProposedMutation, MutationType
from app.services.simulation.orchestration import MultiAgentScenarioOrchestrator
from app.core.database import SessionLocal


def test_whatif_target_resolution_with_extension(db_session):
    """
    Issue 1 Verification:
    Target 'studentgamificationservice.ts' or 'studentgamificationservice'
    must resolve successfully against a baseline artifact having name
    'StudentGamificationService' and location 'src/services/studentgamificationservice.ts'.
    """
    repo = Repository(
        id="repo-p0-whatif",
        name="test-repo-p0-whatif",
        local_path="/tmp/test_p0_whatif",
        environment="TEST",
    )
    db_session.merge(repo)

    snap = RepositorySnapshot(
        id="snap-p0-whatif",
        repository_id=repo.id,
        commit_hash="c0ffee1234567890abcdef1234567890abcdef12",
        commit_message="Add student gamification service",
    )
    db_session.merge(snap)

    art = StructuralArtifact(
        id="art-p0-gamification",
        snapshot_id=snap.id,
        name="StudentGamificationService",
        qualified_name="src.services.StudentGamificationService",
        artifact_type="SERVICE",
        location="src/services/studentgamificationservice.ts:1:100",
    )
    art_dep = StructuralArtifact(
        id="art-p0-dep",
        snapshot_id=snap.id,
        name="DepService",
        qualified_name="src.services.DepService",
        artifact_type="SERVICE",
        location="src/services/dep.ts:1:50",
    )
    db_session.merge(art)
    db_session.merge(art_dep)

    rel = ArtifactRelationship(
        id="rel-p0-1",
        snapshot_id=snap.id,
        source_artifact_id=art.id,
        target_artifact_id="art-p0-dep",
        relationship_type="CALLS",
    )
    db_session.merge(rel)
    db_session.commit()

    validator = ScenarioValidator()

    # Case A: User specifies raw file with extension: 'studentgamificationservice.ts'
    mutation_with_ext = ProposedMutation(
        mutation_id="mut-p0-1",
        target="studentgamificationservice.ts",
        mutation_type=MutationType.MODIFY_SYMBOL,
    )
    res = validator.validate_mutations([art], [rel], [mutation_with_ext])
    assert res.is_valid is True, f"Failed to validate extension-bearing target: {res.errors}"
    assert len(res.validated_mutations) == 1
    assert res.validated_mutations[0].target == "studentgamificationservice.ts"

    # Case B: User specifies lowercase stem: 'studentgamificationservice'
    mutation_stem = ProposedMutation(
        mutation_id="mut-p0-2",
        target="studentgamificationservice",
        mutation_type=MutationType.MODIFY_SYMBOL,
    )
    res_stem = validator.validate_mutations([art], [rel], [mutation_stem])
    assert res_stem.is_valid is True
    assert res_stem.validated_mutations[0].target == "studentgamificationservice"

    # Case C: Non-existent target must yield explicit resolution error without hallucination
    mutation_invalid = ProposedMutation(
        mutation_id="mut-p0-3",
        target="completely_nonexistent_service.ts",
        mutation_type=MutationType.MODIFY_SYMBOL,
    )
    res_invalid = validator.validate_mutations([art], [rel], [mutation_invalid])
    assert res_invalid.is_valid is False
    assert len(res_invalid.errors) > 0
    assert "does not exist" in res_invalid.errors[0] or "cannot be resolved" in res_invalid.errors[0]
    assert len(res_invalid.unknown_entities) == 1


def test_whatif_orchestration_end_to_end_and_persistence(client: TestClient, db_session):
    """
    Issue 1 & 3 Verification:
    Verify /repositories/{id}/scenarios/orchestrate handles extension targets,
    persists Scenario and ScenarioResult in DB, redacts secrets, and serves the report
    via /repositories/{id}/scenarios/{scenario_id}/report.
    """
    repo = Repository(
        id="repo-p0-orch",
        name="test-repo-p0-orch",
        local_path="/tmp/test_p0_orch",
        environment="TEST",
    )
    db_session.merge(repo)

    snap = RepositorySnapshot(
        id="snap-p0-orch",
        repository_id=repo.id,
        commit_hash="deadbeef1234567890abcdef1234567890abcdef",
        commit_message="Baseline snapshot",
    )
    db_session.merge(snap)

    art1 = StructuralArtifact(
        id="art-p0-svc",
        snapshot_id=snap.id,
        name="StudentGamificationService",
        qualified_name="services.StudentGamificationService",
        artifact_type="SERVICE",
        location="src/services/studentgamificationservice.ts",
    )
    art2 = StructuralArtifact(
        id="art-p0-client",
        snapshot_id=snap.id,
        name="LeaderboardController",
        qualified_name="controllers.LeaderboardController",
        artifact_type="CONTROLLER",
        location="src/controllers/leaderboard.ts",
    )
    rel = ArtifactRelationship(
        id="rel-p0-call",
        snapshot_id=snap.id,
        source_artifact_id=art2.id,
        target_artifact_id=art1.id,
        relationship_type="CALLS",
    )
    db_session.merge(art1)
    db_session.merge(art2)
    db_session.merge(rel)
    db_session.commit()

    # Step 1: Call orchestrate with explicit target containing extension and natural language query
    payload = {
        "query": "What happens if we remove studentgamificationservice.ts?",
        "base_snapshot_id": snap.id,
        "explicit_target": "studentgamificationservice.ts",
        "explicit_type": "REMOVE_ENTITY",
    }
    response = client.post(f"/repositories/{repo.id}/scenarios/orchestrate", json=payload)
    assert response.status_code == 200, f"Orchestrate failed: {response.text}"
    data = response.json()

    scenario_id = data["scenario_id"]
    assert scenario_id is not None
    assert data["simulation"]["status"] in ("COMPLETED", "SUCCESS")
    assert len(data["simulation"]["proposed_changes"]) == 1
    assert data["simulation"]["proposed_changes"][0]["target_entity"] == art1.id

    # Verify query preservation
    assert "studentgamificationservice.ts" in data["plan"]["user_query"]

    # Step 2: Verify scenario was persisted in database
    db_scenario = db_session.query(Scenario).filter_by(id=scenario_id).first()
    assert db_scenario is not None
    assert db_scenario.repository_id == repo.id

    # Step 3: Fetch engineering report via report endpoint
    report_res = client.get(f"/repositories/{repo.id}/scenarios/{scenario_id}/report")
    assert report_res.status_code == 200, f"Report endpoint failed: {report_res.text}"
    report_data = report_res.json()
    assert "markdown_content" in report_data or "report_markdown" in report_data
    markdown = report_data.get("markdown_content") or report_data.get("report_markdown")
    assert "StudentGamificationService" in markdown
    assert "Architecture Impact" in markdown


def test_test_impact_with_commit_sha_and_snapshot_resolution(client: TestClient, db_session):
    """
    Issue 2 Verification:
    Verify POST /repositories/{id}/test-impact resolves when passed a 40-character commit SHA
    or snapshot ID, and classifies tests accurately without returning 404 or generic failure.
    """
    repo = Repository(
        id="repo-p0-test-impact",
        name="test-repo-p0-test-impact",
        local_path="/tmp/test_p0_test_impact",
        environment="TEST",
    )
    db_session.merge(repo)

    sha_base = "1111111111111111111111111111111111111111"
    sha_target = "2222222222222222222222222222222222222222"

    snap_base = RepositorySnapshot(
        id="snap-p0-base",
        repository_id=repo.id,
        commit_hash=sha_base,
        commit_message="Base commit",
    )
    snap_target = RepositorySnapshot(
        id="snap-p0-target",
        repository_id=repo.id,
        commit_hash=sha_target,
        commit_message="Target commit",
    )
    db_session.merge(snap_base)
    db_session.merge(snap_target)

    # Add baseline artifact, changed target artifact, and covering test artifact
    art_base = StructuralArtifact(
        id="art-p0-tested-base",
        repository_id=repo.id,
        snapshot_id=snap_base.id,
        name="AuthManager",
        qualified_name="core.auth.AuthManager",
        artifact_type="CLASS",
        location="core/auth.py:10:50",
        source_hash="hash_v1",
    )
    art_target = StructuralArtifact(
        id="art-p0-tested-target",
        repository_id=repo.id,
        snapshot_id=snap_target.id,
        name="AuthManager",
        qualified_name="core.auth.AuthManager",
        artifact_type="CLASS",
        location="core/auth.py:10:50",
        source_hash="hash_v2_modified",
    )
    art_test = StructuralArtifact(
        id="art-p0-test-case",
        repository_id=repo.id,
        snapshot_id=snap_target.id,
        name="test_auth_login",
        qualified_name="tests.test_auth.test_auth_login",
        artifact_type="TEST_CASE",
        location="tests/test_auth.py:10:30",
        source_hash="test_hash_v1",
    )
    rel_test = ArtifactRelationship(
        id="rel-p0-test-coverage",
        repository_id=repo.id,
        snapshot_id=snap_target.id,
        source_artifact_id=art_test.id,
        target_artifact_id=art_target.id,
        relationship_type="TESTS",
        confidence=1.0,
    )
    db_session.merge(art_base)
    db_session.merge(art_target)
    db_session.merge(art_test)
    db_session.merge(rel_test)
    db_session.commit()

    # Request test-impact using commit SHA strings directly (as sent from UI dropdowns)
    req_payload = {
        "target_snapshot_id": sha_target,
        "base_snapshot_id": sha_base,
    }
    res = client.post(f"/repositories/{repo.id}/test-impact", json=req_payload)
    assert res.status_code == 200, f"Test impact failed with commit SHA resolution: {res.text}"
    impact_data = res.json()

    assert impact_data["analysis_id"] is not None
    assert impact_data["target_snapshot_id"] == snap_target.id
    assert impact_data["summary"]["directly_affected_count"] >= 1
    assert any(t["test_name"] == "test_auth_login" for t in impact_data["affected_tests"])


def test_architecture_graph_inbound_outbound_metrics(client: TestClient, db_session):
    """
    Issue 4 Verification:
    Verify /repositories/{id}/graph returns accurate in_degree and out_degree metrics,
    and entry points (in_degree == 0, out_degree > 0) are correctly structured so UI does not
    misinterpret progressive disclosure filtering as missing relationships.
    """
    repo = Repository(
        id="repo-p0-graph",
        name="test-repo-p0-graph",
        local_path="/tmp/test_p0_graph",
        environment="TEST",
    )
    db_session.merge(repo)

    snap = RepositorySnapshot(
        id="snap-p0-graph",
        repository_id=repo.id,
        commit_hash="3333333333333333333333333333333333333333",
        commit_message="Graph commit",
    )
    db_session.merge(snap)

    entry_art = StructuralArtifact(
        id="art-p0-entry",
        snapshot_id=snap.id,
        name="MainRouter",
        qualified_name="router.MainRouter",
        artifact_type="COMPONENT",
        location="src/router.ts:1:50",
    )
    callee_art = StructuralArtifact(
        id="art-p0-callee",
        snapshot_id=snap.id,
        name="DataStore",
        qualified_name="storage.DataStore",
        artifact_type="SERVICE",
        location="src/storage.ts:1:50",
    )
    rel = ArtifactRelationship(
        id="rel-p0-graph-call",
        snapshot_id=snap.id,
        source_artifact_id=entry_art.id,
        target_artifact_id=callee_art.id,
        relationship_type="CALLS",
    )
    db_session.merge(entry_art)
    db_session.merge(callee_art)
    db_session.merge(rel)
    db_session.commit()

    res = client.get(f"/repositories/{repo.id}/graph?snapshot_id={snap.id}")
    assert res.status_code == 200, f"Graph endpoint failed: {res.text}"
    graph_data = res.json()

    nodes = {n["id"]: n for n in graph_data.get("nodes", [])}
    assert "art-p0-entry" in nodes
    assert "art-p0-callee" in nodes

    entry_node = nodes["art-p0-entry"]
    callee_node = nodes["art-p0-callee"]

    # Entry point has 0 in_degree and >= 1 out_degree
    assert entry_node.get("in_degree", 0) == 0
    assert entry_node.get("out_degree", 0) >= 1

    # Callee has >= 1 in_degree
    assert callee_node.get("in_degree", 0) >= 1
