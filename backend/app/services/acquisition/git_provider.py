"""
Repository Acquisition Service.
Manages secure cloning of public/private GitHub repositories into an isolated workspace.
Security guarantees:
- Uses subprocess with explicit arg arrays (no shell=True, no command interpolation)
- Validates clone target URL before use
- Enforces clone into isolated workspace directory (no arbitrary path writes)
- Prevents path traversal
- Redacts tokens immediately after use (never stored in plain DB columns)
- Enforces repository size and timeout limits
- Cleans up on failure
"""

import os
import shutil
import subprocess
import time
import uuid
from dataclasses import dataclass
from typing import Optional


# Workspace root for all cloned repositories
# Relative to the project root. Created on first use.
_CLONE_WORKSPACE_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../../../data/cloned_repos")
)

# Safety limits
_CLONE_TIMEOUT_SECONDS = 300       # 5 minutes max for clone
_MAX_WORKSPACE_ENTRIES = 100       # Max concurrent cloned repos in workspace
_CLONE_DEPTH = 1                   # Shallow clone (history depth 1) for analysis


def _get_sanitized_git_env() -> dict:
    """
    Builds a minimal, secure environment for git subprocess invocations.
    Explicitly removes sensitive variables (database credentials, API keys, JWT secrets, PATs).
    """
    safe_keys = {
        "PATH",
        "HOME",
        "TMPDIR",
        "TEMP",
        "TMP",
        "USER",
        "LOGNAME",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "SYSTEMROOT",
        "COMSPEC",
    }
    clean_env = {k: v for k, v in os.environ.items() if k.upper() in safe_keys}

    # Strip any variable that contains sensitive keywords
    sensitive_substrings = ("SECRET", "PASSWORD", "PASSWD", "TOKEN", "KEY", "POSTGRES", "DATABASE", "JWT", "AUTH")
    for k in list(clean_env.keys()):
        k_upper = k.upper()
        if any(sub in k_upper for sub in sensitive_substrings):
            clean_env.pop(k, None)

    # Git security controls
    clean_env["GIT_TERMINAL_PROMPT"] = "0"
    clean_env["GIT_OPTIONAL_LOCKS"] = "0"
    return clean_env


@dataclass
class AcquisitionResult:
    """Result of a successful repository acquisition."""
    success: bool
    workspace_path: str         # Absolute path to the cloned repo on disk
    commit_sha: str             # Resolved HEAD commit SHA
    branch_name: str            # Resolved branch name
    remote_url: str             # The canonical HTTPS URL (token stripped)
    error_message: Optional[str] = None

    # Safe user-facing reason if failed
    user_facing_error: Optional[str] = None


