"""
Phase 8.6.3 — Security Domain K & U: Path Traversal & Filesystem Containment Tests (SEC-01).

Validates:
1. Rejection of system directory paths (/etc, /var, /usr, /System, /) in onboarding.
2. Rejection of directory traversal sequences (../, ../../).
3. Symlink escape containment in RepositoryScanner (symlinks pointing outside repo root are skipped).
4. Acceptance of valid paths strictly within approved workspace roots.
"""

import os
import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from app.core.filesystem import validate_safe_local_path
from app.services.discovery.scanner import RepositoryScanner
from main import app

client = TestClient(app)


def test_onboard_system_directory_rejection():
    """
    SEC-01 Fix Verification:
    Tests that onboarding sensitive system directories (/etc, /var, /usr, /System)
    is strictly rejected with HTTP 400.
    """
    for system_dir in ["/etc", "/var", "/usr", "/bin", "/sbin", "/System", "/private/etc"]:
        if os.path.exists(system_dir) and os.path.isdir(system_dir):
            resp = client.post("/repositories/onboard", json={
                "local_path": system_dir,
                "name": "test-system-dir-attack",
            })
            assert resp.status_code == 400, f"Expected 400 for system dir '{system_dir}', got {resp.status_code}"
            assert "outside" in resp.json()["detail"].lower() or "system" in resp.json()["detail"].lower()


def test_onboard_path_traversal_sequences():
    """
    Tests that relative path traversal sequences escaping workspace boundaries
    are deterministically rejected with HTTP 400.
    """
    traversal_paths = [
        "../../../../../../../../etc",
        "../../../../../../../../var",
        "../../../../../../../../nonexistent_traversal_dir",
        "./../../../../etc",
    ]
    for bad_path in traversal_paths:
        resp = client.post("/repositories/onboard", json={
            "local_path": bad_path,
            "name": "test-traversal-sequence",
        })
        assert resp.status_code == 400
        detail = resp.json()["detail"].lower()
        assert "does not exist" in detail or "outside" in detail or "system" in detail


def test_scanner_symlink_escape_containment(tmp_path):
    """
    Symlink Escape Verification:
    Creates an authorized repository containing:
    1. A legitimate file (app.py)
    2. A symlink (escape_link -> /etc/hosts or external dir)
    3. A symlinked external directory

    Verifies that RepositoryScanner strictly confines itself to the repository root
    and DOES NOT crawl, index, or parse files outside the repository.
    """
    repo_dir = tmp_path / "safe_repo"
    repo_dir.mkdir()

    # Legitimate file
    safe_file = repo_dir / "calculator.py"
    safe_file.write_text("def add(a, b): return a + b\n")

    # Outside target
    outside_dir = tmp_path / "outside_secret_zone"
    outside_dir.mkdir()
    secret_file = outside_dir / "secret.env"
    secret_file.write_text("SUPER_SECRET_KEY=confidential_data_12345\n")

    # Symlink file pointing outside
    symlink_file = repo_dir / "escape_symlink.py"
    try:
        os.symlink(str(secret_file), str(symlink_file))
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks not supported on this filesystem")

    # Symlink directory pointing outside
    symlink_dir = repo_dir / "escape_dir"
    try:
        os.symlink(str(outside_dir), str(symlink_dir), target_is_directory=True)
    except (OSError, NotImplementedError):
        pass

    # Run scanner on safe_repo
    scanner = RepositoryScanner()
    inventory = scanner.scan(str(repo_dir))

    scanned_filenames = [f.file_name for f in inventory.files]
    assert "calculator.py" in scanned_filenames, "Legitimate file was not scanned!"
    assert "escape_symlink.py" not in scanned_filenames, "CRITICAL: External symlink file was indexed!"
    assert "secret.env" not in scanned_filenames, "CRITICAL: File from external directory symlink was indexed!"


def test_validate_safe_local_path_allowed_vs_unauthorized(tmp_path):
    """Unit tests for validate_safe_local_path function."""
    allowed_root = tmp_path / "allowed_workspace"
    allowed_root.mkdir()
    child_repo = allowed_root / "my_project"
    child_repo.mkdir()

    forbidden_dir = tmp_path / "forbidden_workspace"
    forbidden_dir.mkdir()

    # Child of allowed root succeeds
    canonical = validate_safe_local_path(str(child_repo), allowed_roots=[allowed_root])
    assert canonical == str(child_repo.resolve())

    # Path outside allowed root fails with 400
    with pytest.raises(Exception) as exc_info:
        validate_safe_local_path(str(forbidden_dir), allowed_roots=[allowed_root])
    assert "400" in str(exc_info.value)
    assert "outside" in str(exc_info.value).lower()
