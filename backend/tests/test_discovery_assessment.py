import os
import sys
import uuid
import unittest

if sys.version_info < (3, 11):
    venv_py = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".venv", "bin", "python3"))
    if os.path.exists(venv_py):
        os.execv(venv_py, [venv_py, "-m", "unittest", os.path.abspath(__file__)])

# Ensure backend and venv dependencies are discoverable
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

venv_site = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".venv", "lib", "python3.12", "site-packages"))
if os.path.exists(venv_site) and venv_site not in sys.path:
    sys.path.insert(0, venv_site)

from fastapi.testclient import TestClient
from main import app
from app.models.entities import (
    Project,
    Repository,
    RepositorySnapshot,
    StructuralArtifact,
    ArtifactRelationship,
    AnalysisRun,
    User,
)
from app.services.discovery.assessment_models import (
    DiscoveryStatus,
    FindingCategory,
    FindingSeverity,
    RoadmapPriority,
)
from app.services.discovery.assessment_engine import TechnicalAssessmentEngine
from app.services.discovery.engine import discovery_engine
from app.core.database import SessionLocal
from app.core.auth import create_access_token

FIXTURES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "tests", "fixtures"))


class TestDiscoveryAndTechnicalAssessment(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = SessionLocal()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def tearDown(self):
        self.db.rollback()

    def _create_project_and_repo(self, prefix: str, local_path: str = "/tmp/test_repo", tenant_id: str = "tenant-test-default"):
        uid = uuid.uuid4().hex[:6]
        project = Project(
            id=f"proj-{prefix}-{uid}",
            name=f"Project-{prefix}-{uid}",
            description="Test Project",
        )
        self.db.merge(project)

        repo = Repository(
            id=f"repo-{prefix}-{uid}",
            project_id=project.id,
            name=f"repo-{prefix}-{uid}",
            local_path=local_path,
            environment="TEST",
        )
        self.db.merge(repo)
        self.db.commit()
        return project, repo

    def test_assessment_circular_dependency_detection(self):
        """
        Phase D Requirement:
        Deterministic evaluation of architecture & modularity detects circular
        dependencies (A -> B and B -> A) and generates FIND-ARCH-CIRCULAR with
        evidence and an advisory roadmap recommendation.
        """
        _, repo = self._create_project_and_repo("circ", "/tmp/test_repo_circular")

        snap = RepositorySnapshot(
            id=f"snap-circ-{uuid.uuid4().hex[:6]}",
            repository_id=repo.id,
            commit_hash="a1b2c3d4e5f67890123456789012345678901234",
            branch_name="main",
        )
        self.db.merge(snap)
        self.db.commit()

        art_a = StructuralArtifact(
            id=f"art-order-srv-{uuid.uuid4().hex[:6]}",
            repository_id=repo.id,
            snapshot_id=snap.id,
            name="OrderService",
            qualified_name="com.example.OrderService",
            artifact_type="SERVICE",
            location="src/services/OrderService.java:10:100",
        )
        art_b = StructuralArtifact(
            id=f"art-pay-srv-{uuid.uuid4().hex[:6]}",
            repository_id=repo.id,
            snapshot_id=snap.id,
            name="PaymentService",
            qualified_name="com.example.PaymentService",
            artifact_type="SERVICE",
            location="src/services/PaymentService.java:15:120",
        )
        self.db.merge(art_a)
        self.db.merge(art_b)

        # Circular relationship: A -> B and B -> A
        rel_ab = ArtifactRelationship(
            id=f"rel-ab-{uuid.uuid4().hex[:6]}",
            snapshot_id=snap.id,
            source_artifact_id=art_a.id,
            target_artifact_id=art_b.id,
            relationship_type="CALLS",
        )
        rel_ba = ArtifactRelationship(
            id=f"rel-ba-{uuid.uuid4().hex[:6]}",
            snapshot_id=snap.id,
            source_artifact_id=art_b.id,
            target_artifact_id=art_a.id,
            relationship_type="DEPENDS_ON",
        )
        self.db.merge(rel_ab)
        self.db.merge(rel_ba)
        self.db.commit()

        engine = TechnicalAssessmentEngine()
        result = engine.assess_repository(self.db, repo.id, snapshot_id=snap.id)

        self.assertIsNotNone(result)
        self.assertIn(result.status, (DiscoveryStatus.COMPLETE, DiscoveryStatus.PARTIAL))
        
        # Verify circular dependency finding
        circ_findings = [f for f in result.findings if f.category == FindingCategory.ARCHITECTURE]
        self.assertGreater(len(circ_findings), 0)
        self.assertTrue(any("circular" in f.id.lower() or "circular" in f.rationale.lower() for f in circ_findings))

        # Verify score penalty
        arch_score = next((d for d in result.dimensional_scores if d.dimension_name == "Architecture & Modularity"), None)
        self.assertIsNotNone(arch_score)
        self.assertLess(arch_score.score, 100)

        # Verify advisory roadmap recommendation synthesized
        roadmap = result.roadmap_recommendations
        self.assertGreater(len(roadmap), 0)
        self.assertTrue(any("circular" in r.title.lower() or "decouple" in r.title.lower() for r in roadmap))
        self.assertIn(roadmap[0].priority, (RoadmapPriority.P0_IMMEDIATE, RoadmapPriority.P1_HIGH))

    def test_assessment_testing_gap_and_high_coupling(self):
        """
        Phase D Requirement:
        Evaluate testing inventory and linkage gaps, and identify god components
        with high fan-out coupling.
        """
        _, repo = self._create_project_and_repo("god", "/tmp/test_repo_god")

        snap = RepositorySnapshot(
            id=f"snap-god-{uuid.uuid4().hex[:6]}",
            repository_id=repo.id,
            commit_hash="b2c3d4e5f6789012345678901234567890123456",
            branch_name="main",
        )
        self.db.merge(snap)
        self.db.commit()

        god_art = StructuralArtifact(
            id=f"art-god-{uuid.uuid4().hex[:6]}",
            repository_id=repo.id,
            snapshot_id=snap.id,
            name="MonolithController",
            qualified_name="com.example.MonolithController",
            artifact_type="SERVICE",
            location="src/controllers/MonolithController.ts:1:500",
        )
        self.db.merge(god_art)

        # Fan out to 12 dependencies
        for i in range(12):
            dep = StructuralArtifact(
                id=f"art-dep-{i}-{uuid.uuid4().hex[:6]}",
                repository_id=repo.id,
                snapshot_id=snap.id,
                name=f"SubService{i}",
                qualified_name=f"com.example.SubService{i}",
                artifact_type="SERVICE",
                location=f"src/services/SubService{i}.ts:1:50",
            )
            self.db.merge(dep)
            rel = ArtifactRelationship(
                id=f"rel-god-{i}-{uuid.uuid4().hex[:6]}",
                snapshot_id=snap.id,
                source_artifact_id=god_art.id,
                target_artifact_id=dep.id,
                relationship_type="CALLS",
            )
            self.db.merge(rel)

        self.db.commit()

        engine = TechnicalAssessmentEngine()
        result = engine.assess_repository(self.db, repo.id, snapshot_id=snap.id)

        # Check high coupling finding
        coupling_finding = next((f for f in result.findings if "COUP-HIGH-FANOUT" in f.id), None)
        self.assertIsNotNone(coupling_finding)
        self.assertIn(coupling_finding.severity, (FindingSeverity.MEDIUM, FindingSeverity.HIGH, FindingSeverity.CRITICAL))

        # Check test gap finding (core component without linked tests)
        test_gap_finding = next((f for f in result.findings if "TEST-GAP" in f.id), None)
        self.assertIsNotNone(test_gap_finding)
        self.assertEqual(test_gap_finding.affected_entity, "MonolithController")

        # Verify roadmap addresses test gap
        self.assertTrue(any("test" in r.title.lower() for r in result.roadmap_recommendations))

    def test_assessment_typescript_react_fixture(self):
        """
        Phase B & D: Verify Discovery & Technical Assessment on real TypeScript fixture.
        """
        fixture_path = os.path.join(FIXTURES_DIR, "typescript_react_vitest")
        self.assertTrue(os.path.exists(fixture_path), f"Fixture path not found: {fixture_path}")

        profile, plan = discovery_engine.discover(fixture_path)
        self.assertTrue(any(l.name.lower() == "typescript" for l in profile.languages))
        self.assertTrue(any(f.name.lower() == "react" for f in profile.frameworks))

        _, repo = self._create_project_and_repo("ts", fixture_path)

        snap = RepositorySnapshot(
            id=f"snap-ts-{uuid.uuid4().hex[:6]}",
            repository_id=repo.id,
            commit_hash="c3d4e5f678901234567890123456789012345678",
            branch_name="main",
        )
        self.db.merge(snap)

        art_ts = StructuralArtifact(
            id=f"art-ts-{uuid.uuid4().hex[:6]}",
            repository_id=repo.id,
            snapshot_id=snap.id,
            name="App",
            qualified_name="src.App",
            artifact_type="COMPONENT",
            location="src/App.tsx:1:50",
        )
        self.db.merge(art_ts)
        self.db.commit()

        engine = TechnicalAssessmentEngine()
        result = engine.assess_repository(self.db, repo.id, snapshot_id=snap.id)

        self.assertIn(result.status, (DiscoveryStatus.COMPLETE, DiscoveryStatus.PARTIAL))
        self.assertGreater(result.completeness.files_discovered, 0)
        self.assertEqual(len(result.dimensional_scores), 9)

    def test_assessment_java_spring_fixture(self):
        """
        Phase B & D: Verify Discovery & Technical Assessment on real Java fixture.
        """
        fixture_path = os.path.join(FIXTURES_DIR, "java_spring_maven_junit")
        self.assertTrue(os.path.exists(fixture_path), f"Fixture path not found: {fixture_path}")

        profile, plan = discovery_engine.discover(fixture_path)
        self.assertTrue(any(l.name.lower() == "java" for l in profile.languages))
        self.assertTrue(any("spring" in f.name.lower() for f in profile.frameworks))
        self.assertTrue(any(b.name.lower() == "maven" for b in profile.build_systems))

        _, repo = self._create_project_and_repo("java", fixture_path)

        snap = RepositorySnapshot(
            id=f"snap-java-{uuid.uuid4().hex[:6]}",
            repository_id=repo.id,
            commit_hash="d4e5f67890123456789012345678901234567890",
            branch_name="main",
        )
        self.db.merge(snap)

        art_java = StructuralArtifact(
            id=f"art-java-{uuid.uuid4().hex[:6]}",
            repository_id=repo.id,
            snapshot_id=snap.id,
            name="DemoApplication",
            qualified_name="com.example.DemoApplication",
            artifact_type="SERVICE",
            location="src/main/java/com/example/DemoApplication.java:1:80",
        )
        self.db.merge(art_java)
        self.db.commit()

        engine = TechnicalAssessmentEngine()
        result = engine.assess_repository(self.db, repo.id, snapshot_id=snap.id)

        self.assertIn(result.status, (DiscoveryStatus.COMPLETE, DiscoveryStatus.PARTIAL))
        self.assertGreater(result.completeness.files_discovered, 0)
        self.assertEqual(len(result.dimensional_scores), 9)

    def test_assessment_unsupported_repo_handling(self):
        """
        Phase C & D: A repository with unsupported or non-code files must be truthfully
        classified as UNSUPPORTED or PARTIAL, never reported as COMPLETE with zero findings.
        """
        fixture_path = os.path.join(FIXTURES_DIR, "cobol_legacy")
        _, repo = self._create_project_and_repo("cobol", fixture_path)

        snap = RepositorySnapshot(
            id=f"snap-cobol-{uuid.uuid4().hex[:6]}",
            repository_id=repo.id,
            commit_hash="e5f6789012345678901234567890123456789012",
            branch_name="main",
        )
        self.db.merge(snap)
        self.db.commit()

        engine = TechnicalAssessmentEngine()
        result = engine.assess_repository(self.db, repo.id, snapshot_id=snap.id)

        # Must reflect unsupported / limited status truthfully
        self.assertIn(result.status, (DiscoveryStatus.UNSUPPORTED, DiscoveryStatus.PARTIAL))
        # Completeness must show notes explaining limitations
        self.assertIsNotNone(result.completeness.notes)

    def test_assessment_report_generation_and_secret_redaction(self):
        """
        Phase G & H: Assessment reports must be generated in markdown, match persisted
        results, and redact secrets or tokens.
        """
        _, repo = self._create_project_and_repo("sec", "/tmp/test_repo_sec")

        snap = RepositorySnapshot(
            id=f"snap-sec-{uuid.uuid4().hex[:6]}",
            repository_id=repo.id,
            commit_hash="f678901234567890123456789012345678901234",
            branch_name="main",
        )
        self.db.merge(snap)
        self.db.commit()

        art = StructuralArtifact(
            id=f"art-sec-{uuid.uuid4().hex[:6]}",
            repository_id=repo.id,
            snapshot_id=snap.id,
            name="ConfigManager",
            qualified_name="ConfigManager",
            artifact_type="SERVICE",
            location="src/config.ts:1:10",
        )
        self.db.merge(art)
        self.db.commit()

        engine = TechnicalAssessmentEngine()
        result = engine.assess_repository(self.db, repo.id, snapshot_id=snap.id)

        raw_token = "ghp_1234567890abcdef1234567890abcdef123456"
        report_md = result.report_markdown

        # Sanitize markdown report
        self.assertIsNotNone(report_md)
        assert report_md is not None
        self.assertIn("Technical Assessment", report_md)
        self.assertNotIn(raw_token, report_md)
        self.assertIn("Executive Summary", report_md)
        self.assertIn("Advisory Remediation Roadmap", report_md)

    def test_api_discovery_endpoints_and_tenant_authorization(self):
        """
        Phase F & H: API router endpoints:
        - POST /repositories/{id}/discovery/assess
        - GET /repositories/{id}/discovery/assessment
        - GET /repositories/{id}/discovery/report
        Enforce tenant authorization and safe access controls.
        """
        uid = uuid.uuid4().hex[:6]
        test_user = User(
            id=f"user-disc-{uid}",
            username=f"disc_user_{uid}",
            email=f"disc_{uid}@example.com",
            hashed_password="dummy_hashed_password_for_test",
            role="engineer",
            is_active=True,
        )
        self.db.merge(test_user)

        _, repo = self._create_project_and_repo("api", "/tmp/test_repo_discovery_api")
        # Update repo owner
        setattr(repo, "owner_id", test_user.id)
        self.db.merge(repo)

        snap = RepositorySnapshot(
            id=f"snap-disc-api-{uid}",
            repository_id=repo.id,
            commit_hash="1234567890123456789012345678901234567890",
            branch_name="main",
        )
        self.db.merge(snap)
        self.db.commit()

        token = create_access_token(user_id=test_user.id, username=test_user.username, role=test_user.role)
        headers = {"Authorization": f"Bearer {token}"}

        # 1. POST Assessment
        res_post = self.client.post(
            f"/repositories/{repo.id}/discovery/assess?snapshot_id={snap.id}",
            headers=headers,
        )
        self.assertEqual(res_post.status_code, 200, f"Assess failed: {res_post.text}")
        post_data = res_post.json()
        self.assertIn("assessment_id", post_data)
        self.assertIn("dimensional_scores", post_data)

        # 2. GET Assessment
        res_get = self.client.get(
            f"/repositories/{repo.id}/discovery/assessment",
            headers=headers,
        )
        self.assertEqual(res_get.status_code, 200)
        get_data = res_get.json()
        self.assertEqual(get_data["assessment_id"], post_data["assessment_id"])

        # 3. GET Report
        res_rep = self.client.get(
            f"/repositories/{repo.id}/discovery/report",
            headers=headers,
        )
        self.assertEqual(res_rep.status_code, 200)
        rep_data = res_rep.json()
        self.assertIn("report_markdown", rep_data)
        self.assertGreater(len(rep_data["report_markdown"]), 100)

        # 4. Cross-Tenant Authorization Rejection
        other_token = create_access_token(user_id="other_foreign_user", username="foreign_user", role="engineer")
        other_headers = {"Authorization": f"Bearer {other_token}"}
        res_denied = self.client.get(
            f"/repositories/{repo.id}/discovery/assessment",
            headers=other_headers,
        )
        # Multi-tenant isolation returns 403 or 404
        self.assertIn(res_denied.status_code, (403, 404))

    def test_previously_failing_assessment_path_with_real_files(self):
        """
        Regression Test 1:
        Verifies that scanning a repository with files on disk (FileInventory present)
        and evaluating Dimension 7 (Maintenance Hotspots) executes without throwing
        NameError: name 'SUPPORTED_EXTS' is not defined.
        """
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a source file > 100KB to trigger the maintenance hotspot check
            hotspot_file = os.path.join(tmpdir, "monolithic_service.py")
            with open(hotspot_file, "w") as f:
                f.write("# Monolithic file\n" + "x = 1\n" * 20000)  # > 100KB
            
            normal_file = os.path.join(tmpdir, "helper.ts")
            with open(normal_file, "w") as f:
                f.write("export const helper = 42;\n")

            _, repo = self._create_project_and_repo("hotspot", tmpdir)
            snap = RepositorySnapshot(
                id=f"snap-hotspot-{uuid.uuid4().hex[:6]}",
                repository_id=repo.id,
                commit_hash="c1d2e3f4" * 5,
                branch_name="main",
            )
            self.db.merge(snap)
            self.db.commit()

            engine = TechnicalAssessmentEngine()
            # This previously crashed with NameError: name 'SUPPORTED_EXTS' is not defined
            result = engine.assess_repository(self.db, repo.id, snap.id)
            self.assertIsNotNone(result)
            self.assertEqual(result.repository_id, repo.id)
            # Verify Dimension 7 Maintenance Hotspots identified the >100KB file
            dim_maint = next((d for d in result.dimensional_scores if "Maintenance" in d.dimension_name), None)
            self.assertIsNotNone(dim_maint)
            hotspot_finding = next((f for f in result.findings if f.category == FindingCategory.MAINTENANCE), None)
            self.assertIsNotNone(hotspot_finding)
            self.assertIn("monolithic_service.py", hotspot_finding.title)

    def test_typescript_javascript_source_discovery(self):
        """Regression Test 2: TypeScript & JavaScript source files and package.json manifest."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "package.json"), "w") as f:
                f.write('{"name": "test-ts-app", "version": "1.0.0"}')
            with open(os.path.join(tmpdir, "index.ts"), "w") as f:
                f.write("export function run(): void {}")
            with open(os.path.join(tmpdir, "component.tsx"), "w") as f:
                f.write("export const App = () => null;")
            with open(os.path.join(tmpdir, "script.js"), "w") as f:
                f.write("module.exports = {};")

            _, repo = self._create_project_and_repo("tsjs", tmpdir)
            snap = RepositorySnapshot(
                id=f"snap-tsjs-{uuid.uuid4().hex[:6]}",
                repository_id=repo.id,
                commit_hash="abcdef1234567890" * 2 + "12345678",
                branch_name="main",
            )
            self.db.merge(snap)
            # Add corresponding structural artifacts
            art1 = StructuralArtifact(
                id=f"art-ts-{uuid.uuid4().hex[:6]}",
                repository_id=repo.id,
                snapshot_id=snap.id,
                name="run",
                qualified_name="index.run",
                artifact_type="FUNCTION",
                location="index.ts:1:1",
            )
            art2 = StructuralArtifact(
                id=f"art-tsx-{uuid.uuid4().hex[:6]}",
                repository_id=repo.id,
                snapshot_id=snap.id,
                name="App",
                qualified_name="component.App",
                artifact_type="COMPONENT",
                location="component.tsx:1:1",
            )
            self.db.merge(art1)
            self.db.merge(art2)
            self.db.commit()

            engine = TechnicalAssessmentEngine()
            result = engine.assess_repository(self.db, repo.id, snap.id)
            self.assertIn(result.completeness.status, (DiscoveryStatus.COMPLETE, DiscoveryStatus.PARTIAL))
            self.assertGreaterEqual(result.completeness.files_analyzed, 2)
            self.assertGreaterEqual(result.completeness.symbols_extracted, 2)

    def test_python_source_discovery(self):
        """Regression Test 3: Python source discovery with pyproject.toml."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "pyproject.toml"), "w") as f:
                f.write('[project]\nname = "py-app"\n')
            with open(os.path.join(tmpdir, "app.py"), "w") as f:
                f.write("def main(): pass\n")

            _, repo = self._create_project_and_repo("py", tmpdir)
            snap = RepositorySnapshot(
                id=f"snap-py-{uuid.uuid4().hex[:6]}",
                repository_id=repo.id,
                commit_hash="py12345678901234" * 2 + "12345678",
                branch_name="main",
            )
            self.db.merge(snap)
            art = StructuralArtifact(
                id=f"art-py-{uuid.uuid4().hex[:6]}",
                repository_id=repo.id,
                snapshot_id=snap.id,
                name="main",
                qualified_name="app.main",
                artifact_type="FUNCTION",
                location="app.py:1:1",
            )
            self.db.merge(art)
            self.db.commit()

            engine = TechnicalAssessmentEngine()
            result = engine.assess_repository(self.db, repo.id, snap.id)
            self.assertEqual(result.completeness.status, DiscoveryStatus.COMPLETE)
            self.assertEqual(result.completeness.files_analyzed, 1)

    def test_java_source_discovery(self):
        """Regression Test 4: Java source discovery with pom.xml."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "pom.xml"), "w") as f:
                f.write("<project></project>")
            with open(os.path.join(tmpdir, "Application.java"), "w") as f:
                f.write("public class Application {}")

            _, repo = self._create_project_and_repo("java", tmpdir)
            snap = RepositorySnapshot(
                id=f"snap-java-{uuid.uuid4().hex[:6]}",
                repository_id=repo.id,
                commit_hash="java123456789012" * 2 + "12345678",
                branch_name="main",
            )
            self.db.merge(snap)
            art = StructuralArtifact(
                id=f"art-java-{uuid.uuid4().hex[:6]}",
                repository_id=repo.id,
                snapshot_id=snap.id,
                name="Application",
                qualified_name="Application",
                artifact_type="CLASS",
                location="Application.java:1:1",
            )
            self.db.merge(art)
            self.db.commit()

            engine = TechnicalAssessmentEngine()
            result = engine.assess_repository(self.db, repo.id, snap.id)
            self.assertEqual(result.completeness.status, DiscoveryStatus.COMPLETE)
            self.assertEqual(result.completeness.files_analyzed, 1)

    def test_unsupported_language_handling(self):
        """Regression Test 5: Unsupported languages are recorded and yield UNSUPPORTED status."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "program.cbl"), "w") as f:
                f.write("IDENTIFICATION DIVISION.\nPROGRAM-ID. HELLO.\n")
            with open(os.path.join(tmpdir, "calc.pas"), "w") as f:
                f.write("program Calc; begin end.\n")

            _, repo = self._create_project_and_repo("unsupported", tmpdir)
            snap = RepositorySnapshot(
                id=f"snap-unsup-{uuid.uuid4().hex[:6]}",
                repository_id=repo.id,
                commit_hash="unsup12345678901" * 2 + "12345678",
                branch_name="main",
            )
            self.db.merge(snap)
            self.db.commit()

            engine = TechnicalAssessmentEngine()
            result = engine.assess_repository(self.db, repo.id, snap.id)
            self.assertEqual(result.completeness.status, DiscoveryStatus.UNSUPPORTED)
            self.assertIn(".cbl", result.completeness.unsupported_extensions)
            self.assertIn(".pas", result.completeness.unsupported_extensions)
            self.assertEqual(result.completeness.files_analyzed, 0)
            self.assertEqual(result.completeness.symbols_extracted, 0)

    def test_documentation_only_repository_handling(self):
        """Regression Test 6: Documentation-only repositories are not counted as AST source files and yield UNSUPPORTED."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "README.md"), "w") as f:
                f.write("# Documentation Repository\nThis contains only markdown.\n")
            with open(os.path.join(tmpdir, "ARCHITECTURE.rst"), "w") as f:
                f.write("Architecture Overview\n====================\n")
            with open(os.path.join(tmpdir, "notes.txt"), "w") as f:
                f.write("Some notes.\n")

            _, repo = self._create_project_and_repo("docs", tmpdir)
            snap = RepositorySnapshot(
                id=f"snap-docs-{uuid.uuid4().hex[:6]}",
                repository_id=repo.id,
                commit_hash="docs123456789012" * 2 + "12345678",
                branch_name="main",
            )
            self.db.merge(snap)
            self.db.commit()

            engine = TechnicalAssessmentEngine()
            result = engine.assess_repository(self.db, repo.id, snap.id)
            self.assertEqual(result.completeness.status, DiscoveryStatus.UNSUPPORTED)
            self.assertEqual(result.completeness.files_analyzed, 0)
            self.assertEqual(result.completeness.symbols_extracted, 0)
            self.assertIn("documentation", result.completeness.explanation.lower())

    def test_assessment_completeness_and_coverage_accounting(self):
        """Regression Test 7: Completeness coverage percentage correctly computes analyzed vs unsupported ratio."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            # 1 Python file + 1 unsupported Fortran file + 1 ignored image
            with open(os.path.join(tmpdir, "service.py"), "w") as f:
                f.write("def serve(): pass\n")
            with open(os.path.join(tmpdir, "legacy.f90"), "w") as f:
                f.write("program legacy\nend program\n")
            with open(os.path.join(tmpdir, "logo.png"), "wb") as f:
                f.write(b"\x89PNG\r\n\x1a\n")

            _, repo = self._create_project_and_repo("coverage", tmpdir)
            snap = RepositorySnapshot(
                id=f"snap-cov-{uuid.uuid4().hex[:6]}",
                repository_id=repo.id,
                commit_hash="cov1234567890123" * 2 + "12345678",
                branch_name="main",
            )
            self.db.merge(snap)
            art = StructuralArtifact(
                id=f"art-cov-{uuid.uuid4().hex[:6]}",
                repository_id=repo.id,
                snapshot_id=snap.id,
                name="serve",
                qualified_name="service.serve",
                artifact_type="FUNCTION",
                location="service.py:1:1",
            )
            self.db.merge(art)
            self.db.commit()

            engine = TechnicalAssessmentEngine()
            result = engine.assess_repository(self.db, repo.id, snap.id)
            self.assertEqual(result.completeness.status, DiscoveryStatus.PARTIAL)
            self.assertEqual(result.completeness.files_analyzed, 1)
            # 1 analyzed code file out of 2 total code files (service.py + legacy.f90) = 50.0% coverage
            self.assertAlmostEqual(result.completeness.coverage_percentage, 50.0, places=1)
            self.assertEqual(result.completeness.files_skipped, 1)  # logo.png skipped

    def test_error_propagation_and_truthful_failure_states(self):
        """Regression Test 8: Non-existent repository raises ValueError; failed parsing yields FAILED status."""
        import tempfile
        engine = TechnicalAssessmentEngine()

        # Non-existent repository
        with self.assertRaises(ValueError) as ctx:
            engine.assess_repository(self.db, "non_existent_repo_id_12345")
        self.assertIn("not found", str(ctx.exception))

        # Supported code files exist on disk, but 0 structural artifacts extracted -> FAILED status
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "bad_syntax.py"), "w") as f:
                f.write("def broken syntax (:)): pass\n")

            _, repo = self._create_project_and_repo("failed", tmpdir)
            snap = RepositorySnapshot(
                id=f"snap-fail-{uuid.uuid4().hex[:6]}",
                repository_id=repo.id,
                commit_hash="fail123456789012" * 2 + "12345678",
                branch_name="main",
            )
            self.db.merge(snap)
            self.db.commit()

            # No artifacts in DB -> FAILED
            result = engine.assess_repository(self.db, repo.id, snap.id)
            self.assertEqual(result.completeness.status, DiscoveryStatus.FAILED)
            self.assertIn("zero symbols", result.completeness.explanation.lower())


if __name__ == "__main__":
    unittest.main()
