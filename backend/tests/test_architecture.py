import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.entities import Project, Repository, RepositorySnapshot
from app.services.architecture.detector import architecture_drift_detector
from app.services.architecture.comparator import snapshot_drift_comparator
from app.services.architecture.service import architecture_service
from app.services.architecture.models import (
    DriftCategory,
    DriftSeverity,
    DriftStatus,
    ArchitectureDrift,
    ArchitectureConformanceReport,
)

FIXTURE_VAL_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "tests", "validation", "arch_repo")
)
VAL_BASELINE = os.path.join(FIXTURE_VAL_DIR, "architecture-baseline.yaml")


class TestArchitectureDriftDetection:
    """Rigorous verification of deterministic architecture drift and boundary conformance."""

    def test_baseline_loading(self):
        baseline = architecture_drift_detector.load_baseline(VAL_BASELINE)
        assert baseline.version == "1.0.0"
        assert "presentation" in baseline.layers
        assert "infrastructure" in baseline.layers
        assert len(baseline.rules) >= 1
        assert baseline.rules[0].category == "LAYER_VIOLATION"

    def test_intentional_drift_detected_with_evidence(self):
        """Verifies that an intentional forbidden dependency is caught with exact line and evidence."""
        # Write controller with intentional violation
        controller_path = os.path.join(FIXTURE_VAL_DIR, "presentation", "controller.py")
        bad_code = (
            "from application.service import UserService\n"
            "# Intentional forbidden dependency\n"
            "from infrastructure.db import DatabaseClient\n\n"
            "class UserController:\n"
            "    def __init__(self):\n"
            "        self.service = UserService()\n"
            "        self.raw_db = DatabaseClient()\n"
        )
        with open(controller_path, "w", encoding="utf-8") as f:
            f.write(bad_code)

        spec = architecture_drift_detector.load_baseline(VAL_BASELINE)
        report = architecture_drift_detector.detect_drift(
            repository_path=FIXTURE_VAL_DIR,
            baseline=spec,
        )

        assert report.violations > 0
        assert report.conformance_percentage < 100.0

        # Verify evidence
        matching_drift = next(
            (d for d in report.drifts if "infrastructure.db" in d.target),
            None
        )
        assert matching_drift is not None
        assert matching_drift.line == 3
        assert matching_drift.severity in ("HIGH", DriftSeverity.HIGH)
        assert matching_drift.confidence == 0.98
        assert "presentation/controller.py:3" in matching_drift.actual_evidence

    def test_drift_resolution_restores_100_percent_conformance(self):
        """Verifies that resolving the violation brings conformance back to 100%."""
        controller_path = os.path.join(FIXTURE_VAL_DIR, "presentation", "controller.py")
        clean_code = (
            "from application.service import UserService\n\n"
            "class UserController:\n"
            "    def __init__(self):\n"
            "        self.service = UserService()\n\n"
            "    def handle_request(self, user_id: str):\n"
            "        return self.service.fetch_user(user_id)\n"
        )
        with open(controller_path, "w", encoding="utf-8") as f:
            f.write(clean_code)

        spec = architecture_drift_detector.load_baseline(VAL_BASELINE)
        clean_report = architecture_drift_detector.detect_drift(
            repository_path=FIXTURE_VAL_DIR,
            baseline=spec,
        )

        assert clean_report.violations == 0
        assert clean_report.circular_dependencies == 0
        assert clean_report.conformance_percentage == 100.0
        assert len(clean_report.drifts) == 0

    def test_snapshot_drift_comparison(self):
        """Verifies snapshot comparison identifying new and resolved drifts."""
        # Report A has 1 drift
        drift_a = ArchitectureDrift(
            category=DriftCategory.LAYER_VIOLATION.value,
            severity=DriftSeverity.HIGH.value,
            source="presentation.controller",
            target="infrastructure.db",
            expected_rule="Presentation must not depend on Infrastructure",
            actual_evidence="controller.py:3 -> import DatabaseClient",
            file_path="presentation/controller.py",
            line_number=3,
        )
        report_a = ArchitectureConformanceReport(
            snapshot_id="snap_v1",
            violations=1,
            conformance_percentage=85.0,
            drifts=[drift_a],
        )

        # Report B has resolved the drift
        report_b = ArchitectureConformanceReport(
            snapshot_id="snap_v2",
            violations=0,
            conformance_percentage=100.0,
            drifts=[],
        )

        diff = snapshot_drift_comparator.compare_reports(report_a, report_b)
        assert len(diff.resolved_drifts) == 1
        assert len(diff.new_drifts) == 0
        assert diff.conformance_delta == +15.0
        assert diff.resolved_drifts[0].status == "RESOLVED"

    def test_persistence_and_retrieval(self, db_session: Session):
        """Verifies storing conformance reports and drifts in PostgreSQL."""
        import uuid
        uid = uuid.uuid4().hex[:8]
        proj = Project(name=f"Arch-Test-Project-{uid}", description="Architecture testing")
        db_session.add(proj)
        db_session.flush()

        repo = Repository(project_id=proj.id, name=f"arch-test-repo-{uid}", local_path=FIXTURE_VAL_DIR)
        db_session.add(repo)
        db_session.flush()

        drift = ArchitectureDrift(
            category="FORBIDDEN_DEPENDENCY",
            severity="HIGH",
            source="ui.view",
            target="db.raw",
            expected_rule="UI cannot bypass API",
            actual_evidence="view.py:10: import raw_db",
            file_path="ui/view.py",
            line_number=10,
            confidence=0.98,
        )
        report = ArchitectureConformanceReport(
            repository_id=repo.id,
            snapshot_id=None,
            expected_boundaries=10,
            validated_boundaries=8,
            violations=1,
            conformance_percentage=90.0,
            drifts=[drift],
            summary="Test persistence report",
        )

        saved = architecture_service.persist_report(db_session, report, repo.id)
        assert saved.id is not None
        assert saved.violations_count == 1
        assert saved.conformance_percentage == 90.0

        # Query back
        retrieved = architecture_service.get_latest_report(db_session, repo.id)
        assert retrieved is not None
        assert retrieved.violations == 1
        assert retrieved.conformance_percentage == 90.0
        assert len(retrieved.drifts) == 1
        assert retrieved.drifts[0].source == "ui.view"


