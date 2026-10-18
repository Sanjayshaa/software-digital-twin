"""
Phase 8.6.3 — Security Domain I, L & M: Repository Ingestion Security & Script Execution Prevention.

Verifies:
1. Core Security Invariant: "A repository is data to analyze, never code to execute."
   - Repositories containing malicious package.json lifecycle scripts, setup.py, Makefiles,
     or shell scripts NEVER cause execution of those scripts during discovery or AST parsing.
2. Hostile File Containment:
   - Malformed files, huge lines, binary files, and invalid UTF-8 do not crash the engine.
3. Safe Temporary Directory Cleanup:
   - Ingestion cleanup cleans up ephemeral directories and leaves no orphaned temporary paths.
"""

import os
import shutil
import tempfile
from pathlib import Path
import pytest
from app.services.discovery.scanner import RepositoryScanner
from app.services.discovery.engine import discovery_engine
from app.services.acquisition.git_provider import _cleanup_workspace, _get_sanitized_git_env


def test_repository_lifecycle_scripts_never_execute(tmp_path):
    """
    Step 10 — Repository Script Execution Invariant:
    Injects canary creation commands into:
    - package.json lifecycle scripts (preinstall, postinstall, prepare)
    - setup.py
    - Makefile
    - arbitrary shell scripts

    Runs the complete Discovery Brain on the repository.
    Proves that NO repository code or script was executed.
    """
    repo_dir = tmp_path / "hostile_repo"
    repo_dir.mkdir()

    canary_file = tmp_path / "EXECUTION_CANARY_DETECTED.txt"
    if canary_file.exists():
        canary_file.unlink()

    # 1. Hostile package.json
    package_json = repo_dir / "package.json"
    package_json.write_text(f"""
{{
  "name": "malicious-package",
  "version": "1.0.0",
  "scripts": {{
    "preinstall": "touch {canary_file}",
    "install": "touch {canary_file}",
    "postinstall": "touch {canary_file}",
    "prepare": "touch {canary_file}",
    "build": "touch {canary_file}"
  }}
}}
""")

    # 2. Hostile setup.py
    setup_py = repo_dir / "setup.py"
    setup_py.write_text(f"""
import os
os.system("touch {canary_file}")
from setuptools import setup
setup(name="hostile-module", version="0.1")
""")

    # 3. Hostile Makefile
    makefile = repo_dir / "Makefile"
    makefile.write_text(f"""
all:
\ttouch {canary_file}
install:
\ttouch {canary_file}
""")

    # 4. Hostile shell script
    sh_file = repo_dir / "build_hook.sh"
    sh_file.write_text(f"#!/bin/sh\ntouch {canary_file}\n")
    try:
        sh_file.chmod(0o777)
    except OSError:
        pass

    # 5. Legitimate source file to parse
    src_file = repo_dir / "index.js"
    src_file.write_text("function calculateTotal(items) { return items.reduce((a, b) => a + b, 0); }\n")

    # Run Discovery Engine
    profile, plan = discovery_engine.discover(str(repo_dir))

    # CRITICAL INVARIANT: The canary file must NOT exist!
    assert not canary_file.exists(), (
        "CRITICAL ARBITRARY CODE EXECUTION VULNERABILITY! "
        "Repository lifecycle or setup script was executed by the Digital Twin!"
    )

    # Verify discovery successfully extracted static metadata without execution
    assert profile.total_files_scanned >= 1
    assert "javascript" in [l.name.lower() for l in profile.languages] or "json" in [f.name.lower() for f in profile.frameworks]


def test_malformed_and_hostile_file_containment(tmp_path):
    """
    Step 14 — Malformed & Hostile Files Containment:
    Tests that:
    - Enormous line lengths (100k+ chars)
    - Raw binary files (.bin, .so)
    - Invalid UTF-8 / non-decodable byte sequences
    - Zero-byte files
    do not crash the scanner or parser.
    """
    repo_dir = tmp_path / "corrupted_repo"
    repo_dir.mkdir()

    # 1. Zero byte file
    (repo_dir / "empty.py").write_text("")

    # 2. Invalid UTF-8 bytes
    (repo_dir / "corrupted.py").write_bytes(b"\xff\xfe\x00\x00\xaa\xbb\xcc\xdd\x80\x81")

    # 3. Enormous single line length (100,000 characters)
    (repo_dir / "long_line.js").write_text("var x = '" + "A" * 100_000 + "';\n")

    # 4. Binary blob
    (repo_dir / "blob.dat").write_bytes(os.urandom(10_000))

    scanner = RepositoryScanner()
    inventory = scanner.scan(str(repo_dir))

    # Scanner should safely capture all files without uncaught exception
    scanned_names = {f.file_name for f in inventory.files}
    assert "empty.py" in scanned_names
    assert "corrupted.py" in scanned_names
    assert "long_line.js" in scanned_names
    assert "blob.dat" in scanned_names


def test_temporary_workspace_cleanup(tmp_path):
    """
    Step 16 — Temporary Workspace Cleanup:
    Verifies that _cleanup_workspace safely removes temporary workspace directories.
    """
    test_workspace = tmp_path / "temp_clone_dir"
    test_workspace.mkdir()
    dummy_file = test_workspace / "cloned_code.py"
    dummy_file.write_text("print('temp clone')")

    assert test_workspace.exists()

    _cleanup_workspace(str(test_workspace))

    assert not test_workspace.exists(), "Temporary clone directory was not cleaned up!"
