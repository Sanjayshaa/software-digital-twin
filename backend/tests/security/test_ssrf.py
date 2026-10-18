"""
Phase 8.6.3 — Security Domain J: Server-Side Request Forgery (SSRF) Tests (SEC-02).

Validates the full SSRF Test Matrix (Step 7):
1. Rejection of non-HTTPS schemes (file://, http://, ssh://, ftp://, gopher://).
2. Rejection of direct IP addresses:
   - Loopback (127.0.0.1, 127.x.x.x, ::1)
   - Private IPv4 (10.x.x.x, 172.16-31.x.x, 192.168.x.x)
   - Link-local (169.254.x.x, fe80::)
   - Cloud metadata (169.254.169.254, metadata.google.internal)
3. Rejection of embedded credentials (userinfo) and non-standard ports.
4. DNS Resolution Safety:
   - Hostname resolving to private/loopback IP is rejected.
   - Hostname resolving to legitimate public IP is accepted.
5. Legitimate public GitHub URLs continue to be accepted.
"""

import pytest
from app.services.acquisition import is_safe_clone_url


def test_ssrf_rejects_non_https_schemes():
    dangerous_urls = [
        "file:///etc/passwd",
        "ssh://git@github.com/owner/repo.git",
        "git://github.com/owner/repo.git",
        "http://github.com/owner/repo.git",
        "ftp://internal.corp/repo.git",
        "gopher://127.0.0.1:70/",
        "javascript:alert(1)",
        "data:text/plain;base64,SGVsbG8sIFdvcmxkIQ==",
    ]
    for url in dangerous_urls:
        is_safe, reason = is_safe_clone_url(url, check_dns=False)
        assert not is_safe, f"Expected {url} to be rejected, but passed with reason: {reason}"
        assert "Only HTTPS" in reason or "Invalid" in reason or "character" in reason


def test_ssrf_rejects_private_and_loopback_ips():
    """
    SEC-02 Fix Verification:
    Tests that private, loopback, link-local, and cloud metadata addresses
    are rejected even when framed as HTTPS.
    """
    private_ip_urls = [
        "https://127.0.0.1/owner/repo",
        "https://127.0.1.1/owner/repo",
        "https://10.0.0.1/owner/repo",
        "https://10.254.254.254/owner/repo",
        "https://172.16.0.1/owner/repo",
        "https://172.31.255.255/owner/repo",
        "https://192.168.1.1/owner/repo",
        "https://192.168.100.50/owner/repo",
        "https://169.254.169.254/latest/meta-data",
        "https://169.254.1.1/owner/repo",
        "https://0.0.0.0/owner/repo",
    ]
    for url in private_ip_urls:
        is_safe, reason = is_safe_clone_url(url, check_dns=False)
        assert not is_safe, f"Expected private IP URL {url} to be rejected! Reason: {reason}"
        assert "forbidden" in reason.lower() or "internal" in reason.lower() or "private" in reason.lower()


def test_ssrf_rejects_internal_cloud_hostnames():
    internal_hostnames = [
        "https://localhost/owner/repo",
        "https://subdomain.localhost/owner/repo",
        "https://metadata.google.internal/computeMetadata/v1",
        "https://instance-data/latest/meta-data",
        "https://server.internal/repo",
        "https://router.local/repo",
    ]
    for url in internal_hostnames:
        is_safe, reason = is_safe_clone_url(url, check_dns=False)
        assert not is_safe, f"Expected internal hostname {url} to be rejected! Reason: {reason}"
        assert "forbidden" in reason.lower()


def test_ssrf_rejects_credentials_and_custom_ports():
    bad_urls = [
        "https://admin:secret@github.com/owner/repo",
        "https://user:password123@github.com/owner/repo",
        "https://github.com:8080/owner/repo",
        "https://github.com:22/owner/repo",
        "https://github.com:5432/owner/repo",
    ]
    for url in bad_urls:
        is_safe, reason = is_safe_clone_url(url, check_dns=False)
        assert not is_safe, f"Expected {url} to be rejected! Reason: {reason}"
        assert "credentials" in reason.lower() or "port" in reason.lower()


def test_ssrf_dns_resolution_private_ip_rejection():
    """
    Step 6 — SSRF DNS Safety Verification:
    Tests that a hostname which resolves via DNS to a private IP (e.g. 127.0.0.1)
    is caught and rejected before any network request occurs.
    """
    # Mock DNS resolver returning a loopback address
    def mock_dns_resolver_private(hostname, port, proto=0):
        return [(2, 1, 6, "", ("127.0.0.1", 443))]

    is_safe, reason = is_safe_clone_url(
        "https://evil-rebind-domain.example.com/owner/repo",
        check_dns=True,
        dns_resolver=mock_dns_resolver_private,
    )
    assert not is_safe, "CRITICAL: DNS rebinding to 127.0.0.1 was not caught!"
    assert "resolves to private/internal ip" in reason.lower()

    # Mock DNS resolver returning a private 10.x IP
    def mock_dns_resolver_corp_internal(hostname, port, proto=0):
        return [(2, 1, 6, "", ("10.0.1.5", 443))]

    is_safe_corp, reason_corp = is_safe_clone_url(
        "https://corp-internal.example.com/owner/repo",
        check_dns=True,
        dns_resolver=mock_dns_resolver_corp_internal,
    )
    assert not is_safe_corp
    assert "resolves to private/internal ip" in reason_corp.lower()


