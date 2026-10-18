"""
Regression test suite for P1 Ingestion Integrity: Deterministic File Content Hashing.

Verifies:
1. 16 mandatory file types / cases:
   - LICENSE
   - README.md
   - CODE_OF_CONDUCT.md
   - .gitignore
   - JSON
   - YAML
   - TOML
   - Dockerfile
   - SQL
   - unsupported language
   - unknown extension
   - empty file
   - Unicode file
   - Python
   - JavaScript/TypeScript
   - binary/unparseable file
2. Every successfully discovered and persisted file has:
   - sha256_hash IS NOT NULL
   - len(sha256_hash) == 64
   - sha256_hash == hashlib.sha256(file_bytes).hexdigest().lower()
   - file_hash == sha256_hash
3. Invariants:
   - analyzer failure != hash failure
   - language detection failure != hash failure
   - test detection failure != hash failure
"""

import os
import hashlib
import uuid
import pytest
from app.core.filesystem import compute_file_sha256, compute_bytes_sha256
from app.services.discovery.scanner import RepositoryScanner
from app.services.analysis.persistence.twin_writer import twin_writer
from app.services.analysis.runtime.result import AnalysisRunResult
from app.models.entities import Project, Repository, File as FileModel


def test_canonical_hashing_functions(tmp_path):
    """Verifies canonical file and byte hashing utilities."""
    empty_file = tmp_path / "empty.txt"
    empty_file.write_bytes(b"")
    empty_hash = compute_file_sha256(str(empty_file))
    assert len(empty_hash) == 64
    assert empty_hash == hashlib.sha256(b"").hexdigest().lower()
    assert empty_hash == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    content = "Hello, Digital Twin 2026! 🚀 \u2705 \U0001F600".encode("utf-8")
    unicode_file = tmp_path / "unicode.txt"
    unicode_file.write_bytes(content)
    unicode_hash = compute_file_sha256(str(unicode_file))
    assert len(unicode_hash) == 64
    assert unicode_hash == hashlib.sha256(content).hexdigest().lower()
    assert compute_bytes_sha256(content) == unicode_hash


def test_16_file_types_discovery_and_persistence(tmp_path, db_session):
    """
    Creates a repository fixture with all 16 specified file categories,
    runs RepositoryScanner, persists via twin_writer, and asserts
    strict deterministic SHA-256 integrity on every single database record.
    """
    repo_dir = tmp_path / "test_repo_all_types"
    repo_dir.mkdir()

    # Define all 16 file test cases
    test_files = {
        "LICENSE": b"Apache License 2.0\nCopyright 2026 Digital Twin\n",
        "README.md": b"# Digital Twin\nLiving software model and change impact engine.\n",
        "CODE_OF_CONDUCT.md": b"# Contributor Covenant Code of Conduct\nOur pledge to a welcoming community.\n",
        ".gitignore": b"__pycache__/\n*.pyc\n.venv/\n",
        "config.json": b'{\n  "app": "digital-twin",\n  "version": "1.0.0"\n}\n',
        "deploy.yaml": b"apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: twin-core\n",
        "pyproject.toml": b'[project]\nname = "twin"\nversion = "0.1.0"\n',
        "Dockerfile": b"FROM python:3.12-slim\nWORKDIR /app\nCOPY . .\n",
        "schema.sql": b"CREATE TABLE users (id VARCHAR(36) PRIMARY KEY, name VARCHAR(255));\n",
        "unsupported.xyz": b"UNSUPPORTED_LANGUAGE_SYNTAX_DATA_12345\n",
        "unknown_no_ext": b"BINARY_OR_CUSTOM_FORMAT_WITHOUT_EXTENSION\n",
        "empty_file.txt": b"",
        "unicode_spec.md": "Special characters: ä, ö, ü, ß, 日本語, 🌟, 🛡️\n".encode("utf-8"),
        "service.py": b"def calculate_impact():\n    return 42\n",
        "frontend.ts": b"export interface TwinModel {\n  id: string;\n  name: string;\n}\n",
        "binary_blob.bin": bytes([0x00, 0xFF, 0xFE, 0x01, 0x00, 0x89, 0x50, 0x4E, 0x47]),
    }

    # Write files to directory
    for filename, data in test_files.items():
        filepath = repo_dir / filename
        filepath.write_bytes(data)

    # 1. Scan Inventory
    scanner = RepositoryScanner()
    inventory = scanner.scan(str(repo_dir))
    assert inventory.total_files == len(test_files)

    for sf in inventory.files:
        expected_bytes = test_files[sf.file_name]
        expected_sha = hashlib.sha256(expected_bytes).hexdigest().lower()
        assert sf.sha256_hash == expected_sha
        assert len(sf.sha256_hash) == 64

    # 2. Persist to Database
    unique_suffix = uuid.uuid4().hex[:8]
    proj = Project(name=f"Proj-HashTest-{unique_suffix}", description="Test")
    db_session.add(proj)
    db_session.commit()
    db_session.refresh(proj)

    repo = Repository(
        project_id=proj.id,
        name=f"Repo-HashTest-{unique_suffix}",
        local_path=str(repo_dir),
        default_branch="main",
    )
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)

    snapshot_id = f"snap_test_{unique_suffix}"
    dummy_result = AnalysisRunResult(
        run_id=f"run_test_{unique_suffix}",
        repository_id=repo.id,
        snapshot_id=snapshot_id,
    )

    twin_writer.write_twin(
        db=db_session,
        repository_id=repo.id,
        snapshot_id=snapshot_id,
        inventory=inventory,
        result=dummy_result,
        commit_hash="4b825dc642cb6eb9a060e54bf8d69288fbee4904",
        branch_name="main",
    )
    db_session.commit()

    # 3. Query all persisted files and assert database invariants
    persisted_files = (
        db_session.query(FileModel)
        .filter_by(repository_id=repo.id, snapshot_id=snapshot_id)
        .all()
    )
    assert len(persisted_files) == len(test_files)

    for pf in persisted_files:
        assert pf.sha256_hash is not None, f"File {pf.path} has NULL sha256_hash in database!"
        assert len(pf.sha256_hash) == 64, f"File {pf.path} sha256_hash length is not 64: {pf.sha256_hash}"
        assert pf.file_hash == pf.sha256_hash, f"File {pf.path} file_hash does not match sha256_hash"
        
        expected_bytes = test_files[pf.file_name]
        expected_sha = hashlib.sha256(expected_bytes).hexdigest().lower()
        assert pf.sha256_hash == expected_sha, f"File {pf.path} hash mismatch: {pf.sha256_hash} vs {expected_sha}"


