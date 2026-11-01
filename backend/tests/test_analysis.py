"""
Integration and Unit Tests for Phase 3: Structural Intelligence & Digital Twin Builder.

Validates:
1. Tree-sitter adapter parsing for Python, Java, JS, TS.
2. Deep AST structural extractors (classes, methods, functions, imports, calls, exports).
3. Framework & test mappings (FastAPI/Spring endpoints, Pytest/JUnit/Vitest test links).
4. Secondary analyzers (COBOL, C++, SQL, Docker).
5. Deterministic hashing & idempotency.
6. Twin persistence and snapshot awareness.
7. Twin Query Service & NetworkX Graph Projection.
8. End-to-end multi-language analysis on polyglot_microservice fixture.
"""

from pathlib import Path
import pytest
from sqlalchemy.orm import Session

from app.services.analysis.parsers.treesitter_adapter import TreeSitterAdapter
from app.services.analysis.analyzers.python_analyzer import PythonStructuralAnalyzer
from app.services.analysis.analyzers.java_analyzer import JavaStructuralAnalyzer
from app.services.analysis.analyzers.typescript_analyzer import TypeScriptStructuralAnalyzer
from app.services.analysis.analyzers.javascript_analyzer import JavaScriptStructuralAnalyzer
from app.services.analysis.analyzers.secondary_analyzers import (
    CobolStructuralAnalyzer,
    CppStructuralAnalyzer,
    DatabaseStructuralAnalyzer,
    DockerStructuralAnalyzer,
)
from app.services.analysis.runtime.result import ArtifactType, RelationshipType
from app.services.analysis.normalizers.identity import build_artifact_id, build_relationship_id
from app.services.analysis.engine import structural_twin_engine
from app.services.analysis.query.twin_query_service import twin_query_service
from app.services.analysis.graph.projection import graph_projection_service
from app.services.discovery.engine import discovery_engine
from app.services.discovery.scanner import RepositoryScanner
from app.services.analysis.runtime.context import AnalysisContext
from app.models.entities import (
    Repository,
    Snapshot,
    StructuralArtifact,
    ArtifactRelationship,
    AnalysisRun,
    Project,
)

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures"


class TestTreeSitterAdapter:
    """Validates parser adapter infrastructure across supported languages."""

    def test_python_parsing(self):
        adapter = TreeSitterAdapter("python")
        code = b"def greet(name: str):\n    return f'Hello, {name}'\n"
        res = adapter.parse_source(code, "test.py")
        assert res.success is True
        assert res.root_node is not None
        assert res.root_node.node_type == "module"
        assert len(res.root_node.children) > 0

    def test_java_parsing(self):
        adapter = TreeSitterAdapter("java")
        code = b"public class App {\n    public static void main(String[] args) {}\n}\n"
        res = adapter.parse_source(code, "App.java")
        assert res.success is True
        assert res.root_node.node_type == "program"

    def test_javascript_and_typescript_parsing(self):
        js_adapter = TreeSitterAdapter("javascript")
        js_code = b"function add(a, b) { return a + b; }\n"
        js_res = js_adapter.parse_source(js_code, "app.js")
        assert js_res.success is True

        ts_adapter = TreeSitterAdapter("typescript")
        ts_code = b"interface User { id: string; }\nconst u: User = { id: '1' };\n"
        ts_res = ts_adapter.parse_source(ts_code, "types.ts")
        assert ts_res.success is True


class TestDeterministicIdentity:
    """Verifies that entity and relationship IDs are strictly deterministic and snapshot-isolated."""

    def test_stable_artifact_id(self):
        id1 = build_artifact_id("snap_1", "python", "app.py", ArtifactType.CLASS, "OrderService")
        id2 = build_artifact_id("snap_1", "python", "app.py", ArtifactType.CLASS, "OrderService")
        id3 = build_artifact_id("snap_2", "python", "app.py", ArtifactType.CLASS, "OrderService")
        assert id1 == id2
        assert id1.startswith("art_")
        assert id1 != id3  # Snapshot-isolated

    def test_stable_relationship_id(self):
        rel1 = build_relationship_id("snap_1", "art_a", RelationshipType.CALLS, "art_b")
        rel2 = build_relationship_id("snap_1", "art_a", RelationshipType.CALLS, "art_b")
        rel3 = build_relationship_id("snap_1", "art_a", RelationshipType.IMPORTS, "art_b")
        assert rel1 == rel2
        assert rel1.startswith("rel_")
        assert rel1 != rel3


