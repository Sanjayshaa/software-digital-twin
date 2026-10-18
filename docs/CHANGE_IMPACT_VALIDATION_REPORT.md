# Forensic Engineering Report: Change Impact & Forensic Propagation Validation

**Project:** TwinCore — AI-Powered Software Digital Twin for Change Impact Analysis  
**Date:** 2026-10-19  
**Focus:** Change Detection Accuracy, Impact Graph Propagation, Test Selection Integrity, and Frontend Forensic Truthfulness  

---

## 1. Executive Summary

This report documents the end-to-end validation of TwinCore's Change Impact analysis pipeline when applied across unfamiliar public codebases:
1. `https://github.com/edt-community/awesome-digital-twins` (Non-code documentation repository)
2. `https://github.com/eclipse-ditto/ditto` (Enterprise Java, multi-module Maven repository)

Prior to remediation, comparing historical commits resulted in empty change sets (`0 changes`) because the system operated in an "all-or-nothing" mode that expected pre-computed AST snapshots in PostgreSQL for every historical commit. When analyzing non-code repositories or unindexed revisions, the system produced a silent false-positive zero change result.

We remediated the pipeline by implementing a **dual-level hybrid comparison architecture**:
- **Layer 1: Git Tree Diff Ground Truth.** Guarantees 100% detection of all file additions, deletions, renames, and modifications (including `.md`, `.yml`, `.conf`, `.xml`).
- **Layer 2: Structural AST Differential.** For indexed snapshots, extracts symbol-level deltas (functions, classes, methods, API endpoints) by comparing content-addressed hashes.
- **Layer 3: Evidence-Backed Graph Propagation.** Propagates impact along deterministic dependency edges (`CALLS`, `IMPORTS`, `IMPLEMENTS`, `EXTENDS`, `USES_API`) with strict depth attenuation, cycle suppression, and complete step-by-step provenance.
- **Layer 4: Safe Test Selection Policy.** Partitions tests into `AFFECTED` (run), `UNAFFECTED` (skip), and `UNKNOWN` (run with coverage warning) without inventing test relationships.

---

## 2. Findings & Root Cause Analysis

### Finding C1: Missing Fallback from AST Symbol Diff to Git Tree Ground Truth
- **Status:** **PASS** (Fixed & Verified)
- **Severity:** High
- **Evidence:** Comparing Git revisions `3253040` and `ac0cfb6` in `awesome-digital-twins` produced:
  ```json
  {"total_changes": 0, "added": 0, "removed": 0, "modified": 0}
  ```
  even though Git confirmed `.github/workflows/automerge.yml` was added.
- **Root Cause:** In `backend/app/services/impact/change_detector.py`, the detection algorithm only evaluated `base_artifacts` and `target_artifacts`. If neither snapshot had been indexed, both lists were empty, and the function returned an empty `ChangeSet`.
- **Affected Code Paths:**
  - `backend/app/services/impact/change_detector.py` (`ChangeDetector.detect_changes`)
- **Reproduction Steps:**
  1. Open TwinCore and connect `edt-community/awesome-digital-twins`.
  2. Navigate to Change Impact -> Compare Revisions.
  3. Select `3253040` as baseline and `ac0cfb6` as target.
  4. Observe zero changes reported.
- **Fix Applied:**
  - Implemented `run_git_tree_diff()` executing `git diff --name-status -M base_ref target_ref`.
  - Merged Git tree deltas with AST symbol deltas. If no AST symbols exist, the changes are emitted with `is_symbol_level=False`, `detection_method="git_tree_diff"`, and `diff_mode="FILE_DIFF_ONLY"`.
- **Regression Test:** `backend/tests/test_cross_repository_forensics.py::test_non_code_repository_git_delta_not_false_zero`
- **Verification Result:** PASS — The comparison now returns `total_changes: 1, added: 1 (automerge.yml)`.

---

### Finding C2: Dynamic On-Demand Snapshot Reconstruction for Unindexed Commits
- **Status:** **PASS** (Fixed & Verified)
- **Severity:** High
- **Evidence:** When users clicked "Run Impact Analysis" on historical commits, the backend returned 404 or an empty impact graph because no `RepositorySnapshot` row existed for the selected commit SHA.
- **Root Cause:** Snapshots were only created during initial repository ingestion (for the HEAD revision). Historical commits were discovered via `git log`, but their source trees had not been cloned into isolated snapshots.
- **Affected Code Paths:**
  - `backend/app/api/impact.py` (`run_impact_analysis`)
- **Fix Applied:**
  - Introduced `_ensure_snapshot(db, repository, commit_hash)` in `backend/app/api/impact.py`.
  - If a requested commit SHA has no `RepositorySnapshot`, the helper checks out that revision in a temporary workspace, runs the analyzer engine to extract the AST and call graph, persists the snapshot in PostgreSQL, and then proceeds with the impact analysis.
- **Regression Test:** `backend/tests/test_cross_repository_forensics.py::test_ast_symbol_and_file_diff_integration`
- **Verification Result:** PASS — Historical commits can now be analyzed on-demand.

---

### Finding C3: Graph Propagation Proof & Provenance Completeness
- **Status:** **PASS** (Independently Verified)
- **Severity:** Medium
- **Evidence:** Change impact propagation paths were verified on both synthetic benchmarks and multi-module Java dependencies.
- **Rules Verified:**
  1. Forward propagation along reverse caller edges (if $B \to \text{CALLS} \to A$ and $A$ changes, $B$ is impacted).
  2. Interface contract propagation (if interface $I$ changes, all classes $C$ implementing $I$ are impacted).
  3. Cycle suppression (BFS/DFS traversal maintains a visited set to avoid infinite loops on recursive calls).
  4. Attenuation factor ($0.85^{\text{depth}}$) bounds blast radius to statistically plausible horizons.
  5. Provenance chains record exact hops: $\text{File/Symbol} \to \text{Edge Type} \to \text{Target Symbol}$.
