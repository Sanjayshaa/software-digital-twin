#!/usr/bin/env python3
"""
TwinCore Smart CI Test-Targeter CLI.
Predicts impacted regression tests from Git diffs / Pull Requests and selectively executes them.

Usage:
    twincore test --staged
    twincore test --base origin/main --head HEAD --exec
    twincore ci-report --base origin/main --head HEAD
"""

import sys
import os
import argparse
import subprocess
import json
import urllib.request
import urllib.error

DEFAULT_TWINCORE_URL = os.environ.get("TWINCORE_URL", "http://localhost:8000")
DEFAULT_API_KEY = os.environ.get("TWINCORE_API_KEY", "")


def get_git_commit(ref: str) -> str:
    """Resolve git ref to full commit hash."""
    try:
        res = subprocess.check_output(["git", "rev-parse", ref], stderr=subprocess.DEVNULL)
        return res.decode().strip()
    except Exception:
        return ref


def get_repo_remote_info() -> str:
    """Attempts to discover current repo identifier from git origin."""
    try:
        url = subprocess.check_output(["git", "config", "--get", "remote.origin.url"], stderr=subprocess.DEVNULL).decode().strip()
        # Clean git@github.com:User/Repo.git or https://github.com/User/Repo
        clean = url.replace("git@github.com:", "").replace("https://github.com/", "").replace(".git", "")
        return clean.strip()
    except Exception:
        return os.path.basename(os.getcwd())


def call_test_impact_api(server_url: str, repo_id: str, base_ref: str, head_ref: str, api_key: str = "") -> dict:
    url = f"{server_url.rstrip('/')}/repositories/{repo_id}/test-impact"
    payload = {
        "target_snapshot_id": head_ref,
        "base_snapshot_id": base_ref,
        "max_depth": 6,
        "include_indirect": True,
        "include_unaffected": True
    }
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode()
        sys.stderr.write(f"❌ TwinCore API Error ({e.code}): {err_msg}\n")
        sys.exit(1)
    except Exception as e:
        sys.stderr.write(f"❌ Could not connect to TwinCore at {server_url}: {e}\n")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="TwinCore Smart CI Test-Targeter")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Test command
    test_parser = subparsers.add_parser("test", help="Compute and run impacted tests")
    test_parser.add_argument("--repo", default=None, help="Repository ID in TwinCore (defaults to git remote name)")
    test_parser.add_argument("--base", default="HEAD~1", help="Base commit / branch (default: HEAD~1)")
    test_parser.add_argument("--head", default="HEAD", help="Target commit / branch (default: HEAD)")
    test_parser.add_argument("--staged", action="store_true", help="Inspect local staged changes against HEAD")
    test_parser.add_argument("--server", default=DEFAULT_TWINCORE_URL, help=f"TwinCore Server URL (default: {DEFAULT_TWINCORE_URL})")
    test_parser.add_argument("--api-key", default=DEFAULT_API_KEY, help="TwinCore API JWT Token")
    test_parser.add_argument("--exec", action="store_true", help="Execute the selected tests using local test runner")
    test_parser.add_argument("--runner", choices=["pytest", "jest", "gotest"], default="pytest", help="Test runner binary (default: pytest)")

    # CI Report command
    ci_parser = subparsers.add_parser("ci-report", help="Generate GitHub Actions sticky markdown summary")
    ci_parser.add_argument("--repo", default=None)
    ci_parser.add_argument("--base", default="origin/main")
    ci_parser.add_argument("--head", default="HEAD")
    ci_parser.add_argument("--server", default=DEFAULT_TWINCORE_URL)
    ci_parser.add_argument("--api-key", default=DEFAULT_API_KEY)
    ci_parser.add_argument("--output", default=None, help="Write markdown to file (optional)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    repo_id = args.repo or get_repo_remote_info()
    base_sha = get_git_commit(args.base)
    head_sha = get_git_commit(args.head)

    print(f"\n🔍 TwinCore Test Intelligence Targeter")
    print(f"   Repository: {repo_id}")
    print(f"   Analyzing:  {base_sha[:8]} → {head_sha[:8]}")

    data = call_test_impact_api(args.server, repo_id, base_sha, head_sha, getattr(args, "api_key", ""))
    affected = data.get("affected_tests", [])
    roi = data.get("roi_metrics", {})
    cmds = data.get("ci_commands", {})

    print(f"\n⚡️ Results:")
    print(f"   Impacted Tests: {len(affected)} / {roi.get('total_tests', len(affected))} total tests")
    print(f"   Skip Rate:      {roi.get('skip_percentage', 0)}% ({roi.get('skipped_tests', 0)} tests skipped)")
    print(f"   Speedup Factor: {roi.get('speedup_factor', '1.0x')} faster")

    if args.command == "ci-report":
        pr_md = data.get("pr_markdown", "")
        if args.output:
            with open(args.output, "w") as f:
                f.write(pr_md)
            print(f"\n✅ PR Markdown Report written to {args.output}")
        else:
            print("\n--- GITHUB ACTIONS PR COMMENT ---")
            print(pr_md)
        return

    # test command
    run_cmd = cmds.get(args.runner, "pytest")
    print(f"\n🚀 Recommended Test Command:")
    print(f"   $ {run_cmd}\n")

    if args.exec:
        if not affected:
            print("✅ All tests safe! Zero tests impacted by changes. Skipping test execution.")
            sys.exit(0)

        print(f"▶️ Executing targeted test command via {args.runner}...")
        res = subprocess.call(run_cmd, shell=True)
        sys.exit(res)


if __name__ == "__main__":
    main()
