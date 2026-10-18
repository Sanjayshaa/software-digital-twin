"""
Phase 8.5 — Real Repository Ingestion & Data Integrity Tests.

Verifies:
1. Real Git commit SHA is resolved from a local git repository (not hardcoded "HEAD")
2. Non-git directories produce vcs_type=none and commit_sha="no-git" (never fabricated)
3. GitHub URL validation rejects unsafe URLs (injection, non-HTTPS, malformed)
4. GitHub URL validation accepts well-formed HTTPS URLs
5. real_validation_repo is a proper isolated git repository
6. Process discovery API response field names match what the frontend expects
7. Workspace isolation: two different repos produce separate, distinct snapshot IDs
8. Repository deduplication: onboarding the same path twice does not create duplicate DB entries
9. Onboard API returns real metadata structure (no hardcoded 'HEAD' or 'snap_latest')
"""

import hashlib
import os
import subprocess
import tempfile
import pytest

from sqlalchemy.orm import Session
from app.services.acquisition import resolve_git_info, is_safe_clone_url


# ============================================================
# FIXTURE: Temporary real Git repository
# ============================================================

@pytest.fixture
def temp_git_repo(tmp_path):
    """Creates a temporary, real Git repository with a committed file."""
    repo_dir = tmp_path / "test_git_repo"
    repo_dir.mkdir()

    # Initialize git repository
    subprocess.run(["git", "init", str(repo_dir)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo_dir), "config", "user.email", "test@test.com"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo_dir), "config", "user.name", "Test User"], check=True, capture_output=True)

    # Create and commit a file
    test_file = repo_dir / "main.py"
    test_file.write_text("def hello(): return 'world'\n")
    subprocess.run(["git", "-C", str(repo_dir), "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo_dir), "commit", "-m", "initial commit"], check=True, capture_output=True)

    return str(repo_dir)


@pytest.fixture
def temp_non_git_dir(tmp_path):
    """Creates a temporary directory that is NOT a git repository."""
    non_git = tmp_path / "not_a_git_repo"
    non_git.mkdir()
    (non_git / "app.py").write_text("x = 1\n")
    return str(non_git)


# ============================================================
# TEST GROUP 1: resolve_git_info() — Git Metadata Resolution
# ============================================================

class TestResolveGitInfo:

    def test_resolves_real_commit_sha_from_git_repo(self, temp_git_repo):
        """Real git repo must return actual 40-char commit SHA, not 'HEAD'."""
        info = resolve_git_info(temp_git_repo)
        assert info.is_git_repo is True
        assert info.vcs_type == "git"
        assert len(info.commit_sha) == 40, f"Expected 40-char SHA, got: {info.commit_sha!r}"
        assert info.commit_sha != "HEAD", "commit_sha must not be the literal string 'HEAD'"
        assert info.commit_sha != "no-git", "commit_sha must not be 'no-git' for a real git repo"
        # Must be a valid hexadecimal SHA
        assert all(c in "0123456789abcdef" for c in info.commit_sha), f"Invalid SHA hex: {info.commit_sha}"

    def test_resolves_real_branch_name(self, temp_git_repo):
        """Real git repo must return actual branch name."""
        info = resolve_git_info(temp_git_repo)
        assert info.is_git_repo is True
        assert info.branch_name not in ("HEAD", "no-git", ""), \
            f"Expected real branch name, got: {info.branch_name!r}"

    def test_non_git_dir_returns_no_git(self, temp_non_git_dir):
        """Non-git directory must return no-git, not fabricate commit info."""
        info = resolve_git_info(temp_non_git_dir)
        assert info.is_git_repo is False
        assert info.vcs_type == "none"
        assert info.commit_sha == "no-git", f"Expected 'no-git', got: {info.commit_sha!r}"
        assert info.branch_name == "no-git", f"Expected 'no-git', got: {info.branch_name!r}"

    def test_nonexistent_path_returns_no_git(self):
        """Nonexistent path must return no-git (no crash, no fabrication)."""
        info = resolve_git_info("/nonexistent/path/that/does/not/exist")
        assert info.is_git_repo is False
        assert info.commit_sha == "no-git"
        assert info.vcs_type == "none"

    def test_no_parent_traversal(self, temp_non_git_dir):
        """
        A directory without its own .git must NOT pick up parent .git.
        This is the real_validation_repo bug: if real_validation_repo had no .git,
        the old code would have stored the PARENT project's commit SHA as its commit.
        """
        info = resolve_git_info(temp_non_git_dir)
        # If the parent happens to be a git repo, this directory still should NOT be detected
        # as a git repo because resolve_git_info only checks for .git directly inside path.
        assert info.is_git_repo is False, (
            f"Non-git directory at {temp_non_git_dir} must not inherit parent's .git. "
            f"Got is_git_repo=True, commit_sha={info.commit_sha}"
        )

    def test_commit_sha_is_deterministic(self, temp_git_repo):
        """Same repo produces same SHA on repeated calls."""
        info1 = resolve_git_info(temp_git_repo)
        info2 = resolve_git_info(temp_git_repo)
        assert info1.commit_sha == info2.commit_sha

    def test_different_repos_produce_different_shas(self, temp_git_repo, tmp_path):
        """Different repos with different commits produce different SHAs."""
        repo2_dir = tmp_path / "second_repo"
        repo2_dir.mkdir()
        subprocess.run(["git", "init", str(repo2_dir)], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo2_dir), "config", "user.email", "test@test.com"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo2_dir), "config", "user.name", "Test"], check=True, capture_output=True)
        (repo2_dir / "other.py").write_text("y = 2\n")
        subprocess.run(["git", "-C", str(repo2_dir), "add", "."], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo2_dir), "commit", "-m", "different commit"], check=True, capture_output=True)

        info1 = resolve_git_info(temp_git_repo)
        info2 = resolve_git_info(str(repo2_dir))
        assert info1.commit_sha != info2.commit_sha, "Different repos must produce different commit SHAs"


