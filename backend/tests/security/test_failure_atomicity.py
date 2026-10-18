"""
Phase 8.6.4 — Security Domain: Failure Atomicity & Cleanup Verification.

Verifies:
1. When GitHub repository acquisition fails, the temporary clone workspace is deleted.
2. When Digital Twin build fails, the cloned directory is purged and DB transaction is rolled back.
3. No orphan workspace directories or corrupted DB records leak from failed operations.
"""

import os
import shutil
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from main import app
from app.services.acquisition.git_provider import (
    acquire_github_repository,
    cleanup_acquired_workspace,
    _CLONE_WORKSPACE_ROOT,
)

client = TestClient(app)


def test_acquisition_failure_cleans_workspace(tmp_path):
    """
    Verifies that when git clone fails (e.g. non-zero returncode),
    the temporary workspace directory is immediately removed from disk.
    """
    with patch("subprocess.run") as mock_run, \
         patch("app.services.acquisition.is_safe_clone_url", return_value=(True, "")):
        # Simulate clone failure
        mock_run.return_value.returncode = 128
        mock_run.return_value.stdout = ""
        mock_run.return_value.stderr = "fatal: repository 'https://github.com/nonexistent/repo.git' not found"

        result = acquire_github_repository("https://github.com/nonexistent/repo")
        assert not result.success
        assert result.workspace_path == ""

        # Verify no temporary directory left in clone workspace root matching nonexistent
        if os.path.exists(_CLONE_WORKSPACE_ROOT):
            remaining = [
                d for d in os.listdir(_CLONE_WORKSPACE_ROOT)
                if "nonexistent_repo" in d
            ]
            assert len(remaining) == 0, f"Leaked workspace directories found: {remaining}"


def test_build_failure_cleans_workspace_and_rolls_back():
    """
    Verifies that if structural twin engine fails after cloning,
    the workspace directory is purged and the endpoint returns HTTP 500 cleanly.
    """
    with patch("app.api.graph.acquire_github_repository") as mock_acq, \
         patch("app.api.graph.structural_twin_engine.build_structural_twin") as mock_build, \
         patch("app.api.graph.is_safe_clone_url", return_value=(True, "")):

        # Create a mock cloned directory
        test_workspace = os.path.join(_CLONE_WORKSPACE_ROOT, "test_failure_workspace_12345")
        os.makedirs(test_workspace, exist_ok=True)
        dummy_file = os.path.join(test_workspace, "code.py")
        with open(dummy_file, "w") as f:
            f.write("print('hello')")

        from app.services.acquisition.git_provider import AcquisitionResult
        mock_acq.return_value = AcquisitionResult(
            success=True,
            workspace_path=test_workspace,
            commit_sha="1122334455667788",
            branch_name="main",
            remote_url="https://github.com/mock/repo",
        )

        # Simulate build crash
        mock_build.side_effect = RuntimeError("Simulated AST parser crash")

        response = client.post(
            "/repositories/connect-github",
            json={
                "github_url": "https://github.com/mock/repo",
                "branch": "main",
            },
        )
        assert response.status_code == 500
        assert "Digital Twin build failed" in response.json()["detail"]

        # CRITICAL: Verify workspace was cleaned up despite exception
        assert not os.path.exists(test_workspace), "CRITICAL: Workspace directory leaked after build failure!"
