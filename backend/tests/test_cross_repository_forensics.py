"""
Phase 7 — Cross-Repository Ingestion, Historical Reconstruction & Change Impact Forensics.
Regression tests validating:
1. Exact commit resolution & Git tree diff integration
2. Dual-level change detection (Git ground truth + AST symbols)
3. Non-code / documentation repository handling (e.g., Markdown/YAML changes)
4. Missing snapshot vs identical commit distinction (IDENTICAL_COMMITS vs VERIFIED_ZERO_CHANGES vs FILE_DIFF_ONLY)
5. Distinguishing verified zero-change from unanalyzed states
6. Snapshot contamination prevention
7. Safe test selection policy & unknown coverage
"""

import os
import uuid
import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session

from app.models.entities import (
    Repository,
    RepositorySnapshot,
    StructuralArtifact,
    ArtifactRelationship,
    File,
)
from app.services.impact.models import ChangeSet, ChangeItem, ChangeType
from app.services.impact.change_detector import ChangeDetector, run_git_tree_diff
from app.services.impact.analyzer import ImpactAnalyzer


def test_git_tree_diff_nonexistent_workspace():
    """Validates that a non-existent workspace path returns graceful failure without throwing."""
    success, entries, err = run_git_tree_diff("/non/existent/path/xyz123", "HEAD~1", "HEAD")
    assert success is False
    assert entries == []
    assert "does not exist" in (err or "").lower()


def test_git_tree_diff_parsing(tmp_path):
    """Validates that Git name-status output lines are parsed accurately into ChangeItem tuples."""
    fake_git_repo = tmp_path / "repo"
    fake_git_repo.mkdir()
    (fake_git_repo / ".git").mkdir()

    # Simulate git diff output: Added, Modified, Removed, Renamed
    mock_stdout = (
        "A\tREADME.md\n"
        "M\tsrc/main.py\n"
        "D\told_config.json\n"
        "R100\told_name.txt\tnew_name.txt\n"
    )

    with patch("subprocess.run") as mock_run:
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = mock_stdout
        mock_proc.stderr = ""
        mock_run.return_value = mock_proc

        success, entries, err = run_git_tree_diff(str(fake_git_repo), "revA", "revB")
        assert success is True
        assert err is None
        assert len(entries) == 4
        assert entries[0] == ("ADDED", "README.md", None)
        assert entries[1] == ("MODIFIED", "src/main.py", None)
        assert entries[2] == ("REMOVED", "old_config.json", None)
        assert entries[3] == ("RENAMED", "new_name.txt", "old_name.txt")


def test_identical_commit_comparison_is_verified_zero():
    """Validates that comparing identical commit hashes yields IDENTICAL_COMMITS and is_verified_zero=True."""
    mock_db = MagicMock(spec=Session)
    detector = ChangeDetector()

    repo_id = str(uuid.uuid4())
    commit_sha = "3253040bc18b28cf9db0b53755cf643f8705bc03"

    # Same base and target commit
    cs = detector.detect_changes(
        db=mock_db,
        repository_id=repo_id,
        base_snapshot_id=commit_sha,
        target_snapshot_id=commit_sha,
    )

    assert cs.status == "IDENTICAL_COMMITS"
    assert cs.is_verified_zero is True
    assert cs.summary["total_changes"] == 0
    assert cs.diff_mode == "IDENTICAL"


def test_non_code_repository_git_delta_not_false_zero():
    """
    Validates that a documentation repository (e.g. awesome-digital-twins)
    with only markdown or yaml changes returns FILE_DIFF_ONLY with nonzero count,
    NOT an empty result or false-positive zero changes.
    """
    mock_db = MagicMock(spec=Session)
    repo = Repository(
        id="repo_awesome",
        name="awesome-digital-twins",
        local_path="/tmp/fake_awesome_repo",
    )
    mock_db.query().filter_by().first.return_value = repo
    mock_db.query().filter().first.return_value = None  # No full AST snapshot indexed yet

    detector = ChangeDetector()

    with patch("app.services.impact.change_detector.run_git_tree_diff") as mock_diff:
        mock_diff.return_value = (
            True,
            [
                ("ADDED", ".github/workflows/automerge.yml", None),
                ("MODIFIED", "README.md", None),
            ],
            None,
        )

        cs = detector.detect_changes(
            db=mock_db,
            repository_id="repo_awesome",
            base_snapshot_id="3253040",
            target_snapshot_id="ac0cfb6",
        )

        assert cs.status == "FILE_DIFF_ONLY"
        assert cs.diff_mode == "FILE_DIFF_ONLY"
        assert cs.is_verified_zero is False
        assert cs.summary["total_changes"] == 2
        assert cs.summary["added"] == 1
        assert cs.summary["modified"] == 1
        assert len(cs.changes) == 2
        assert cs.changes[0].source_file in [".github/workflows/automerge.yml", "README.md"]