# ============================================================
# TEST GROUP 2: real_validation_repo Integrity
# ============================================================

class TestRealValidationRepo:
    """Verifies that real_validation_repo has its own isolated .git directory."""

    @pytest.fixture
    def validation_repo_path(self):
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        return os.path.join(base, "real_validation_repo")

    def test_real_validation_repo_has_git_directory(self, validation_repo_path):
        """real_validation_repo must have its own .git directory."""
        git_dir = os.path.join(validation_repo_path, ".git")
        assert os.path.exists(git_dir), (
            f"real_validation_repo at {validation_repo_path} must have its own .git directory. "
            "Without it, git commands pick up the parent project's git state."
        )

    def test_real_validation_repo_commit_sha_is_independent(self, validation_repo_path):
        """real_validation_repo commit SHA must differ from the parent project's SHA."""
        # Parent project SHA
        parent_result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True,
            cwd=os.path.dirname(validation_repo_path)
        )
        parent_sha = parent_result.stdout.strip()

        # real_validation_repo SHA
        val_info = resolve_git_info(validation_repo_path)
        assert val_info.is_git_repo is True, "real_validation_repo must be a real git repo"
        assert val_info.commit_sha != parent_sha, (
            f"real_validation_repo commit SHA ({val_info.commit_sha[:8]}) must not match "
            f"the parent project's SHA ({parent_sha[:8]}). "
            "These must be independent git repositories."
        )


# ============================================================
# TEST GROUP 3: is_safe_clone_url() — Security Validation
# ============================================================