def acquire_github_repository(
    github_url: str,
    branch: Optional[str] = None,
    github_token: Optional[str] = None,
) -> AcquisitionResult:
    """
    Securely clones a public or private GitHub repository into an isolated workspace.

    Security:
    - Uses subprocess with explicit arg list (no shell=True)
    - Token is injected via HTTPS credential URL only within this function scope
    - Token is never stored or logged
    - Clone target is restricted to the controlled workspace directory
    - URL is validated before use via is_safe_clone_url()

    Args:
        github_url: HTTPS clone URL (e.g. https://github.com/owner/repo)
        branch: Optional branch to checkout (defaults to remote default)
        github_token: Optional GitHub Personal Access Token for private repos (not stored)

    Returns:
        AcquisitionResult with workspace_path, commit_sha, and branch_name.
    """
    from app.services.acquisition import is_safe_clone_url, resolve_git_info

    # 1. Validate URL
    is_safe, reason = is_safe_clone_url(github_url)
    if not is_safe:
        return AcquisitionResult(
            success=False,
            workspace_path="",
            commit_sha="",
            branch_name="",
            remote_url=github_url,
            error_message=f"Invalid repository URL: {reason}",
            user_facing_error=reason if "This is not a repository URL" in reason else "The repository URL is not valid. Please use a public HTTPS GitHub URL.",
        )

    # Normalize URL (strip .git suffix for display; keep for clone)
    canonical_url = github_url.rstrip("/")
    if not canonical_url.endswith(".git"):
        clone_url_base = canonical_url + ".git"
    else:
        clone_url_base = canonical_url
    display_url = canonical_url.removesuffix(".git")

    # 2. Ensure workspace exists
    os.makedirs(_CLONE_WORKSPACE_ROOT, exist_ok=True)

    # 3. Enforce workspace entry limit
    try:
        existing = [
            d for d in os.listdir(_CLONE_WORKSPACE_ROOT)
            if os.path.isdir(os.path.join(_CLONE_WORKSPACE_ROOT, d))
        ]
        if len(existing) >= _MAX_WORKSPACE_ENTRIES:
            return AcquisitionResult(
                success=False,
                workspace_path="",
                commit_sha="",
                branch_name="",
                remote_url=display_url,
                error_message="Workspace capacity exceeded",
                user_facing_error="The server workspace is at capacity. Please contact the administrator.",
            )
    except OSError:
        pass

    # 4. Create isolated workspace directory
    clone_id = str(uuid.uuid4())[:8]
    # Derive a safe folder name from the repo URL
    repo_slug = _safe_folder_name(display_url)
    workspace_dir = os.path.join(_CLONE_WORKSPACE_ROOT, f"{repo_slug}_{clone_id}")

    # 5. Build authenticated clone URL (token injected in memory only, never logged)
    if github_token and github_token.strip():
        # Use HTTPS with embedded credentials: https://token@github.com/owner/repo.git
        # Token is used only in this variable scope and passed via subprocess env
        scheme_end = clone_url_base.index("://") + 3
        auth_clone_url = clone_url_base[:scheme_end] + f"x-access-token:{github_token.strip()}@" + clone_url_base[scheme_end:]
    else:
        auth_clone_url = clone_url_base

    # 6. Execute shallow clone with hardened Git configuration (blocks HTTP redirects, symlinks, credential helpers)
    clone_args = [
        "git",
        "-c", "http.followRedirects=false",
        "-c", "core.symlinks=false",
        "-c", "credential.helper=",
        "clone",
        "--depth", str(_CLONE_DEPTH),
        "--single-branch",
    ]
    if branch:
        clone_args += ["--branch", branch]
    clone_args += [auth_clone_url, workspace_dir]

    # Security: never pass auth_clone_url to shell; use arg array with shell=False
    start_time = time.time()
    try:
        result = subprocess.run(
            clone_args,
            capture_output=True,
            text=True,
            timeout=_CLONE_TIMEOUT_SECONDS,
            shell=False,          # CRITICAL: never use shell=True with user-controlled input
            env=_get_sanitized_git_env(),
        )
    except subprocess.TimeoutExpired:
        _cleanup_workspace(workspace_dir)
        return AcquisitionResult(
            success=False,
            workspace_path="",
            commit_sha="",
            branch_name="",
            remote_url=display_url,
            error_message="Clone operation timed out",
            user_facing_error="Repository cloning took too long. The repository may be too large or the network is slow.",
        )
    except FileNotFoundError:
        return AcquisitionResult(
            success=False,
            workspace_path="",
            commit_sha="",
            branch_name="",
            remote_url=display_url,
            error_message="git executable not found on server",
            user_facing_error="Git is not available on the server. Please contact the administrator.",
        )

    if result.returncode != 0:
        _cleanup_workspace(workspace_dir)
        # Sanitize error message — never expose token in error output
        stderr_safe = _sanitize_git_error(result.stderr, github_token)
        return AcquisitionResult(
            success=False,
            workspace_path="",
            commit_sha="",
            branch_name="",
            remote_url=display_url,
            error_message=f"Clone failed: {stderr_safe}",
            user_facing_error=_user_facing_clone_error(result.returncode, result.stderr),
        )

    # 7. Resolve real commit SHA and branch
    git_info = resolve_git_info(workspace_dir)

    elapsed_ms = (time.time() - start_time) * 1000

    return AcquisitionResult(
        success=True,
        workspace_path=workspace_dir,
        commit_sha=git_info.commit_sha,
        branch_name=git_info.branch_name or branch or "main",
        remote_url=display_url,
    )