class TestDeepStructuralAnalyzers:
    """Validates structural extraction logic for primary languages."""

    def test_python_analyzer_extraction(self):
        py_fixture = FIXTURES_DIR / "python_fastapi_pytest"
        scanner = RepositoryScanner()
        inventory = scanner.scan(str(py_fixture))
        context = AnalysisContext(
            repository_id="repo_py",
            repository_path=str(py_fixture),
            snapshot_id="snap_test_py",
        )
        analyzer = PythonStructuralAnalyzer()
        artifacts, rels, evidence, warnings = analyzer.analyze_repository(context, inventory)

        artifact_names = {a.name for a in artifacts}
        artifact_types = {a.artifact_type for a in artifacts}

        # Expected classes, methods, functions
        assert "OrderService" in artifact_names
        assert "create_order" in artifact_names
        assert "calculate_total" in artifact_names
        assert ArtifactType.CLASS in artifact_types
        assert ArtifactType.METHOD in artifact_types
        assert ArtifactType.FUNCTION in artifact_types

        # Verify FastAPI endpoint detection
        api_endpoints = [a for a in artifacts if a.artifact_type == ArtifactType.API_ENDPOINT]
        assert len(api_endpoints) >= 1
        assert any("POST" in ep.name for ep in api_endpoints)

        # Verify Pytest test function and TESTS relationship
        test_cases = [a for a in artifacts if a.artifact_type == ArtifactType.TEST_CASE]
        assert any(tc.name == "test_create_order" for tc in test_cases)
        tests_rels = [r for r in rels if r.relationship_type == RelationshipType.TESTS]
        assert len(tests_rels) >= 1

    def test_java_analyzer_extraction(self):
        java_fixture = FIXTURES_DIR / "java_spring_maven_junit"
        scanner = RepositoryScanner()
        inventory = scanner.scan(str(java_fixture))
        context = AnalysisContext(
            repository_id="repo_java",
            repository_path=str(java_fixture),
            snapshot_id="snap_test_java",
        )
        analyzer = JavaStructuralAnalyzer()
        artifacts, rels, evidence, warnings = analyzer.analyze_repository(context, inventory)

        artifact_names = {a.name for a in artifacts}
        assert "PaymentController" in artifact_names
        assert "getPayments" in artifact_names

        # Spring API endpoints
        endpoints = [a for a in artifacts if a.artifact_type == ArtifactType.API_ENDPOINT]
        assert len(endpoints) >= 1

        # JUnit tests
        test_artifacts = [a for a in artifacts if a.artifact_type == ArtifactType.TEST_CASE]
        assert any(t.name == "testPaymentProcessing" for t in test_artifacts)

    def test_typescript_analyzer_extraction(self):
        ts_fixture = FIXTURES_DIR / "typescript_react_vitest"
        scanner = RepositoryScanner()
        inventory = scanner.scan(str(ts_fixture))
        context = AnalysisContext(
            repository_id="repo_ts",
            repository_path=str(ts_fixture),
            snapshot_id="snap_test_ts",
        )
        analyzer = TypeScriptStructuralAnalyzer()
        artifacts, rels, evidence, warnings = analyzer.analyze_repository(context, inventory)

        names = {a.name for a in artifacts}
        assert "App" in names or "render" in names or any("test" in n.lower() for n in names)
        exports = [r for r in rels if r.relationship_type == RelationshipType.EXPORTS]
        assert len(exports) >= 1

    def test_javascript_analyzer_extraction(self):
        js_fixture = FIXTURES_DIR / "javascript_node"
        scanner = RepositoryScanner()
        inventory = scanner.scan(str(js_fixture))
        context = AnalysisContext(
            repository_id="repo_js",
            repository_path=str(js_fixture),
            snapshot_id="snap_test_js",
        )
        analyzer = JavaScriptStructuralAnalyzer()
        artifacts, rels, evidence, warnings = analyzer.analyze_repository(context, inventory)

        names = {a.name for a in artifacts}
        assert "calculateFee" in names