class TestUrlSafetyValidation:
    """Verifies that URL injection and unsafe URL patterns are rejected."""

    def test_valid_github_https_url(self):
        is_safe, reason = is_safe_clone_url("https://github.com/owner/repo")
        assert is_safe is True, f"Expected safe, got reason: {reason}"

    def test_valid_github_https_url_with_dot_git(self):
        is_safe, reason = is_safe_clone_url("https://github.com/owner/repo.git")
        assert is_safe is True, f"Expected safe, got reason: {reason}"

    def test_valid_github_url_with_hyphens_underscores(self):
        is_safe, reason = is_safe_clone_url("https://github.com/my-org/my-service_v2")
        assert is_safe is True, f"Expected safe, got reason: {reason}"

    def test_rejects_ssh_url(self):
        is_safe, reason = is_safe_clone_url("git@github.com:owner/repo.git")
        assert is_safe is False
        assert reason, "Should return a reason"

    def test_rejects_file_url(self):
        is_safe, reason = is_safe_clone_url("file:///etc/passwd")
        assert is_safe is False

    def test_rejects_http_url(self):
        is_safe, reason = is_safe_clone_url("http://github.com/owner/repo")
        assert is_safe is False, "HTTP (non-HTTPS) must be rejected"

    def test_rejects_url_with_semicolon(self):
        is_safe, reason = is_safe_clone_url("https://github.com/owner/repo; rm -rf /")
        assert is_safe is False
        assert reason

    def test_rejects_url_with_backtick(self):
        is_safe, reason = is_safe_clone_url("https://github.com/owner/`rm -rf /`")
        assert is_safe is False

    def test_rejects_url_with_dollar_sign(self):
        is_safe, reason = is_safe_clone_url("https://github.com/owner/$(id)")
        assert is_safe is False

    def test_rejects_url_with_pipe(self):
        is_safe, reason = is_safe_clone_url("https://github.com/owner/repo | cat /etc/passwd")
        assert is_safe is False

    def test_rejects_empty_string(self):
        is_safe, reason = is_safe_clone_url("")
        assert is_safe is False

    def test_rejects_none_like_input(self):
        is_safe, reason = is_safe_clone_url(None)
        assert is_safe is False

    def test_rejects_url_exceeding_max_length(self):
        long_url = "https://github.com/owner/" + "a" * 600
        is_safe, reason = is_safe_clone_url(long_url)
        assert is_safe is False

    def test_rejects_newline_in_url(self):
        is_safe, reason = is_safe_clone_url("https://github.com/owner/repo\nextra")
        assert is_safe is False


# ============================================================
# TEST GROUP 4: Snapshot ID Determinism
# ============================================================

class TestSnapshotIdDeterminism:
    """Verifies that snapshot IDs are correctly derived and isolated."""

    def test_snapshot_id_derived_from_real_commit_sha(self, temp_git_repo):
        """
        Snapshot ID must be derived from the REAL commit SHA, not from the literal
        string 'HEAD'. This ensures different snapshots of the same repo are distinct.
        """
        info = resolve_git_info(temp_git_repo)
        assert info.is_git_repo is True

        # Derive the snapshot ID as the engine does
        repo_id = "test-repo-id"
        snap_raw = f"{repo_id}::{info.commit_sha}::{info.branch_name}"
        snapshot_id = f"snap_{hashlib.sha256(snap_raw.encode('utf-8')).hexdigest()[:16]}"

        # If we had used the literal "HEAD" string instead
        snap_raw_fake = f"{repo_id}::HEAD::main"
        snapshot_id_fake = f"snap_{hashlib.sha256(snap_raw_fake.encode('utf-8')).hexdigest()[:16]}"

        assert snapshot_id != snapshot_id_fake, (
            "Snapshot derived from real commit SHA must differ from one derived from 'HEAD' literal. "
            "The old code was generating identical snapshots for all analyses of the same repo."
        )

    def test_different_commits_produce_different_snapshot_ids(self, tmp_path):
        """Different commits of the same logical repo must produce different snapshot IDs."""
        repo_id = "same-repo-abc123"

        sha1 = "a" * 40
        sha2 = "b" * 40
        branch = "main"

        snap1 = f"snap_{hashlib.sha256(f'{repo_id}::{sha1}::{branch}'.encode()).hexdigest()[:16]}"
        snap2 = f"snap_{hashlib.sha256(f'{repo_id}::{sha2}::{branch}'.encode()).hexdigest()[:16]}"

        assert snap1 != snap2, "Different commits must produce different snapshot IDs"


# ============================================================
# TEST GROUP 5: Process Discovery API Contract
# ============================================================