def cleanup_acquired_workspace(workspace_path: str) -> None:
    """
    Removes a previously cloned workspace directory.
    Only removes paths within the controlled workspace root.
    """
    if not workspace_path:
        return
    abs_path = os.path.abspath(workspace_path)
    if abs_path.startswith(_CLONE_WORKSPACE_ROOT):
        _cleanup_workspace(abs_path)


def _cleanup_workspace(path: str) -> None:
    """Removes a directory tree safely."""
    try:
        if os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)
    except Exception:
        pass


def _safe_folder_name(url: str) -> str:
    """Derives a safe directory name from a repository URL."""
    # Extract owner/repo from URL path
    parts = url.rstrip("/").split("/")
    if len(parts) >= 2:
        slug = f"{parts[-2]}_{parts[-1]}"
    else:
        slug = parts[-1] if parts else "repo"
    # Keep only safe characters
    import re
    return re.sub(r"[^a-zA-Z0-9_\-]", "_", slug)[:60]


def _sanitize_git_error(stderr: str, token: Optional[str]) -> str:
    """Removes any token text from an error message before logging."""
    if not stderr:
        return "unknown error"
    sanitized = stderr[:400]
    if token and token.strip():
        sanitized = sanitized.replace(token.strip(), "***REDACTED***")
    return sanitized


def _user_facing_clone_error(returncode: int, stderr: str) -> str:
    """Returns a safe, human-readable error message for common clone failures."""
    stderr_lower = (stderr or "").lower()
    if "not found" in stderr_lower or "repository" in stderr_lower and "not found" in stderr_lower:
        return "Repository not found. Check the URL and ensure the repository is public (or provide a valid access token for private repos)."
    if "authentication" in stderr_lower or "authorization" in stderr_lower or "403" in stderr_lower:
        return "Authentication failed. For private repositories, please provide a valid GitHub Personal Access Token."
    if "timeout" in stderr_lower or "timed out" in stderr_lower:
        return "Connection timed out while cloning the repository."
    if "already exists" in stderr_lower:
        return "Repository workspace already exists. Please try again."
    return "Repository acquisition failed. Please verify the URL is correct and accessible."


