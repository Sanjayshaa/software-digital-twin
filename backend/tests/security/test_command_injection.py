"""
Phase 8.6.1 — Security Domain L: Command Injection & Subprocess Safety Tests.

Verifies:
1. Subprocess invocations in Git Acquisition use explicit argv lists (shell=False).
2. Metacharacters in branch names, tags, or URLs cannot break out into shell execution.
"""

import pytest
import subprocess
from unittest.mock import patch, MagicMock
from app.services.acquisition.git_provider import acquire_github_repository


def test_command_injection_argv_list_no_shell():
    """
    Proves that acquire_github_repository executes git via explicit list arguments
    with shell=False, preventing command injection via branch or url arguments.
    """
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        # Attempt command injection payload in branch name
        malicious_branch = "main; touch /tmp/pwned; #"
        acquire_github_repository(
            github_url="https://github.com/safe-org/safe-repo.git",
            branch=malicious_branch,
        )

        assert mock_run.called, "subprocess.run was not invoked"
        called_args, called_kwargs = mock_run.call_args

        # Verify shell=False
        assert called_kwargs.get("shell") is False, "CRITICAL: shell must be False!"

        # Verify command is a list
        cmd_list = called_args[0]
        assert isinstance(cmd_list, list), "Command must be passed as an argv list"
        assert cmd_list[0] == "git"
        assert "clone" in cmd_list

        # Verify the malicious branch is passed as a discrete argv element, not executed
        branch_idx = cmd_list.index("--branch")
        assert cmd_list[branch_idx + 1] == malicious_branch
