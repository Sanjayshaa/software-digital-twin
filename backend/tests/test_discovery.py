import os
import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.services.discovery.engine import discovery_engine
from app.services.discovery.models import EvidenceType
from app.models.entities import Project, Repository, AnalysisPlan, ProjectTechnology

FIXTURES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "tests", "fixtures"))
GROUND_TRUTH_PATH = os.path.join(FIXTURES_DIR, "ground_truth.json")


@pytest.fixture(scope="module")
def ground_truth():
    with open(GROUND_TRUTH_PATH, "r") as f:
        return json.load(f)


def test_fixture_1_python_fastapi_pytest(ground_truth):
    fixture_path = os.path.join(FIXTURES_DIR, "python_fastapi_pytest")
    profile, plan = discovery_engine.discover(fixture_path)
    expected = ground_truth["python_fastapi_pytest"]

    detected_langs = [l.name for l in profile.languages]
    for el in expected["expected_languages"]:
        assert el in detected_langs, f"Expected language {el} not in {detected_langs}"

    detected_fws = [f.name for f in profile.frameworks]
    for ef in expected["expected_frameworks"]:
        assert ef in detected_fws, f"Expected framework {ef} not in {detected_fws}"

    detected_tests = [t.name for t in profile.testing_frameworks]
    for et in expected["expected_testing"]:
        assert et in detected_tests, f"Expected test framework {et} not in {detected_tests}"

    detected_dbs = [d.name for d in profile.databases]
    for ed in expected["expected_databases"]:
        assert ed in detected_dbs, f"Expected database {ed} not in {detected_dbs}"

    # Plan verification
    assert plan.total_steps > 0
    assert any("python" in s.target_technology for s in plan.steps)


def test_fixture_2_java_spring_maven_junit(ground_truth):
    fixture_path = os.path.join(FIXTURES_DIR, "java_spring_maven_junit")
    profile, plan = discovery_engine.discover(fixture_path)
    expected = ground_truth["java_spring_maven_junit"]

    detected_langs = [l.name for l in profile.languages]
    for el in expected["expected_languages"]:
        assert el in detected_langs, f"Expected language {el} not in {detected_langs}"

    detected_fws = [f.name for f in profile.frameworks]
    for ef in expected["expected_frameworks"]:
        assert ef in detected_fws, f"Expected framework {ef} not in {detected_fws}"

    detected_bm = [b.name for b in profile.build_systems]
    for ebm in expected["expected_build_systems"]:
        assert ebm in detected_bm, f"Expected build system {ebm} not in {detected_bm}"

    detected_tests = [t.name for t in profile.testing_frameworks]
    for et in expected["expected_testing"]:
        assert et in detected_tests, f"Expected test framework {et} not in {detected_tests}"

    detected_dbs = [d.name for d in profile.databases]
    for ed in expected["expected_databases"]:
        assert ed in detected_dbs, f"Expected database {ed} not in {detected_dbs}"


def test_fixture_3_typescript_react_vitest(ground_truth):
    fixture_path = os.path.join(FIXTURES_DIR, "typescript_react_vitest")
    profile, plan = discovery_engine.discover(fixture_path)
    expected = ground_truth["typescript_react_vitest"]

    detected_langs = [l.name for l in profile.languages]
    for el in expected["expected_languages"]:
        assert el in detected_langs

    detected_fws = [f.name for f in profile.frameworks]
    for ef in expected["expected_frameworks"]:
        assert ef in detected_fws

    detected_tests = [t.name for t in profile.testing_frameworks]
    for et in expected["expected_testing"]:
        assert et in detected_tests


def test_fixture_4_go_modules_gotest(ground_truth):
    fixture_path = os.path.join(FIXTURES_DIR, "go_modules_gotest")
    profile, plan = discovery_engine.discover(fixture_path)
    expected = ground_truth["go_modules_gotest"]

    detected_langs = [l.name for l in profile.languages]
    for el in expected["expected_languages"]:
        assert el in detected_langs

    detected_fws = [f.name for f in profile.frameworks]
    for ef in expected["expected_frameworks"]:
        assert ef in detected_fws

    detected_tests = [t.name for t in profile.testing_frameworks]
    for et in expected["expected_testing"]:
        assert et in detected_tests