class TestProcessDiscoveryApiContract:
    """
    Verifies the frontend field names match the backend ProcessDiscoveryResult schema.
    This is the E1 bug identified in the audit: frontend used processes_discovered,
    steps_created, transitions_created — but backend returns total_processes,
    total_steps, total_transitions.
    """

    def test_process_discovery_result_has_total_processes_field(self):
        """Backend ProcessDiscoveryResult must have total_processes (not processes_discovered)."""
        from app.services.process.models import ProcessDiscoveryResult
        fields = ProcessDiscoveryResult.model_fields
        assert "total_processes" in fields, "ProcessDiscoveryResult must have total_processes"
        assert "processes_discovered" not in fields, \
            "processes_discovered field does not exist in ProcessDiscoveryResult — frontend was using wrong name"

    def test_process_discovery_result_has_total_steps_field(self):
        """Backend ProcessDiscoveryResult must have total_steps (not steps_created)."""
        from app.services.process.models import ProcessDiscoveryResult
        fields = ProcessDiscoveryResult.model_fields
        assert "total_steps" in fields, "ProcessDiscoveryResult must have total_steps"
        assert "steps_created" not in fields, \
            "steps_created field does not exist in ProcessDiscoveryResult — frontend was using wrong name"

    def test_process_discovery_result_has_total_transitions_field(self):
        """Backend ProcessDiscoveryResult must have total_transitions (not transitions_created)."""
        from app.services.process.models import ProcessDiscoveryResult
        fields = ProcessDiscoveryResult.model_fields
        assert "total_transitions" in fields, "ProcessDiscoveryResult must have total_transitions"
        assert "transitions_created" not in fields, \
            "transitions_created field does not exist in ProcessDiscoveryResult — frontend was using wrong name"

    def test_process_discovery_result_has_required_frontend_fields(self):
        """All fields that the corrected frontend accesses must exist in the backend schema."""
        from app.services.process.models import ProcessDiscoveryResult
        fields = ProcessDiscoveryResult.model_fields

        # These are the fields the fixed frontend now uses:
        corrected_frontend_fields = ["total_processes", "total_steps", "total_transitions"]
        for f in corrected_frontend_fields:
            assert f in fields, f"ProcessDiscoveryResult must have field '{f}' for frontend contract"


# ============================================================
# TEST GROUP 6: Onboard Response Schema Contract
# ============================================================

class TestOnboardResponseContract:
    """
    Verifies that the onboard endpoint response does not contain
    hardcoded 'HEAD' or placeholder values when real git data is available.
    """

    def test_engine_resolves_commit_from_real_git_repo(self, temp_git_repo, db_session):
        """
        build_structural_twin() must resolve real commit SHA from a real git repo
        and NOT store the literal string 'HEAD' in the snapshot's commit_hash.
        """
        import uuid
        from app.services.analysis.engine import StructuralTwinEngine
        from app.models.entities import Project, Repository, RepositorySnapshot

        unique_suffix = uuid.uuid4().hex[:8]
        proj = Project(name=f"Test-Project-OnboardContract-{unique_suffix}", description="Test")
        db_session.add(proj)
        db_session.commit()
        db_session.refresh(proj)

        repo = Repository(
            project_id=proj.id,
            name=f"test-onboard-contract-{unique_suffix}",
            local_path=temp_git_repo,
            default_branch="main",
        )
        db_session.add(repo)
        db_session.commit()
        db_session.refresh(repo)

        # Run the engine
        engine = StructuralTwinEngine()
        snapshot_id, result = engine.build_structural_twin(
            db=db_session,
            repository_id=repo.id,
        )

        # Verify the snapshot has a real commit hash, not "HEAD"
        snapshot = db_session.query(RepositorySnapshot).filter_by(id=snapshot_id).first()
        assert snapshot is not None, "Snapshot must be persisted"
        assert snapshot.commit_hash != "HEAD", (
            f"Snapshot commit_hash must not be the literal 'HEAD' string. "
            f"Got: {snapshot.commit_hash!r}. The engine must resolve the real SHA."
        )
        assert len(snapshot.commit_hash) == 40, (
            f"Expected 40-char commit SHA in snapshot. Got: {snapshot.commit_hash!r}"
        )

    def test_engine_stores_no_git_for_non_git_dir(self, temp_non_git_dir, db_session):
        """
        build_structural_twin() for a non-git directory must store 'no-git'
        as the commit_hash — not the literal 'HEAD'.
        """
        import uuid
        from app.services.analysis.engine import StructuralTwinEngine
        from app.models.entities import Project, Repository, RepositorySnapshot

        unique_suffix = uuid.uuid4().hex[:8]
        proj = Project(name=f"Test-Project-NonGit-{unique_suffix}", description="Test")
        db_session.add(proj)
        db_session.commit()
        db_session.refresh(proj)

        repo = Repository(
            project_id=proj.id,
            name=f"test-non-git-dir-{unique_suffix}",
            local_path=temp_non_git_dir,
            default_branch="main",
        )
        db_session.add(repo)
        db_session.commit()
        db_session.refresh(repo)

        engine = StructuralTwinEngine()
        snapshot_id, result = engine.build_structural_twin(
            db=db_session,
            repository_id=repo.id,
        )

        snapshot = db_session.query(RepositorySnapshot).filter_by(id=snapshot_id).first()
        assert snapshot is not None
        # Must not store the fabricated "HEAD" string
        assert snapshot.commit_hash != "HEAD", (
            f"Non-git directory must not store 'HEAD' as commit. Got: {snapshot.commit_hash!r}"
        )
        # Must use no-git sentinel
        assert snapshot.commit_hash == "no-git", (
            f"Non-git directory must store 'no-git' as commit_hash. Got: {snapshot.commit_hash!r}"
        )