class TestSecondaryAnalyzers:
    """Validates secondary language extractors (COBOL, C++, SQL, Docker)."""

    def test_cobol_analyzer(self):
        cobol_fixture = FIXTURES_DIR / "cobol_legacy"
        scanner = RepositoryScanner()
        inventory = scanner.scan(str(cobol_fixture))
        context = AnalysisContext(
            repository_id="repo_cobol",
            repository_path=str(cobol_fixture),
            snapshot_id="snap_test_cobol",
        )
        analyzer = CobolStructuralAnalyzer()
        artifacts, rels, evidence, warnings = analyzer.analyze_repository(context, inventory)

        names = {a.name for a in artifacts}
        assert "IDENTIFICATION_DIVISION" in names
        assert "PROCEDURE_DIVISION" in names
        copy_rels = [r for r in rels if r.relationship_type == RelationshipType.COPY_DEPENDS_ON]
        assert len(copy_rels) >= 1

    def test_cpp_analyzer(self):
        cpp_fixture = FIXTURES_DIR / "cpp_cmake"
        scanner = RepositoryScanner()
        inventory = scanner.scan(str(cpp_fixture))
        context = AnalysisContext(
            repository_id="repo_cpp",
            repository_path=str(cpp_fixture),
            snapshot_id="snap_test_cpp",
        )
        analyzer = CppStructuralAnalyzer()
        artifacts, rels, evidence, warnings = analyzer.analyze_repository(context, inventory)

        names = {a.name for a in artifacts}
        assert "CoreEngine" in names

    def test_database_and_docker_analyzers(self):
        poly_fixture = FIXTURES_DIR / "polyglot_microservice"
        scanner = RepositoryScanner()
        inventory = scanner.scan(str(poly_fixture))
        context = AnalysisContext(
            repository_id="repo_poly",
            repository_path=str(poly_fixture),
            snapshot_id="snap_test_poly",
        )

        db_analyzer = DatabaseStructuralAnalyzer()
        db_arts, db_rels, db_ev, db_warn = db_analyzer.analyze_repository(context, inventory)
        db_names = {a.name for a in db_arts}
        assert "payments" in db_names

        docker_analyzer = DockerStructuralAnalyzer()
        doc_arts, doc_rels, doc_ev, doc_warn = docker_analyzer.analyze_repository(context, inventory)
        assert len(doc_arts) >= 2