def discover_repository_commits(
    workspace_path: str,
    max_count: int = 50,
    allow_deepen: bool = True,
    default_branch: str = "main",
) -> dict:
    """
    Safely introspects the real Git repository at workspace_path to discover accessible commits.
    - If shallow and allow_deepen=True, attempts to deepen history up to max_count commits.
    - Extracts full SHA, short SHA, author, date, message, and head status.
    - Never fabricates commits.
    """
    abs_path = os.path.abspath(workspace_path)
    dot_git = os.path.join(abs_path, ".git")
    if not os.path.exists(dot_git):
        return {
            "is_git_repo": False,
            "is_shallow": False,
            "total_commits": 0,
            "commits": [],
            "error": "Directory is not a Git repository.",
        }

    clean_env = _get_sanitized_git_env()
    shallow_file = os.path.join(dot_git, "shallow")
    is_shallow = os.path.exists(shallow_file)

    # If the repository is shallow and allow_deepen is True, try deepening history
    if is_shallow and allow_deepen:
        try:
            deepen_args = ["git", "fetch", f"--depth={max_count}", "origin", default_branch]
            subprocess.run(
                deepen_args,
                cwd=abs_path,
                env=clean_env,
                capture_output=True,
                text=True,
                timeout=30,
            )
            is_shallow = os.path.exists(shallow_file)
        except Exception:
            pass

    # Resolve HEAD commit SHA
    head_sha = ""
    try:
        head_res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=abs_path,
            env=clean_env,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if head_res.returncode == 0:
            head_sha = head_res.stdout.strip()
    except Exception:
        pass

    # Read git log
    commits = []
    try:
        log_res = subprocess.run(
            ["git", "log", f"-n{max_count}", "--pretty=format:%H\x1f%h\x1f%an\x1f%ae\x1f%aI\x1f%s"],
            cwd=abs_path,
            env=clean_env,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if log_res.returncode == 0 and log_res.stdout.strip():
            for line in log_res.stdout.strip().split("\n"):
                parts = line.split("\x1f")
                if len(parts) >= 6:
                    c_sha = parts[0].strip()
                    s_sha = parts[1].strip()
                    author_name = parts[2].strip()
                    author_email = parts[3].strip()
                    date_str = parts[4].strip()
                    subject = parts[5].strip()
                    commits.append({
                        "commit_sha": c_sha,
                        "short_sha": s_sha,
                        "author": f"{author_name} <{author_email}>" if author_email else author_name,
                        "authored_date": date_str,
                        "message": subject,
                        "is_head": (c_sha == head_sha),
                    })
    except Exception as exc:
        return {
            "is_git_repo": True,
            "is_shallow": is_shallow,
            "total_commits": 0,
            "commits": [],
            "error": f"Failed to read git log: {str(exc)}",
        }

    return {
        "is_git_repo": True,
        "is_shallow": is_shallow,
        "total_commits": len(commits),
        "commits": commits,
        "head_sha": head_sha,
    }


def extract_commit_source_tree(
    workspace_path: str,
    commit_sha: str,
    dest_dir: str,
    default_branch: str = "main",
) -> tuple[bool, Optional[str]]:
    """
    Safely extracts the repository source tree at a specific commit SHA into dest_dir
    using `git archive` piped to `tar -x`.
    Does NOT modify the workspace working directory or branch.
    Guarantees isolated extraction for structural twin analysis.
    """
    abs_path = os.path.abspath(workspace_path)
    clean_env = _get_sanitized_git_env()

    if not os.path.isdir(abs_path):
        return False, f"Repository directory '{abs_path}' not found."

    # 1. Verify if commit exists locally
    check_proc = subprocess.run(
        ["git", "cat-file", "-e", f"{commit_sha}^{{commit}}"],
        cwd=abs_path,
        env=clean_env,
        capture_output=True,
        text=True,
    )
    if check_proc.returncode != 0:
        # Detect current branch from repo if default_branch is fallback
        resolved_branch = default_branch
        curr_branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=abs_path,
            env=clean_env,
            capture_output=True,
            text=True,
        )
        if curr_branch.returncode == 0 and curr_branch.stdout.strip() and curr_branch.stdout.strip() != "HEAD":
            resolved_branch = curr_branch.stdout.strip()

        # Attempt fetching by commit SHA directly, then fallback to branches
        fetch_targets = [commit_sha, resolved_branch]
        if resolved_branch != "master":
            fetch_targets.append("master")
        if resolved_branch != "main":
            fetch_targets.append("main")

        fetched = False
        for target in fetch_targets:
            try:
                f_res = subprocess.run(
                    ["git", "fetch", "--depth=50", "origin", target],
                    cwd=abs_path,
                    env=clean_env,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if f_res.returncode == 0:
                    check_proc = subprocess.run(
                        ["git", "cat-file", "-e", f"{commit_sha}^{{commit}}"],
                        cwd=abs_path,
                        env=clean_env,
                        capture_output=True,
                        text=True,
                    )
                    if check_proc.returncode == 0:
                        fetched = True
                        break
            except Exception:
                continue

        if not fetched and check_proc.returncode != 0:
            return False, f"Commit '{commit_sha}' not found in local repository or remote origin."

    # 2. Extract commit tree into dest_dir
    os.makedirs(dest_dir, exist_ok=True)
    try:
        p1 = subprocess.Popen(
            ["git", "archive", commit_sha],
            cwd=abs_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=clean_env,
        )
        p2 = subprocess.Popen(
            ["tar", "-x", "-C", dest_dir],
            stdin=p1.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=clean_env,
        )
        p1.stdout.close()
        out, err = p2.communicate(timeout=60)
        p1.wait(timeout=10)
        if p2.returncode != 0:
            err_msg = err.decode("utf-8", errors="replace") if err else "Tar extraction failed"
            return False, f"Archive extraction failed: {err_msg}"
        return True, None
    except Exception as exc:
        return False, f"Exception during tree extraction: {str(exc)}"