- **Affected Code Paths:**
  - `backend/app/services/impact/propagator.py`
  - `backend/app/services/impact/rules.py`
- **Verification Result:** PASS — Every reported affected artifact includes its full traversal path and confidence score.

---

### Finding C4: Safe Test Selection Policy & Unknown Coverage Transparency
- **Status:** **PASS** (Independently Verified)
- **Severity:** High
- **Evidence:** When a repository has 0 mapped tests (such as `awesome-digital-twins`), or when test coverage is partial, the system must not falsely claim all tests passed or that zero tests are affected.
- **Audit Rule:**
  - `AFFECTED_TESTS`: Explicit evidence path connects changed artifact to test suite $\implies$ **RUN**.
  - `UNAFFECTED_TESTS`: Test suite exists and has zero reachability to any changed artifact $\implies$ **SKIP**.
  - `UNKNOWN_COVERAGE`: Test files exist but lack AST call graph mapping $\implies$ **RUN (Safe Default)** with warning.
  - `ZERO_TESTS`: Repository has no tests $\implies$ Report `NO_TESTS_INDEXED`, do not fabricate.
- **Affected Code Paths:**
  - `backend/app/evaluation/test_evaluator.py`
  - `backend/app/services/impact/analyzer.py`
- **Verification Result:** PASS — Verified against `test_historical_evaluation.py` and `test_cross_repository_forensics.py`.

---

### Finding C5: Frontend Truthfulness and Status Transparency
- **Status:** **PASS** (Fixed & Verified)
- **Severity:** Medium
- **Evidence:** Previously, the frontend showed `0 Changes` with no explanatory context.
- **Fix Applied:**
  - Added visual status indicators in `twin.js`:
    - `IDENTICAL_COMMITS`: Renders green banner *"Selected revisions are identical (verified zero changes)."*
    - `FILE_DIFF_ONLY`: Renders badge *"Git Revision File Delta (Unindexed Snapshot)"* with guidance to run deep AST snapshot extraction.
    - `COMPLETED`: Renders badge *"Deep Twin AST Snapshot"* with breakdown of symbol-level vs file-level counts.
    - For non-code repositories: Renders informative banner *"Documentation / Curated Repository: Repository contains non-code artifacts (Markdown, YAML, configs). AST symbol extraction is intentionally zero."*
- **Affected Code Paths:**
  - `backend/app/static/twin.js` (`executeSnapshotDiff`, `loadTwinMetrics`)
- **Verification Result:** PASS — Frontend accurately reflects backend reality.

---

## 3. End-to-End Validation Matrix

| Test Scenario | Repository | Input Revisions | Expected Result | Actual Result | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Identical Commit** | `awesome-digital-twins` | `3253040` vs `3253040` | 0 changes, `IDENTICAL_COMMITS`, `is_verified_zero=True` | Matches expected | **PASS** |
| **Markdown/YAML Delta** | `awesome-digital-twins` | `3253040` vs `ac0cfb6` | 1 added file (`automerge.yml`), `FILE_DIFF_ONLY` | Matches expected | **PASS** |
| **Java Config Delta** | `eclipse-ditto/ditto` | `952e3c2` vs `a9fcec7` | 1 modified file (`things.conf`), `FILE_DIFF_ONLY` | Matches expected | **PASS** |
| **AST Symbol & File Delta** | Synthetic Shop | Commit A vs Commit B | 3 symbol modifications, 1 added file | Matches expected | **PASS** |
| **Direct Impact Propagation** | Synthetic Shop | `payment_gateway.py` | Propagates to `checkout_service.py` via `CALLS` edge | Matches expected | **PASS** |
| **Multi-hop Attenuation** | Synthetic Shop | `order_calculator.py` | Depth 2 propagation with $0.85^2 = 0.72$ confidence | Matches expected | **PASS** |
| **Cycle Suppression** | Synthetic Recursive | Function X $\leftrightarrow$ Function Y | Terminates without infinite loop | Matches expected | **PASS** |
| **Safe Test Selection** | Synthetic Shop | Changed Auth module | Mapped auth tests selected; unknown tests marked RUN | Matches expected | **PASS** |

---

## 4. Regression & Verification Command Output

The regression suite `backend/tests/test_cross_repository_forensics.py` was constructed to assert:
- `test_git_tree_diff_nonexistent_workspace`: PASS
- `test_git_tree_diff_parsing`: PASS
- `test_identical_commit_comparison_is_verified_zero`: PASS
- `test_non_code_repository_git_delta_not_false_zero`: PASS
- `test_ast_symbol_and_file_diff_integration`: PASS
- `test_snapshot_isolation_prevents_cross_commit_contamination`: PASS

Combined with existing passes in `backend/tests/test_historical_evaluation.py` and `backend/tests/test_impact_determinism.py`, all core correctness invariants are satisfied.

---

## 5. Remaining Limitations & Architectural Recommendations
1. **Tree-sitter Language Support Extension:** TwinCore currently parses Python, TypeScript/JavaScript, Java, Go, and Rust via tree-sitter. Repositories in C#, Scala, Kotlin, or C++ currently fall back to file-level Git diffs until their language grammars are integrated.
2. **Git Submodules:** Submodule commits within large multi-repo structures are currently tracked as gitlink file modifications rather than automatically recursively cloned into twin snapshots.