class TestEndToEndStructuralTwin:
    """Full database-backed integration test: discovery -> planning -> twin analysis -> persistence -> query -> graph."""

    def test_full_polyglot_analysis_and_idempotency(self, db_session: Session):
        repo_path = str(FIXTURES_DIR / "polyglot_microservice")

        # 0. Create Project and Repository records
        import uuid
        proj = Project(
            id=str(uuid.uuid4()),
            name=f"Polyglot Project {uuid.uuid4().hex[:6]}",
            description="Polyglot test project",
        )
        db_session.add(proj)
        db_session.flush()

        repo = Repository(
            id=str(uuid.uuid4()),
            project_id=proj.id,
            name="polyglot_microservice",
            local_path=repo_path,
        )
        db_session.add(repo)
        db_session.commit()

        # 1. Run Analysis Pipeline
        snapshot_id, run_result = structural_twin_engine.build_structural_twin(
            db=db_session,
            repository_id=repo.id,
            commit_hash="abc123456789",
            branch_name="main",
        )

        assert run_result.status == "COMPLETED"
        assert len(run_result.artifacts) > 0
        assert len(run_result.relationships) > 0
        assert len(run_result.evidence) > 0

        # 2. Verify Database Records
        db_artifacts = db_session.query(StructuralArtifact).filter(StructuralArtifact.snapshot_id == snapshot_id).all()
        assert len(db_artifacts) == len(run_result.artifacts)

        db_rels = db_session.query(ArtifactRelationship).filter(ArtifactRelationship.snapshot_id == snapshot_id).all()
        assert len(db_rels) == len(run_result.relationships)

        run = db_session.query(AnalysisRun).filter(AnalysisRun.snapshot_id == snapshot_id).first()
        assert run is not None
        assert run.status == "COMPLETED"

        # 3. Test Twin Query Service
        twin_data = twin_query_service.get_twin(db_session, repo.id, snapshot_id)
        assert twin_data["summary"]["total_artifacts"] == len(db_artifacts)
        assert twin_data["summary"]["total_relationships"] == len(db_rels)

        classes = twin_query_service.get_artifacts_by_type(db_session, repo.id, "CLASS", snapshot_id)
        assert len(classes) > 0

        # Query dependencies of first artifact with relationships
        rel = db_rels[0]
        deps = twin_query_service.get_dependencies(db_session, rel.source_artifact_id)
        assert len(deps) >= 1

        # 4. Test NetworkX Graph Projection
        nx_graph = graph_projection_service.project_to_networkx(db_session, snapshot_id)
        assert nx_graph.number_of_nodes() == len(db_artifacts)
        assert nx_graph.number_of_edges() == len(db_rels)

        summary = graph_projection_service.get_graph_summary(db_session, snapshot_id)
        assert summary["nodes"] == len(db_artifacts)
        assert summary["edges"] == len(db_rels)

        # 5. Test Idempotency (Re-running on the exact same snapshot should not create duplicate entries)
        re_snap_id, re_run_result = structural_twin_engine.build_structural_twin(
            db=db_session,
            repository_id=repo.id,
            commit_hash="abc123456789",
            branch_name="main",
        )
        assert re_run_result.status == "COMPLETED"
        assert re_snap_id == snapshot_id

        # Artifacts count in DB must remain identical, not doubled
        post_count = db_session.query(StructuralArtifact).filter(StructuralArtifact.snapshot_id == snapshot_id).count()
        assert post_count == len(db_artifacts)

    def test_oversized_artifact_and_relationship_truncation_safety(self, db_session: Session):
        """Verifies that strings exceeding column limits (e.g. >255 chars name, >1024 chars qualname)
        are safely bounded without throwing psycopg2.errors.StringDataRightTruncation."""
        from app.services.analysis.runtime.result import AnalysisRunResult, ExtractedArtifact, ExtractedRelationship
        from app.services.analysis.persistence.twin_writer import twin_writer
        from app.services.discovery.scanner import FileInventory
        import uuid

        proj = Project(
            id=str(uuid.uuid4()),
            name=f"Stress Project {uuid.uuid4().hex[:6]}",
            description="Testing schema truncation bounds",
        )
        db_session.add(proj)
        db_session.flush()

        repo = Repository(
            id=str(uuid.uuid4()),
            project_id=proj.id,
            name="stress_repo",
            local_path="/tmp/stress_repo",
        )
        db_session.add(repo)
        db_session.commit()

        snapshot_id = f"snap_{uuid.uuid4().hex[:16]}"
        oversized_name = "function_call_with_very_long_expression_" + ("x" * 300)
        oversized_qual = "module.submodule.class." + ("y" * 1200)
        oversized_target = "LiteLLMProvider(model=\"vendor/reasoner\")." + ("z" * 400)

        art1 = ExtractedArtifact(
            id=f"art_{uuid.uuid4().hex[:20]}",
            artifact_type=ArtifactType.FUNCTION,
            language="python",
            name=oversized_name,
            qualified_name=oversized_qual,
            file_path="src/long_file.py",
            line_start=1,
            line_end=10,
            analyzer_source="python_ast",
            confidence=1.0,
        )

        rel1 = ExtractedRelationship(
            id=f"rel_{uuid.uuid4().hex[:20]}",
            source_qualified_name=oversized_qual,
            target_qualified_name=oversized_target,
            relationship_type=RelationshipType.CALLS,
            confidence=0.9,
            detection_method="ast_call_expression",
            source_location="src/long_file.py:5",
        )

        run_result = AnalysisRunResult(
            run_id=f"run_{uuid.uuid4().hex[:16]}",
            repository_id=repo.id,
            snapshot_id=snapshot_id,
            status="COMPLETED",
            artifacts=[art1],
            relationships=[rel1],
            evidence_items=[],
        )

        inventory = FileInventory(root_path="/tmp/stress_repo", files=[], total_files=0, total_lines=0)

        # Must execute write_twin cleanly without StringDataRightTruncation
        analysis_run = twin_writer.write_twin(
            db=db_session,
            repository_id=repo.id,
            snapshot_id=snapshot_id,
            inventory=inventory,
            result=run_result,
        )
        assert analysis_run is not None

        # Verify artifacts in database have their fields clamped to column constraints
        persisted_arts = db_session.query(StructuralArtifact).filter_by(snapshot_id=snapshot_id).all()
        assert len(persisted_arts) >= 2  # The explicit artifact + inferred external dependency
        for a in persisted_arts:
            assert len(a.name) <= 512
            assert len(a.qualified_name) <= 2048

    def test_long_identifier_and_path_round_trip_persistence(self, db_session: Session):
        """
        P1-DB-02 Regression Test:
        Verifies that qualified names, artifact locations, and relationship source locations
        longer than 255 characters (e.g. 350-character path/qualname) survive round-trip
        persistence intact without unexpected 255-char truncation.
        """
        from app.services.analysis.runtime.result import AnalysisRunResult, ExtractedArtifact, ExtractedRelationship
        from app.services.analysis.persistence.twin_writer import twin_writer
        from app.services.discovery.scanner import FileInventory
        import uuid

        proj = Project(
            id=str(uuid.uuid4()),
            name=f"Long ID Project {uuid.uuid4().hex[:6]}",
        )
        db_session.add(proj)
        db_session.flush()

        repo = Repository(
            id=str(uuid.uuid4()),
            project_id=proj.id,
            name="long_id_repo",
            local_path="/tmp/long_id_repo",
        )
        db_session.add(repo)
        db_session.commit()

        snapshot_id = f"snap_{uuid.uuid4().hex[:16]}"
        long_name = "ClassWithRelativelyLongName"
        # 300 character qualified name (> 255 characters)
        long_qual = "enterprise.core.services.billing.checkout.v2.internal." + ("subcomponent_" * 15) + ".Processor"
        assert len(long_qual) > 255, f"Test setup error: long_qual must exceed 255 (len={len(long_qual)})"

        # 300 character file path (> 255 characters)
        deep_dir = "/".join(["nested_module_level_" + str(i) for i in range(12)])
        long_file_path = f"{deep_dir}/very_deep_processor_implementation.py"
        assert len(long_file_path) > 255, f"Test setup error: long_file_path must exceed 255 (len={len(long_file_path)})"

        # Long external target identifier (> 255 characters)
        long_target_qual = "org.springframework.cloud.gateway.filter.factory.rewrite." + ("TargetFilter_" * 20) + "Service"
        assert len(long_target_qual) > 255, f"Test setup error: long_target_qual must exceed 255 (len={len(long_target_qual)})"

        long_src_loc = f"{long_file_path}:142"

        art = ExtractedArtifact(
            id=f"art_{uuid.uuid4().hex[:20]}",
            artifact_type=ArtifactType.CLASS,
            language="python",
            name=long_name,
            qualified_name=long_qual,
            file_path=long_file_path,
            line_start=142,
            line_end=200,
            analyzer_source="python_ast",
            confidence=1.0,
        )

        rel = ExtractedRelationship(
            id=f"rel_{uuid.uuid4().hex[:20]}",
            source_qualified_name=long_qual,
            target_qualified_name=long_target_qual,
            relationship_type=RelationshipType.CALLS,
            confidence=1.0,
            detection_method="ast_call_expression",
            source_location=long_src_loc,
        )

        run_result = AnalysisRunResult(
            run_id=f"run_{uuid.uuid4().hex[:16]}",
            repository_id=repo.id,
            snapshot_id=snapshot_id,
            status="COMPLETED",
            artifacts=[art],
            relationships=[rel],
            evidence_items=[],
        )

        inventory = FileInventory(root_path="/tmp/long_id_repo", files=[], total_files=0, total_lines=0)

        # Write twin
        twin_writer.write_twin(
            db=db_session,
            repository_id=repo.id,
            snapshot_id=snapshot_id,
            inventory=inventory,
            result=run_result,
        )

        # 1. Verify StructuralArtifact survived intact without 255-char cutoff
        saved_art = db_session.query(StructuralArtifact).filter_by(snapshot_id=snapshot_id, id=art.id).first()
        assert saved_art is not None
        assert saved_art.name == long_name
        assert saved_art.qualified_name == long_qual, (
            f"Qualified name was truncated! Expected length {len(long_qual)}, got {len(saved_art.qualified_name)}"
        )
        assert saved_art.location == long_src_loc, (
            f"Location was truncated! Expected length {len(long_src_loc)}, got {len(saved_art.location)}"
        )
        # Verify file_path property extraction works cleanly on long location
        assert saved_art.file_path == long_file_path

        # 2. Verify External Target Dependency node created by writer preserved full long qualified name
        saved_target = db_session.query(StructuralArtifact).filter_by(
            snapshot_id=snapshot_id,
            qualified_name=long_target_qual,
        ).first()
        assert saved_target is not None, "Target external dependency node must be resolved by long qualified name!"
        assert saved_target.qualified_name == long_target_qual

        # 3. Verify ArtifactRelationship preserved long source_location (> 255 chars)
        saved_rel = db_session.query(ArtifactRelationship).filter_by(snapshot_id=snapshot_id, id=rel.id).first()
        assert saved_rel is not None
        assert saved_rel.source_location == long_src_loc, (
            f"Relationship source_location truncated! Expected {len(long_src_loc)}, got {len(saved_rel.source_location)}"
        )


