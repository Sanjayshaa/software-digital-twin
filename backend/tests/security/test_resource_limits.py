"""
Phase 8.6.3 — Security Domain N: Resource Exhaustion & Boundary Limits Tests.

Verifies:
1. Step 12 & 13: Resource limits on file size, nesting depth, and execution bounds.
2. Large files exceeding MAX_SINGLE_FILE_SIZE (50 MB) are skipped to protect memory.
3. Excessive directory nesting beyond MAX_SCAN_DEPTH is pruned.
4. Clone timeout bounds are configured.
"""

from pathlib import Path
import pytest
from app.services.discovery.scanner import (
    RepositoryScanner,
    MAX_SCAN_DEPTH,
    MAX_SINGLE_FILE_SIZE,
)
from app.services.acquisition.git_provider import _CLONE_TIMEOUT_SECONDS


def test_deeply_nested_directory_pruning(tmp_path):
    """
    Step 13 — Depth Limit Verification:
    Creates a directory tree with 35 nested levels.
    Verifies that RepositoryScanner prunes directory traversal beyond MAX_SCAN_DEPTH (30)
    to prevent stack overflow or directory traversal bombs.
    """
    current_dir = tmp_path / "deep_repo"
    current_dir.mkdir()

    # Create 35 nested directories
    for i in range(35):
        current_dir = current_dir / f"level_{i}"
        current_dir.mkdir()
        (current_dir / f"file_{i}.py").write_text(f"x = {i}\n")

    scanner = RepositoryScanner()
    inventory = scanner.scan(str(tmp_path / "deep_repo"))

    # Verify traversal was bounded and did not exceed depth limit
    assert inventory.total_files <= MAX_SCAN_DEPTH + 1


def test_oversized_file_protection(tmp_path, monkeypatch):
    """
    Step 13 — Oversized File Boundary:
    Simulates a file whose size exceeds the MAX_SINGLE_FILE_SIZE ceiling.
    Verifies that the scanner skips or marks it without reading into memory.
    """
    repo_dir = tmp_path / "oversized_repo"
    repo_dir.mkdir()

    small_file = repo_dir / "normal.py"
    small_file.write_text("print('normal file')")

    huge_file = repo_dir / "huge_blob.iso"
    huge_file.write_text("dummy")

    # Mock os.stat to report huge_file as 100 MB without needing to allocate 100MB on disk
    import os
    real_stat = os.stat

    def mock_stat(path, *args, **kwargs):
        st = real_stat(path, *args, **kwargs)
        if "huge_blob.iso" in str(path):
            return os.stat_result((
                st.st_mode, st.st_ino, st.st_dev, st.st_nlink,
                st.st_uid, st.st_gid, 100 * 1024 * 1024,
                st.st_atime, st.st_mtime, st.st_ctime
            ))
        return st

    monkeypatch.setattr(os, "stat", mock_stat)

    scanner = RepositoryScanner()
    inventory = scanner.scan(str(repo_dir))

    scanned_names = {f.file_name for f in inventory.files}
    assert "normal.py" in scanned_names
    assert "huge_blob.iso" not in scanned_names, "Oversized 100MB file should be skipped!"


def test_clone_timeout_configuration():
    """Step 12 — Verifies clone timeout is bounded."""
    assert _CLONE_TIMEOUT_SECONDS > 0
    assert _CLONE_TIMEOUT_SECONDS <= 600, "Clone timeout must be reasonably bounded (<= 10 mins)"


def test_cumulative_repository_bytes_limit(tmp_path, monkeypatch):
    """
    Step 13 — Cumulative Repository Bytes Boundary:
    Verifies that when cumulative repository bytes exceed MAX_TOTAL_REPO_BYTES (500 MB),
    the scanner truncates and flags `is_truncated = True`.
    """
    import os
    repo_dir = tmp_path / "large_repo"
    repo_dir.mkdir()

    # Create 5 files
    for i in range(5):
        (repo_dir / f"file_{i}.txt").write_text("sample")

    real_stat = os.stat

    # Mock stat to report each file as 150 MB (total 750 MB > 500 MB limit)
    def mock_stat(path, *args, **kwargs):
        st = real_stat(path, *args, **kwargs)
        if "file_" in str(path):
            return os.stat_result((
                st.st_mode, st.st_ino, st.st_dev, st.st_nlink,
                st.st_uid, st.st_gid, 40 * 1024 * 1024,  # Under 50MB single file limit
                st.st_atime, st.st_mtime, st.st_ctime
            ))
        return st

    monkeypatch.setattr(os, "stat", mock_stat)

    from app.services.discovery.scanner import MAX_TOTAL_REPO_BYTES
    # Temporarily lower the threshold for quick testing
    monkeypatch.setattr("app.services.discovery.scanner.MAX_TOTAL_REPO_BYTES", 100 * 1024 * 1024)

    scanner = RepositoryScanner()
    inventory = scanner.scan(str(repo_dir))

    assert inventory.is_truncated is True
    assert inventory.truncation_reason == "MAX_TOTAL_REPO_BYTES_EXCEEDED"
    assert inventory.total_bytes <= 150 * 1024 * 1024


def test_pathological_path_length_skipping(tmp_path):
    """Verifies that files with path length exceeding MAX_PATH_LENGTH are skipped."""
    from app.services.discovery.scanner import MAX_PATH_LENGTH
    repo_dir = tmp_path / "long_path_repo"
    repo_dir.mkdir()

    normal_file = repo_dir / "normal.txt"
    normal_file.write_text("normal")

    scanner = RepositoryScanner()
    # Mock MAX_PATH_LENGTH to small value for deterministic testing
    import app.services.discovery.scanner as sc
    orig = sc.MAX_PATH_LENGTH
    try:
        sc.MAX_PATH_LENGTH = len(str(repo_dir)) + 15  # too short for long filename
        long_file = repo_dir / "a_very_long_file_name_that_exceeds_threshold.txt"
        long_file.write_text("too long")

        inventory = scanner.scan(str(repo_dir))
        scanned_names = {f.file_name for f in inventory.files}
        assert "normal.txt" in scanned_names
        assert "a_very_long_file_name_that_exceeds_threshold.txt" not in scanned_names
    finally:
        sc.MAX_PATH_LENGTH = orig


def test_scenario_mutation_count_limit():
    """Verifies that scenario creation rejects mutation lists exceeding 100 entries."""
    from pydantic import ValidationError
    from app.services.simulation.models import CreateScenarioRequest

    excessive_mutations = [{"mutation_id": f"m_{i}", "mutation_type": "MODIFY_SYMBOL", "target": f"t_{i}"} for i in range(101)]

    with pytest.raises(ValidationError):
        CreateScenarioRequest(
            name="Explosive Scenario",
            base_snapshot_id="snap_123",
            proposed_changes=excessive_mutations,
        )