def test_fixture_5_cpp_cmake(ground_truth):
    fixture_path = os.path.join(FIXTURES_DIR, "cpp_cmake")
    profile, plan = discovery_engine.discover(fixture_path)
    expected = ground_truth["cpp_cmake"]

    detected_langs = [l.name for l in profile.languages]
    for el in expected["expected_languages"]:
        assert el in detected_langs

    detected_bm = [b.name for b in profile.build_systems]
    for ebm in expected["expected_build_systems"]:
        assert ebm in detected_bm

    detected_tests = [t.name for t in profile.testing_frameworks]
    for et in expected["expected_testing"]:
        assert et in detected_tests


def test_fixture_6_cobol_legacy(ground_truth):
    fixture_path = os.path.join(FIXTURES_DIR, "cobol_legacy")
    profile, plan = discovery_engine.discover(fixture_path)
    expected = ground_truth["cobol_legacy"]

    detected_langs = [l.name for l in profile.languages]
    for el in expected["expected_languages"]:
        assert el in detected_langs

    # Check that capability level is Level 1 for COBOL
    cobol_stat = next(l for l in profile.languages if l.name == "cobol")
    assert cobol_stat.capability_level == 1
    assert any(s.analyzer_name == "cobol_analyzer" for s in plan.steps)


def test_fixture_7_c_makefile(ground_truth):
    fixture_path = os.path.join(FIXTURES_DIR, "c_makefile")
    profile, plan = discovery_engine.discover(fixture_path)
    expected = ground_truth["c_makefile"]

    detected_langs = [l.name for l in profile.languages]
    for el in expected["expected_languages"]:
        assert el in detected_langs

    detected_bm = [b.name for b in profile.build_systems]
    for ebm in expected["expected_build_systems"]:
        assert ebm in detected_bm


def test_fixture_8_polyglot_microservice(ground_truth):
    fixture_path = os.path.join(FIXTURES_DIR, "polyglot_microservice")
    profile, plan = discovery_engine.discover(fixture_path)
    expected = ground_truth["polyglot_microservice"]

    detected_langs = [l.name for l in profile.languages]
    for el in expected["expected_languages"]:
        assert el in detected_langs, f"Expected language {el} in {detected_langs}"

    detected_fws = [f.name for f in profile.frameworks]
    for ef in expected["expected_frameworks"]:
        assert ef in detected_fws, f"Expected framework {ef} in {detected_fws}"

    detected_dbs = [d.name for d in profile.databases]
    for ed in expected["expected_databases"]:
        assert ed in detected_dbs, f"Expected database {ed} in {detected_dbs}"

    # Architecture Signal
    signals = [s.signal for s in profile.architecture_signals]
    assert "microservice-like structure" in signals


def test_discovery_persistence_and_api(client: TestClient, db_session: Session):
    # 1. Create a project and repository pointing to polyglot fixture
    fixture_path = os.path.join(FIXTURES_DIR, "polyglot_microservice")
    project = Project(name="Polyglot-Discovery-Test", description="Discovery persistence test")
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    repo = Repository(
        project_id=project.id,
        name="polyglot-repo",
        local_path=fixture_path,
        default_branch="main"
    )
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)

    # 2. Call POST /repositories/{id}/discover
    response = client.post(f"/repositories/{repo.id}/discover")
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["status"] == "completed"
    assert res_data["total_files"] > 0
    assert res_data["total_plan_steps"] > 0

    # 3. Call GET /repositories/{id}/profile
    p_response = client.get(f"/repositories/{repo.id}/profile")
    assert p_response.status_code == 200
    p_data = p_response.json()
    assert len(p_data["languages"]) > 0
    assert len(p_data["frameworks"]) > 0

    # 4. Call GET /repositories/{id}/capabilities
    c_response = client.get(f"/repositories/{repo.id}/capabilities")
    assert c_response.status_code == 200
    c_data = c_response.json()
    assert len(c_data) > 0

    # 5. Call GET /repositories/{id}/analysis-plan
    plan_response = client.get(f"/repositories/{repo.id}/analysis-plan")
    assert plan_response.status_code == 200
    plan_data = plan_response.json()
    assert plan_data["total_steps"] > 0

    # Cleanup
    db_session.delete(project)
    db_session.commit()