def test_ssrf_dns_resolution_public_ip_acceptance():
    """Tests that a hostname resolving to a public IP address is safely accepted."""
    def mock_dns_resolver_public(hostname, port, proto=0):
        return [(2, 1, 6, "", ("140.82.113.3", 443))]

    is_safe, reason = is_safe_clone_url(
        "https://github.com/owner/repo",
        check_dns=True,
        dns_resolver=mock_dns_resolver_public,
    )
    assert is_safe, f"Expected public IP resolution to be accepted, got: {reason}"


def test_ssrf_rejects_shell_metacharacters():
    metachar_urls = [
        "https://github.com/owner/repo.git;rm -rf /",
        "https://github.com/owner/repo.git|cat /etc/passwd",
        "https://github.com/owner/`whoami`/repo.git",
        "https://github.com/owner/$(id)/repo.git",
        "https://github.com/owner/repo.git&calc.exe",
    ]
    for url in metachar_urls:
        is_safe, reason = is_safe_clone_url(url, check_dns=False)
        assert not is_safe, f"Expected metacharacter URL {url} to be rejected"
        assert "forbidden character" in reason.lower()


def test_ssrf_accepts_valid_github_urls():
    valid_urls = [
        "https://github.com/Sanjayshaa/LAB-RECORD-SYSTEM",
        "https://github.com/facebook/react.git",
        "https://github.com/torvalds/linux",
        "https://gitlab.com/group/project.git",
    ]
    # For unit test isolation without network dependency, test with check_dns=False
    for url in valid_urls:
        is_safe, reason = is_safe_clone_url(url, check_dns=False)
        assert is_safe, f"Expected {url} to be accepted, failed with reason: {reason}"


def test_ssrf_dns_multi_address_with_one_private():
    """
    Step 5 B & C: When DNS returns multiple IP addresses and one of them is private,
    the URL must be rejected immediately.
    """
    def mock_dns_mixed(hostname, port, proto=0):
        return [
            (2, 1, 6, "", ("140.82.113.3", 443)),  # Public GitHub IP
            (2, 1, 6, "", ("192.168.1.100", 443)),  # Private LAN IP
        ]

    is_safe, reason = is_safe_clone_url(
        "https://mixed-ip-domain.example.com/owner/repo",
        check_dns=True,
        dns_resolver=mock_dns_mixed,
    )
    assert not is_safe, "CRITICAL: Multi-homed DNS with private IP must be rejected!"
    assert "resolves to private/internal ip" in reason.lower()


def test_ssrf_dns_ipv6_private_and_loopback():
    """
    Step 5: Verifies that IPv6 loopback (::1), link-local (fe80::), and private IPv6 (fc00::)
    resolved addresses are rejected.
    """
    for bad_ip in ["::1", "fe80::1", "fc00::1", "fd00::1", "::ffff:127.0.0.1"]:
        def mock_dns_ipv6(hostname, port, proto=0, ip=bad_ip):
            return [(10, 1, 6, "", (ip, 443, 0, 0))]

        is_safe, reason = is_safe_clone_url(
            "https://ipv6-bad.example.com/owner/repo",
            check_dns=True,
            dns_resolver=mock_dns_ipv6,
        )
        assert not is_safe, f"Expected IPv6 {bad_ip} to be rejected!"


def test_git_clone_redirect_prevention_configuration():
    """
    Step 5 D-K: Verifies that the git acquisition pipeline explicitly passes
    `-c http.followRedirects=false` to git clone to defeat any attempt by the server
    to redirect to private hosts, cloud metadata, or alternative ports.
    """
    from unittest.mock import patch
    from app.services.acquisition.git_provider import acquire_github_repository

    with patch("subprocess.run") as mock_run, \
         patch("app.services.acquisition.is_safe_clone_url", return_value=(True, "")):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = ""
        mock_run.return_value.stderr = ""

        with patch("app.services.acquisition.resolve_git_info") as mock_git_info:
            from app.services.acquisition import GitRepoInfo
            mock_git_info.return_value = GitRepoInfo(
                is_git_repo=True,
                commit_sha="abcdef1234567890",
                branch_name="main",
                remote_url="https://github.com/owner/repo",
                vcs_type="git",
            )
            res = acquire_github_repository("https://github.com/owner/repo")
            assert res.success, f"Acquisition failed: {res.error_message}"

        # Inspect subprocess arguments
        called_args = mock_run.call_args[0][0]
        assert "http.followRedirects=false" in " ".join(called_args), (
            "CRITICAL: http.followRedirects=false missing from git clone invocation!"
        )
        assert "core.symlinks=false" in " ".join(called_args)
        assert "credential.helper=" in " ".join(called_args)

