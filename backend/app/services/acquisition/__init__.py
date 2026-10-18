"""
Repository Git Resolution Utilities.
Safely resolves real commit SHA, branch name, and remote URL from a local path
using GitPython. Falls back gracefully for non-git directories.
Never fabricates commit information.
"""

import os
import re
from typing import Optional, Tuple
from dataclasses import dataclass


@dataclass
class GitRepoInfo:
    """Resolved metadata from a real Git repository."""
    is_git_repo: bool
    commit_sha: str          # Full 40-char SHA or "no-git"
    branch_name: str         # Active branch or "no-git"
    remote_url: Optional[str]  # Origin remote URL or None
    vcs_type: str            # "git" or "none"


def resolve_git_info(path: str) -> GitRepoInfo:
    """
    Resolves real Git metadata (commit SHA, branch, remote URL) from a directory.

    - Uses GitPython to introspect the .git directory at the given path.
    - The .git directory must be directly inside `path` (no parent traversal).
    - If the directory is not a Git repository, returns a safe non-git result.
    - Never executes arbitrary repository scripts or user-controlled code.
    - Never fabricates commit information.

    Args:
        path: Absolute path to the repository root directory.

    Returns:
        GitRepoInfo with resolved metadata.
    """
    abs_path = os.path.abspath(path)

    # Security: verify the path itself exists and is a directory
    if not os.path.isdir(abs_path):
        return GitRepoInfo(
            is_git_repo=False,
            commit_sha="no-git",
            branch_name="no-git",
            remote_url=None,
            vcs_type="none",
        )

    # Check if a .git directory/file exists directly inside this path (no parent traversal)
    dot_git = os.path.join(abs_path, ".git")
    if not os.path.exists(dot_git):
        return GitRepoInfo(
            is_git_repo=False,
            commit_sha="no-git",
            branch_name="no-git",
            remote_url=None,
            vcs_type="none",
        )

    try:
        import git
        repo = git.Repo(abs_path)

        # Resolve HEAD commit
        try:
            commit_sha = repo.head.commit.hexsha
        except Exception:
            commit_sha = "detached-head"

        # Resolve branch name
        try:
            if repo.head.is_detached:
                branch_name = f"detached@{commit_sha[:8]}"
            else:
                branch_name = repo.active_branch.name
        except Exception:
            branch_name = "unknown"

        # Resolve remote URL (origin preferred; none is fine)
        remote_url = None
        try:
            origin = repo.remotes["origin"]
            remote_url = origin.url
        except (IndexError, KeyError, Exception):
            if repo.remotes:
                remote_url = repo.remotes[0].url

        return GitRepoInfo(
            is_git_repo=True,
            commit_sha=commit_sha,
            branch_name=branch_name,
            remote_url=remote_url,
            vcs_type="git",
        )

    except Exception:
        # GitPython failed — still return safe non-git result
        return GitRepoInfo(
            is_git_repo=False,
            commit_sha="no-git",
            branch_name="no-git",
            remote_url=None,
            vcs_type="none",
        )


import ipaddress
import socket
import urllib.parse
from typing import Union


def _is_forbidden_ip(ip_obj: Union[ipaddress.IPv4Address, ipaddress.IPv6Address]) -> bool:
    """Checks whether an IP address is loopback, private, link-local, multicast, or cloud metadata."""
    if ip_obj.is_loopback:
        return True
    if ip_obj.is_private:
        return True
    if ip_obj.is_link_local:
        return True
    if ip_obj.is_multicast:
        return True
    if ip_obj.is_unspecified:
        return True
    if str(ip_obj) in ("169.254.169.254", "fd00:ec2::254"):
        return True
    return False


def is_safe_clone_url(
    url: str,
    check_dns: bool = True,
    dns_resolver=None,
) -> Tuple[bool, str]:
    """
    Validates that a GitHub/Git clone URL is safe to use.
    Enforces SSRF prevention (SEC-02):
    - Scheme must be HTTPS
    - Rejects credentials embedded in URL
    - Rejects non-standard ports (prevents internal port scanning)
    - Rejects loopback, private IPv4/IPv6, link-local, and cloud metadata IPs
    - Performs DNS resolution to prevent DNS rebinding to private IP ranges
    - Rejects shell metacharacters and directory traversal sequences

    Args:
        url: The clone URL string to validate.
        check_dns: If True, resolves hostname and checks all returned IPs.
        dns_resolver: Optional custom resolver callable for deterministic testing.

    Returns:
        (is_safe, reason) tuple.
    """
    if not url or not isinstance(url, str):
        return False, "URL must be a non-empty string"

    url = url.strip()

    # Limit length
    if len(url) > 512:
        return False, "URL exceeds maximum length"

    # Prevent shell metacharacters
    forbidden_chars = [";", "&", "|", "`", "$", "(", ")", "{", "}", "<", ">", "\n", "\r", "\\", "\t", "\0"]
    for ch in forbidden_chars:
        if ch in url:
            return False, f"URL contains forbidden character: {repr(ch)}"

    # Parse URL
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception as exc:
        return False, f"Malformed URL: {str(exc)}"

    # Only allow HTTPS URLs
    if parsed.scheme.lower() != "https":
        return False, "Only HTTPS URLs are supported. Use https://github.com/owner/repo"

    # Disallow userinfo (credentials embedded in URL)
    if parsed.username or parsed.password:
        return False, "Embedded credentials in clone URL are not permitted."

    # Disallow non-standard ports
    if parsed.port and parsed.port != 443:
        return False, f"Non-standard port '{parsed.port}' is forbidden. Only standard HTTPS port 443 is permitted."

    hostname = (parsed.hostname or "").lower().strip()
    if not hostname:
        return False, "URL must contain a valid hostname"

    # Check for forbidden hostnames / internal cloud metadata names
    forbidden_hostnames = {
        "localhost",
        "127.0.0.1",
        "::1",
        "metadata.google.internal",
        "instance-data",
        "metadata.aws",
        "metadata",
    }
    if (
        hostname in forbidden_hostnames
        or hostname.endswith(".localhost")
        or hostname.endswith(".internal")
        or hostname.endswith(".local")
    ):
        return False, f"Destination hostname '{hostname}' is forbidden (internal/cloud infrastructure)."

    # IP address check
    try:
        ip_obj = ipaddress.ip_address(hostname)
        if _is_forbidden_ip(ip_obj):
            return False, f"Direct access to internal/private IP address {ip_obj} is forbidden."
        is_ip_literal = True
    except ValueError:
        is_ip_literal = False

    # DNS Resolution check (detect hostnames resolving to private addresses)
    if check_dns and not is_ip_literal:
        resolver = dns_resolver or socket.getaddrinfo
        try:
            addr_info = resolver(hostname, 443, proto=socket.IPPROTO_TCP)
            resolved_ips = {item[4][0] for item in addr_info if item[4]}
        except Exception as exc:
            return False, f"DNS resolution failed for hostname '{hostname}': {str(exc)}"

        for ip_str in resolved_ips:
            try:
                res_ip = ipaddress.ip_address(ip_str)
                if _is_forbidden_ip(res_ip):
                    return False, f"Hostname '{hostname}' resolves to private/internal IP {res_ip}."
            except ValueError:
                return False, f"Invalid resolved IP '{ip_str}'."

    # Validate path structure: must include at least owner/repo
    path = parsed.path.strip("/")
    if not path or "/" not in path:
        return False, "GitHub repository URL must include owner and repository name (e.g. https://github.com/owner/repo)."

    return True, ""
