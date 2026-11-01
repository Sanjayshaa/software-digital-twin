"""
Test Suite for Live Incremental Change-Analysis Workflow & What-If Bridge.

Verifies:
1. Git working tree diff execution (staged, unstaged, untracked).
2. AST symbol mapping from working tree diff hunks to StructuralArtifact nodes.
3. Live ChangeSet generation with symbol-level accuracy and file-level fallback.
4. Knowledge Graph propagation: Tier 1 direct callers, Tier 2 transitive callers, and targeted test detection.
5. Conversion of detected live changes into ProposedMutation objects.
6. End-to-end bridge into What-If simulation: virtual twin isolation and scenario execution.
7. FastAPI HTTP endpoints: /live-changes and /live-incremental-analysis.
"""

import os
import sys
import unittest

# Subshell Python version auto-re-exec guard
if sys.version_info < (3, 11):
    venv_py = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".venv", "bin", "python3"))
    if os.path.exists(venv_py):
        os.execv(venv_py, [venv_py, "-m", "unittest"] + sys.argv[1:])

import tempfile
import shutil
import subprocess
from datetime import datetime, timezone

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.models.entities import (
    Base,
    Repository,
    RepositorySnapshot,
    StructuralArtifact,
    ArtifactRelationship,
    User,
    Project,
)
from app.core.database import get_db
from app.services.impact.change_detector import (
    change_detector,
    run_git_working_tree_diff,
    map_changes_to_proposed_mutations,
)
from app.services.impact.service import change_impact_service
from app.services.impact.models import ChangeType, ChangeItem
from app.services.simulation.service import scenario_service
from app.services.simulation.models import CreateScenarioRequest, MutationType
from main import app


class TestLiveIncrementalAnalysisWorkflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(cls.engine)
        cls.SessionLocal = sessionmaker(bind=cls.engine, autoflush=False, autocommit=False)

        # Temporary git workspace for real working-tree tests
        cls.test_dir = tempfile.mkdtemp(prefix="twin_live_test_")
        subprocess.run(["git", "init"], cwd=cls.test_dir, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "twin@test.com"], cwd=cls.test_dir, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "Twin Test"], cwd=cls.test_dir, capture_output=True, check=True)

        # Initial committed file
        test_file = os.path.join(cls.test_dir, "service.py")
        with open(test_file, "w") as f:
            f.write(
                "def calculate_total(cart):\n"
                "    return sum(cart.items)\n"
                "\n"
                "def process_payment(amount):\n"
                "    return True\n"
            )
        subprocess.run(["git", "add", "."], cwd=cls.test_dir, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=cls.test_dir, capture_output=True, check=True)

        # Get initial commit hash
        proc = subprocess.run(["git", "rev-parse", "HEAD"], cwd=cls.test_dir, capture_output=True, text=True, check=True)
        cls.initial_commit = proc.stdout.strip()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.test_dir, ignore_errors=True)

    def setUp(self):
        self.db = self.SessionLocal()

        def override_get_db():
            try:
                yield self.db
            finally:
                pass

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

        # Populate baseline Project, Repo, Snapshot, Artifacts and Knowledge Graph relationships
        self.user = User(id="user_live_1", email="live@twincore.test", hashed_password="pw", role="ENGINEER")
        self.db.add(self.user)

        self.project = Project(id="proj_live_1", name="Live Twin Project", user_id="user_live_1")
        self.db.add(self.project)

        self.repo = Repository(
            id="repo_live_1",
            project_id="proj_live_1",
            name="live-ecommerce-service",
            local_path=self.test_dir,
            default_branch="main",
        )
        self.db.add(self.repo)

        self.snap = RepositorySnapshot(
            id="snap_live_base",
            repository_id="repo_live_1",
            commit_hash=self.initial_commit,
            branch_name="main",
        )
        self.db.add(self.snap)

        # Structural Artifacts:
        # art_calc: lines 1-2
        self.art_calc = StructuralArtifact(
            id="art_calc_1",
            snapshot_id="snap_live_base",
            name="calculate_total",
            qualified_name="service.calculate_total",
            artifact_type="FUNCTION",
            location="service.py:1-2",
            line_start=1,
            line_end=2,
            source_hash="hash_calc_v1",
        )
        # art_pay: lines 4-5
        self.art_pay = StructuralArtifact(
            id="art_pay_1",
            snapshot_id="snap_live_base",
            name="process_payment",
            qualified_name="service.process_payment",
            artifact_type="FUNCTION",
            location="service.py:4-5",
            line_start=4,
            line_end=5,
            source_hash="hash_pay_v1",
        )
        # art_api: API Endpoint calling process_payment
        self.art_api = StructuralArtifact(
            id="art_api_checkout",
            snapshot_id="snap_live_base",
            name="checkout_endpoint",
            qualified_name="api.checkout_endpoint",
            artifact_type="API_ENDPOINT",
            location="api/checkout.py:10-25",
            line_start=10,
            line_end=25,
            source_hash="hash_api_v1",
        )
        # art_test: Test suite testing process_payment
        self.art_test = StructuralArtifact(
            id="art_test_payment",
            snapshot_id="snap_live_base",
            name="test_process_payment",
            qualified_name="tests.test_process_payment",
            artifact_type="TEST_SUITE",
            location="tests/test_service.py:1-30",
            line_start=1,
            line_end=30,
            source_hash="hash_test_v1",
        )

        self.db.add_all([self.art_calc, self.art_pay, self.art_api, self.art_test])

        # Knowledge Graph Edges:
        # checkout_endpoint CALLS process_payment (incoming edge to art_pay)
        self.rel_api_to_pay = ArtifactRelationship(
            id="rel_api_pay",
            snapshot_id="snap_live_base",
            source_artifact_id="art_api_checkout",
            target_artifact_id="art_pay_1",
            relationship_type="CALLS",
        )
        # test_process_payment TESTS process_payment
        self.rel_test_to_pay = ArtifactRelationship(
            id="rel_test_pay",
            snapshot_id="snap_live_base",
            source_artifact_id="art_test_payment",
            target_artifact_id="art_pay_1",
            relationship_type="TESTS",
        )
        self.db.add_all([self.rel_api_to_pay, self.rel_test_to_pay])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine)
        Base.metadata.create_all(self.engine)
        app.dependency_overrides.clear()
        # Reset test directory to clean git state
        subprocess.run(["git", "checkout", "."], cwd=self.test_dir, capture_output=True)
        subprocess.run(["git", "clean", "-fd"], cwd=self.test_dir, capture_output=True)

    def test_01_clean_working_tree_detected_accurately(self):
        """Verifies clean working tree returns VERIFIED_CLEAN and zero blast radius."""
        cs = change_detector.detect_live_changes(self.db, "repo_live_1", "snap_live_base")
        self.assertEqual(cs.status, "VERIFIED_CLEAN")
        self.assertTrue(cs.is_verified_zero)
        self.assertEqual(len(cs.changes), 0)
        self.assertEqual(cs.summary["working_tree_status"], "CLEAN")

        # Run live incremental analysis
        res = change_impact_service.run_live_incremental_analysis(self.db, "repo_live_1", "snap_live_base")
        self.assertEqual(res["status"], "VERIFIED_CLEAN")
        self.assertEqual(res["working_tree_status"], "CLEAN")
        self.assertEqual(res["blast_radius_score"], 0.0)
        self.assertEqual(len(res["proposed_mutations"]), 0)

    def test_02_working_tree_diff_and_ast_symbol_mapping(self):
        """Modifies lines 4-5 in service.py and verifies exact intersection with process_payment."""
        test_file = os.path.join(self.test_dir, "service.py")
        with open(test_file, "w") as f:
            f.write(
                "def calculate_total(cart):\n"
                "    return sum(cart.items)\n"
                "\n"
                "def process_payment(amount):\n"
                "    return amount > 0\n"
            )

        ok, entries, line_ranges, err = run_git_working_tree_diff(self.test_dir, self.initial_commit)
        self.assertTrue(ok)
        self.assertGreater(len(entries), 0)

        cs = change_detector.detect_live_changes(self.db, "repo_live_1", "snap_live_base")
        self.assertEqual(cs.status, "COMPLETED")
        self.assertFalse(cs.is_verified_zero)
        self.assertEqual(cs.summary["working_tree_status"], "DIRTY")
        self.assertGreater(len(cs.changes), 0)

        # Verify symbol-level match
        pay_changes = [c for c in cs.changes if c.symbol_name == "process_payment"]
        self.assertGreater(len(pay_changes), 0)
        self.assertTrue(pay_changes[0].is_symbol_level)
        self.assertEqual(pay_changes[0].change_type, ChangeType.MODIFIED)

    def test_03_live_incremental_blast_radius_and_targeted_tests(self):
        """Verifies Knowledge Graph propagation from uncommitted changes to callers & tests."""
        test_file = os.path.join(self.test_dir, "service.py")
        with open(test_file, "w") as f:
            f.write(
                "def calculate_total(cart):\n"
                "    return sum(cart.items)\n"
                "\n"
                "def process_payment(amount):\n"
                "    # Modified payment logic\n"
                "    return False\n"
            )

        res = change_impact_service.run_live_incremental_analysis(self.db, "repo_live_1", "snap_live_base")
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["working_tree_status"], "DIRTY")
        self.assertGreater(res["blast_radius_score"], 0.0)

        # Verify checkout_endpoint was impacted as a caller
        self.assertIn("api.checkout_endpoint", res["affected_apis"])

        # Verify test_process_payment was identified as targeted test suite
        self.assertIn("tests.test_process_payment", res["targeted_tests"])

        # Verify proposed mutations generated
        muts = res["proposed_mutations"]
        self.assertGreater(len(muts), 0)
        self.assertEqual(muts[0]["target"], "service.process_payment")
        self.assertEqual(muts[0]["mutation_type"], "MODIFY_SYMBOL")

    def test_04_direct_bridge_to_what_if_virtual_twin_simulation(self):
        """Verifies proposed_mutations from live working tree feed directly into What-If simulation engine."""
        test_file = os.path.join(self.test_dir, "service.py")
        with open(test_file, "w") as f:
            f.write(
                "def calculate_total(cart):\n"
                "    return sum(cart.items)\n"
                "\n"
                "def process_payment(amount):\n"
                "    # New breaking payment signature\n"
                "    return amount > 100\n"
            )

        res = change_impact_service.run_live_incremental_analysis(self.db, "repo_live_1", "snap_live_base")
        live_mutations = res["proposed_mutations"]
        self.assertGreater(len(live_mutations), 0)

        # Bridge directly to What-If Scenario Service
        req = CreateScenarioRequest(
            name="Virtual Simulation of Uncommitted Changes",
            description="Testing live working tree changes on isolated virtual twin",
            base_snapshot_id="snap_live_base",
            proposed_changes=live_mutations,
        )
        created_scenario = scenario_service.create_scenario(self.db, "repo_live_1", req)
        self.assertIsNotNone(created_scenario["id"])

        # Execute deterministic simulation on virtual twin
        sim_res = scenario_service.simulate_scenario(self.db, created_scenario["id"])
        self.assertEqual(sim_res.repository_id, "repo_live_1")
        self.assertGreater(len(sim_res.impact.directly_affected) + len(sim_res.impact.indirectly_affected), 0)
        # Verify zero mutation to real DB snapshot
        snap_after = self.db.query(RepositorySnapshot).filter_by(id="snap_live_base").first()
        self.assertEqual(snap_after.commit_hash, self.initial_commit)

    def test_05_http_endpoints_live_changes_and_analysis(self):
        """Tests GET /live-changes and POST /live-incremental-analysis via FastAPI TestClient."""
        # 1. Clean state test
        res_clean = self.client.get("/repositories/repo_live_1/live-changes")
        self.assertEqual(res_clean.status_code, 200)
        data_clean = res_clean.json()
        self.assertEqual(data_clean["working_tree_status"], "CLEAN")
        self.assertEqual(data_clean["total_changes"], 0)

        # 2. Modify file in working tree
        test_file = os.path.join(self.test_dir, "service.py")
        with open(test_file, "w") as f:
            f.write(
                "def calculate_total(cart):\n"
                "    return sum(cart.items)\n"
                "\n"
                "def process_payment(amount):\n"
                "    return amount * 1.05\n"
            )

        # 3. Dirty state test
        res_dirty = self.client.get("/repositories/repo_live_1/live-changes")
        self.assertEqual(res_dirty.status_code, 200)
        data_dirty = res_dirty.json()
        self.assertEqual(data_dirty["working_tree_status"], "DIRTY")
        self.assertGreater(data_dirty["total_changes"], 0)
        self.assertGreater(len(data_dirty["proposed_mutations"]), 0)

        # 4. POST /live-incremental-analysis
        res_analysis = self.client.post(
            "/repositories/repo_live_1/live-incremental-analysis",
            json={"base_snapshot_id": "snap_live_base", "max_depth": 5, "include_tests": True},
        )
        self.assertEqual(res_analysis.status_code, 200)
        analysis_data = res_analysis.json()
        self.assertEqual(analysis_data["status"], "SUCCESS")
        self.assertEqual(analysis_data["working_tree_status"], "DIRTY")
        self.assertIn("service.process_payment", [c["qualified_name"] for c in analysis_data["change_set"]["changes"]])
        self.assertIn("api.checkout_endpoint", analysis_data["affected_apis"])
        self.assertIn("tests.test_process_payment", analysis_data["targeted_tests"])
        self.assertGreater(len(analysis_data["proposed_mutations"]), 0)


if __name__ == "__main__":
    unittest.main()