def test_invariants_independent_of_language_and_analyzer_failure(tmp_path, db_session):
    """
    Verifies:
    1. language == None does NOT prevent sha256_hash computation.
    2. Analyzer failure / empty artifacts does NOT prevent sha256_hash computation.
    3. is_test == False does NOT prevent sha256_hash computation.
    """
    repo_dir = tmp_path / "test_repo_invariants"
    repo_dir.mkdir()

    f1 = repo_dir / "UNRECOGNIZED_EXT.custom"
    f1_bytes = b"Random binary or config content here"
    f1.write_bytes(f1_bytes)

    f2 = repo_dir / "empty.unknown"
    f2.write_bytes(b"")

    scanner = RepositoryScanner()
    inventory = scanner.scan(str(repo_dir))
    assert inventory.total_files == 2

    for sf in inventory.files:
        assert len(sf.sha256_hash) == 64

    unique_suffix = uuid.uuid4().hex[:8]
    proj = Project(name=f"Proj-InvTest-{unique_suffix}")
    db_session.add(proj)
    db_session.commit()

    repo = Repository(
        project_id=proj.id,
        name=f"Repo-InvTest-{unique_suffix}",
        local_path=str(repo_dir),
    )
    db_session.add(repo)
    db_session.commit()

    snapshot_id = f"snap_inv_{unique_suffix}"
    # Empty analysis result simulating analyzer failure
    failed_analysis_result = AnalysisRunResult(
        run_id=f"run_inv_{unique_suffix}",
        repository_id=repo.id,
        snapshot_id=snapshot_id,
        analyzer_names=["failing_analyzer"],
    )

    twin_writer.write_twin(
        db=db_session,
        repository_id=repo.id,
        snapshot_id=snapshot_id,
        inventory=inventory,
        result=failed_analysis_result,
    )
    db_session.commit()

    rows = db_session.query(FileModel).filter_by(repository_id=repo.id, snapshot_id=snapshot_id).all()
    assert len(rows) == 2
    for r in rows:
        assert r.sha256_hash is not None
        assert len(r.sha256_hash) == 64
        assert r.language is None or r.language == ""  # Unrecognized language