class TestStatusAndArchitectureAPI:
    """Verifies HTTP API endpoints for Status and Architecture Conformance."""

    def test_status_endpoint(self, client: TestClient):
        response = client.get("/status")
        assert response.status_code == 200
        data = response.json()
        assert "overall_project_progress" in data
        assert "current_phase_progress" in data
        assert "architecture_conformance" in data
        assert data["architecture_conformance"] == 100.0
        assert len(data["phases"]) == 10
        assert data["database_status"]["total_tables"] >= 37

    def test_status_phases_endpoint(self, client: TestClient):
        response = client.get("/status/phases")
        assert response.status_code == 200
        data = response.json()
        assert len(data["phases"]) == 10
        assert data["phases"][0]["status"] == "COMPLETE"
        assert data["phases"][1]["status"] == "COMPLETE"
        assert data["phases"][2]["status"] == "COMPLETE"

    def test_architecture_check_api(self, client: TestClient, db_session: Session):
        import uuid
        uid = uuid.uuid4().hex[:8]
        proj = Project(name=f"Arch-API-Project-{uid}", description="Architecture API test")
        db_session.add(proj)
        db_session.flush()

        repo = Repository(project_id=proj.id, name=f"arch-api-repo-{uid}", local_path=FIXTURE_VAL_DIR)
        db_session.add(repo)
        db_session.commit()

        response = client.post(
            f"/repositories/{repo.id}/architecture/check",
            params={"baseline_path": VAL_BASELINE, "persist": "false"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "conformance_percentage" in data
        assert data["conformance_percentage"] == 100.0
        assert data["violations"] == 0

    def test_circular_dependency_detection(self, tmp_path):
        """Verifies deterministic detection of circular import cycles (A -> B -> C -> A)."""
        pkg = tmp_path / "cyclic_pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "module_a.py").write_text("import cyclic_pkg.module_b\n")
        (pkg / "module_b.py").write_text("import cyclic_pkg.module_c\n")
        (pkg / "module_c.py").write_text("import cyclic_pkg.module_a\n")

        baseline_file = tmp_path / "baseline.yaml"
        baseline_file.write_text(
            "version: '1.0.0'\nlayers:\n  cyclic:\n    modules: ['cyclic_pkg.*']\n    allowed_dependencies: ['cyclic_pkg.*']\nrules: []\n"
        )

        spec = architecture_drift_detector.load_baseline(str(baseline_file))
        report = architecture_drift_detector.detect_drift(
            repository_path=str(tmp_path),
            baseline=spec,
        )

        assert report.circular_dependencies > 0
        cycle_drift = next(
            (d for d in report.drifts if d.category == DriftCategory.CIRCULAR_DEPENDENCY or str(d.category) == "CIRCULAR_DEPENDENCY"),
            None
        )
        assert cycle_drift is not None
        assert cycle_drift.severity in (DriftSeverity.CRITICAL, "CRITICAL")
        assert cycle_drift.confidence == 1.0
        assert "Cycle:" in cycle_drift.actual_evidence

    def test_real_repo_outside_fixtures_validation(self, db_session: Session):
        """Validates real repository analysis against real_validation_repo outside fixtures."""
        from app.services.analysis.engine import structural_twin_engine
        import uuid

        real_repo_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "real_validation_repo")
        )
        if not os.path.exists(real_repo_path):
            real_repo_path = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "..", "tmp", "real_validation_repo")
            )

        uid = uuid.uuid4().hex[:8]
        proj = Project(name=f"RealRepo-Project-{uid}", description="Real repo test")
        db_session.add(proj)
        db_session.flush()

        repo = Repository(
            project_id=proj.id,
            name=f"real-repo-{uid}",
            local_path=real_repo_path,
        )
        db_session.add(repo)
        db_session.commit()

        snapshot_id, result = structural_twin_engine.build_structural_twin(
            db=db_session,
            repository_id=repo.id,
            commit_hash="commit_test_real",
            branch_name="main",
        )

        assert result.status == "COMPLETED"
        assert result.files_scanned == 2
        assert len(result.artifacts) >= 5
        art_names = [a.qualified_name for a in result.artifacts]
        assert "calculator.Calculator" in art_names
        assert "test_calculator.test_add" in art_names