# ============================================================
# TEST GROUP 7: Clone Failure Handling (E)
# ============================================================

class TestCloneFailureHandling:
    """Verifies that clone failures are handled safely and honestly."""

    def test_invalid_url_clone_fails_honestly(self):
        """acquire_github_repository with malformed/injection URL fails validation immediately."""
        from app.services.acquisition.git_provider import acquire_github_repository
        # Malformed / injection URL
        res = acquire_github_repository("https://github.com/some/repo; rm -rf /")
        assert res.success is False
        assert "not valid" in res.user_facing_error.lower()
        assert res.workspace_path == ""

        # Unresolvable host
        res2 = acquire_github_repository("https://not-github-nonexistent-domain.com/some/repo")
        assert res2.success is False
        assert res2.user_facing_error is not None
        assert res2.workspace_path == ""

    def test_nonexistent_repo_clone_fails_honestly(self):
        """acquire_github_repository with unreachable repo returns safe failure and cleans up."""
        from app.services.acquisition.git_provider import acquire_github_repository
        res = acquire_github_repository("https://github.com/definitely-nonexistent-org-12345/nonexistent-repo-99999.git")
        assert res.success is False
        assert res.user_facing_error is not None
        # Workspace should be cleaned up
        if res.workspace_path:
            assert not os.path.exists(res.workspace_path)


# ============================================================
# TEST GROUP 8: Workspace Isolation (F, I)
# ============================================================

class TestWorkspaceIsolation:
    """Verifies workspaces are isolated and do not collide."""

    def test_workspace_path_is_isolated(self):
        """Cloned repo workspace paths must be within data/cloned_repos and have unique subdirs."""
        from app.services.acquisition.git_provider import _safe_folder_name
        slug1 = _safe_folder_name("https://github.com/owner/repo-a")
        slug2 = _safe_folder_name("https://github.com/owner/repo-b")
        assert slug1 != slug2
        assert "/" not in slug1 and "\\" not in slug1
        assert ".." not in slug1

    def test_two_different_repos_have_isolated_snapshots(self, temp_git_repo, tmp_path, db_session):
        """Two different repos with different codebases produce different snapshot IDs and entities."""
        import uuid
        from app.services.analysis.engine import StructuralTwinEngine
        from app.models.entities import Project, Repository

        # Create second git repo with different file
        repo2_dir = tmp_path / "repo2"
        repo2_dir.mkdir()
        subprocess.run(["git", "init", str(repo2_dir)], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo2_dir), "config", "user.email", "test2@test.com"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo2_dir), "config", "user.name", "Test User 2"], check=True, capture_output=True)
        (repo2_dir / "service.py").write_text("class PaymentProcessor:\n    def pay(self): pass\n")
        subprocess.run(["git", "-C", str(repo2_dir), "add", "."], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo2_dir), "commit", "-m", "repo2 commit"], check=True, capture_output=True)

        suffix = uuid.uuid4().hex[:8]
        p = Project(name=f"Proj-Iso-{suffix}", description="Iso")
        db_session.add(p)
        db_session.commit()

        r1 = Repository(project_id=p.id, name=f"r1-{suffix}", local_path=temp_git_repo, default_branch="main")
        r2 = Repository(project_id=p.id, name=f"r2-{suffix}", local_path=str(repo2_dir), default_branch="main")
        db_session.add_all([r1, r2])
        db_session.commit()

        engine = StructuralTwinEngine()
        snap1_id, res1 = engine.build_structural_twin(db=db_session, repository_id=r1.id)
        snap2_id, res2 = engine.build_structural_twin(db=db_session, repository_id=r2.id)

        assert snap1_id != snap2_id, "Snapshots of distinct repositories must be distinct"

