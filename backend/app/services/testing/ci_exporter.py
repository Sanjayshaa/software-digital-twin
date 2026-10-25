"""
Phase 8.6 — Smart CI Test-Targeter & ROI Exporter.
Computes runnable test command lines (pytest, jest, go test) and GitHub Actions PR Markdown summaries.
"""

from typing import Dict, Any, List
import math


def generate_ci_test_commands(affected_tests: List[Dict[str, Any]]) -> Dict[str, str]:
    """
    Extracts test target files/specs and builds executable commands for major test runners.
    """
    test_files = set()
    pytest_nodes = set()

    for t in affected_tests:
        loc = t.get("location") or ""
        test_name = t.get("test_name") or t.get("name") or ""
        
        # Clean file path if it contains line numbers (e.g., path/to/file.py:45)
        clean_file = loc.split(":")[0] if ":" in loc else loc
        if clean_file:
            test_files.add(clean_file)
            if test_name and not test_name.startswith("test_file"):
                pytest_nodes.add(f"{clean_file}::{test_name}")
            else:
                pytest_nodes.add(clean_file)

    sorted_files = sorted(list(test_files))
    sorted_nodes = sorted(list(pytest_nodes))
    files_str = " ".join(sorted_files) if sorted_files else ""
    nodes_str = " ".join(sorted_nodes) if sorted_nodes else ""

    pytest_cmd = f"pytest {nodes_str}" if nodes_str else "pytest"
    jest_cmd = f"npm test -- {files_str}" if files_str else "npm test"
    gotest_cmd = f"go test -v {files_str}" if files_str else "go test ./..."

    return {
        "pytest": pytest_cmd,
        "jest": jest_cmd,
        "gotest": gotest_cmd,
        "test_files": sorted_files,
        "test_count": len(sorted_files),
    }


def compute_ci_roi_metrics(
    total_catalog_count: int,
    impacted_test_count: int,
    avg_test_duration_sec: float = 3.5,
    ci_runner_cost_per_min: float = 0.008,
) -> Dict[str, Any]:
    """
    Calculates time and cost savings compared to running the full test suite.
    """
    safe_total = max(total_catalog_count, impacted_test_count, 1)
    skipped_count = max(0, safe_total - impacted_test_count)

    full_suite_duration_sec = safe_total * avg_test_duration_sec
    targeted_duration_sec = max(impacted_test_count * avg_test_duration_sec, 2.0)
    time_saved_sec = max(0.0, full_suite_duration_sec - targeted_duration_sec)

    time_saved_pct = round((time_saved_sec / full_suite_duration_sec) * 100, 1) if full_suite_duration_sec > 0 else 0.0

    full_cost = (full_suite_duration_sec / 60.0) * ci_runner_cost_per_min
    targeted_cost = (targeted_duration_sec / 60.0) * ci_runner_cost_per_min
    cost_saved = max(0.0, full_cost - targeted_cost)

    return {
        "total_tests": safe_total,
        "impacted_tests": impacted_test_count,
        "skipped_tests": skipped_count,
        "skip_percentage": round((skipped_count / safe_total) * 100, 1),
        "full_suite_duration_seconds": round(full_suite_duration_sec, 1),
        "targeted_duration_seconds": round(targeted_duration_sec, 1),
        "time_saved_seconds": round(time_saved_sec, 1),
        "time_saved_percentage": time_saved_pct,
        "estimated_cost_saved_usd": round(cost_saved, 4),
        "speedup_factor": f"{round(full_suite_duration_sec / targeted_duration_sec, 1)}x" if targeted_duration_sec > 0 else "1.0x",
    }


def generate_pr_markdown_summary(
    repository_name: str,
    base_ref: str,
    head_ref: str,
    impact_data: Dict[str, Any],
) -> str:
    """
    Synthesizes a GitHub Actions Sticky PR Comment in Markdown.
    """
    summary = impact_data.get("summary", {})
    affected = impact_data.get("affected_tests", [])
    unknown = impact_data.get("unknown_coverage", [])
    roi = impact_data.get("roi_metrics", {})
    commands = impact_data.get("ci_commands", {})

    status_icon = "🟢" if len(unknown) == 0 else "🟡"
    speedup = roi.get("speedup_factor", "1.0x")
    time_saved_pct = roi.get("time_saved_percentage", 0)

    md = [
        f"## {status_icon} TwinCore Smart CI Test Intelligence",
        f"**Repository:** `{repository_name}` | **Comparison:** `{base_ref[:8]}` → `{head_ref[:8]}`",
        "",
        f"> ⚡️ **CI Speedup:** **{speedup} faster** ({time_saved_pct}% CI time saved).",
        f"> Ran **{len(affected)} impacted tests** out of {roi.get('total_tests', len(affected))} total tests.",
        "",
        "### 📊 CI Efficiency & ROI Breakdown",
        "| Metric | Full Test Suite | TwinCore Targeted | Savings |",
        "| :--- | :---: | :---: | :---: |",
        f"| **Tests Executed** | {roi.get('total_tests', 0)} | **{len(affected)}** | **{roi.get('skipped_tests', 0)} skipped ({roi.get('skip_percentage', 0)}%)** |",
        f"| **Est. Duration** | {round(roi.get('full_suite_duration_seconds', 0)/60, 1)}m | **{round(roi.get('targeted_duration_seconds', 0)/60, 1)}m** | **-{round(roi.get('time_saved_seconds', 0)/60, 1)} mins** |",
        f"| **CI Runner Cost** | ${roi.get('full_suite_duration_seconds', 0)*0.008/60:.4f} | **${roi.get('targeted_duration_seconds', 0)*0.008/60:.4f}** | **Save ${roi.get('estimated_cost_saved_usd', 0):.4f} / run** |",
        "",
        "### 🧪 Targeted Execution Command",
        "```bash",
        f"{commands.get('pytest', 'pytest')}",
        "```",
        "",
    ]

    if affected:
        md.append("<details><summary><b>🔍 View Affected Tests & Causal Chains (" + str(len(affected)) + ")</b></summary>\n")
        md.append("| Test Name | Classification | Propagation Depth | Reason |")
        md.append("| :--- | :---: | :---: | :--- |")
        for t in affected[:15]:
            name = t.get("test_name") or t.get("name") or "test"
            cls_name = "DIRECT" if t.get("classification") == "DIRECTLY_AFFECTED" else "INDIRECT"
            depth = t.get("depth", 1)
            reason = t.get("reason", "").replace("\n", " ")
            md.append(f"| `{name}` | **{cls_name}** | {depth} hop(s) | {reason} |")
        if len(affected) > 15:
            md.append(f"| *...and {len(affected) - 15} more tests* | | | |")
        md.append("\n</details>\n")

    if unknown:
        md.append(f"### ⚠️ Unmapped Changes ({len(unknown)})")
        md.append("The following modified code artifacts lack mapped tests in the Digital Twin:")
        for u in unknown[:5]:
            md.append(f"- 🔴 `{u.get('name')}` ({u.get('artifact_type', 'CODE')}) in `{u.get('location', '')}`")
        md.append("")

    md.append("---")
    md.append("*Powered by [TwinCore Living Software Digital Twin](https://github.com/Sanjayshaa/software-digital-twin)*")

    return "\n".join(md)