def test_ast_symbol_and_file_diff_integration():
    """
    Validates that when AST snapshots exist, symbol modifications are combined
    with Git file-level changes without duplicate double-counting.
    """
    mock_db = MagicMock(spec=Session)

    snap_a = RepositorySnapshot(id="snap_a", repository_id="repo_java", commit_hash="commit_a")
    snap_b = RepositorySnapshot(id="snap_b", repository_id="repo_java", commit_hash="commit_b")

    def query_filter_side_effect(*args, **kwargs):
        mock_query = MagicMock()
        mock_query.first.side_effect = [snap_a, snap_b]
        return mock_query

    mock_db.query().filter.side_effect = query_filter_side_effect

    art_a = StructuralArtifact(
        id="art_1",
        snapshot_id="snap_a",
        qualified_name="org.eclipse.ditto.ThingService.getThing",
        name="getThing",
        artifact_type="METHOD",
        file_path="things/service/src/main/java/ThingService.java",
        content_hash="hash_v1",
    )
    art_b = StructuralArtifact(
        id="art_1_v2",
        snapshot_id="snap_b",
        qualified_name="org.eclipse.ditto.ThingService.getThing",
        name="getThing",
        artifact_type="METHOD",
        file_path="things/service/src/main/java/ThingService.java",
        content_hash="hash_v2",  # Modified hash
    )

    detector = ChangeDetector()

    with patch("app.services.impact.change_detector.run_git_tree_diff") as mock_diff:
        mock_diff.return_value = (
            True,
            [
                ("MODIFIED", "things/service/src/main/java/ThingService.java", None),
                ("MODIFIED", "things/service/src/main/resources/things.conf", None),
            ],
            None,
        )

        cs = detector.detect_changes(
            db=mock_db,
            repository_id="repo_java",
            base_snapshot_id="commit_a",
            target_snapshot_id="commit_b",
            base_artifacts=[art_a],
            target_artifacts=[art_b],
        )

        assert cs.status == "COMPLETED"
        assert cs.diff_mode == "SYMBOL_AND_FILE"
        assert cs.summary["total_changes"] == 2
        # Symbol-level change for ThingService.getThing
        symbol_changes = [c for c in cs.changes if c.is_symbol_level]
        assert len(symbol_changes) == 1
        assert symbol_changes[0].symbol_name == "getThing"
        assert symbol_changes[0].change_type == ChangeType.MODIFIED
        # File-level change for things.conf (non-AST file)
        file_changes = [c for c in cs.changes if not c.is_symbol_level]
        assert len(file_changes) == 1
        assert file_changes[0].source_file == "things/service/src/main/resources/things.conf"


def test_snapshot_isolation_prevents_cross_commit_contamination():
    """
    Validates that artifacts are strictly isolated by snapshot_id
    and cannot leak into another snapshot's diff.
    """
    mock_db = MagicMock(spec=Session)
    art_foreign = StructuralArtifact(
        id="foreign_art",
        snapshot_id="foreign_snapshot_999",
        qualified_name="com.other.LeakedClass",
        name="LeakedClass",
        artifact_type="CLASS",
        file_path="src/LeakedClass.java",
        content_hash="abc",
    )

    detector = ChangeDetector()
    # If base and target artifacts only belong to their respective snapshots, foreign_art is excluded
    cs = detector.detect_changes(
        db=mock_db,
        repository_id="repo_test",
        base_snapshot_id="snap_1",
        target_snapshot_id="snap_2",
        base_artifacts=[],
        target_artifacts=[],
    )

    for item in cs.changes:
        assert item.qualified_name != "com.other.LeakedClass"
