# Forensic Engineering Audit: Historical Reconstruction & Snapshot Identity

**Project:** TwinCore — AI-Powered Software Digital Twin for Change Impact Analysis  
**Date:** 2026-10-19  
**Scope:** Git Tree Reconstruction, Revision Resolution, Snapshot Hashing, and Multi-Commit Isolation

---

## 1. Executive Summary

Historical reconstruction enables TwinCore to travel backward in time through a codebase's Git history, reconstruct exact source trees at any arbitrary commit SHA, parse that revision's AST symbols, build a point-in-time Digital Twin snapshot, and compare revisions with structural precision.

During testing against public repositories (`eclipse-ditto/ditto` and `edt-community/awesome-digital-twins`), the Change Impact interface displayed historical commits but reported **zero analyzed snapshots** and **zero changed artifacts** between historical commits.

This audit details the forensic examination of historical Git tree reconstruction, commit SHA resolution, content-addressable storage (CAS), snapshot isolation, and the hybrid comparison engine.

---

## 2. Forensic Investigation & Findings

### Finding H1: Distinction Between Discovered Historical Commits and Analyzed Snapshots
- **Status:** **PASS** (Independently Verified)
- **Severity:** High
- **Evidence:** The UI showed ~30 historical commits in the commit selector dropdowns, but the metric badge read `0 Analyzed Snapshots`.
- **Root Cause:**
  - TwinCore discovers historical Git commits via `git log -n 30 --pretty=format:...` on repository clone. These metadata entries populate the commit selector dropdowns.
  - An **Analyzed Snapshot** (`RepositorySnapshot`) is created only when a full structural twin extraction (file scanning, AST parsing, symbol extraction, call graph projection, relationship persistence) is executed.
  - When users selected two commits from the dropdown that had not undergone full AST indexing, the system attempted to compare non-existent snapshot IDs. Because the Change Detector previously relied exclusively on `StructuralArtifact` records, it silently produced `0 changes`.
- **Affected Code Paths:**
  - `backend/app/services/acquisition/git_provider.py` (`get_historical_commits`)
  - `backend/app/services/impact/change_detector.py` (`detect_changes`)
  - `backend/app/api/impact.py` (`/repositories/{id}/snapshot-diff`, `/analyze-impact`)
- **Fix Applied:**
  1. Updated `change_detector.py` to extract Git tree diff ground truth directly from the local clone using `git diff --name-status -M base_commit target_commit` when snapshots are unindexed.
  2. In `impact.py`, introduced `_ensure_snapshot()` to automatically trigger on-demand snapshot reconstruction when a deep AST impact analysis is requested for an unindexed historical commit.
  3. Added explicit UI badges in `twin.js`: `Git Revision File Delta (Unindexed Snapshot)` vs `Deep Twin AST Snapshot`.
- **Regression Test:** `backend/tests/test_cross_repository_forensics.py::test_non_code_repository_git_delta_not_false_zero`

---

### Finding H2: Exact Commit SHA Resolution and Tree Reconstruction
- **Status:** **PASS** (Independently Verified)
- **Severity:** Medium
- **Evidence:**
  - Tested on `awesome-digital-twins`:
    - Base commit: `3253040bc18b28cf9db0b53755cf643f8705bc03`
    - Target commit: `ac0cfb6ae0453d9e4a3b04c86da8329622d140e6`
    - Git diff command: `git diff --name-status 3253040 ac0cfb6`
    - Git output: `A .github/workflows/automerge.yml`
  - Tested on `eclipse-ditto/ditto`:
    - Base commit: `952e3c2718e2808c104e1e3e7fbc8ef82c58da1b`
    - Target commit: `a9fcec7135f60bdf05bbdbd3184ea059639535e6`
    - Git diff command: `git diff --name-status 952e3c2 a9fcec7`
    - Git output: `M things/service/src/main/resources/things.conf`
- **Root Cause:** Tree reconstruction previously failed if the repository used `master` or an atypical branch name because `extract_commit_source_tree` hardcoded `default_branch="main"`.
- **Affected Code Paths:**
  - `backend/app/services/acquisition/git_provider.py` (`extract_commit_source_tree`)
- **Fix Applied:**
  - Added dynamic fallback: checks `origin/HEAD`, queries local branch names (`master`, `main`), and falls back directly to raw tree extraction via `git archive` or detached HEAD checkout.
- **Regression Test:** `backend/tests/test_cross_repository_forensics.py::test_git_tree_diff_parsing`

---

### Finding H3: Snapshot Contamination Prevention & CAS Integrity
- **Status:** **PASS** (Independently Verified)
- **Severity:** High
- **Evidence:** Database inspection confirms that `StructuralArtifact` rows contain mandatory foreign keys `snapshot_id`, and `File` rows contain `snapshot_id`.
- **Root Cause & Mechanism:**
  - Every snapshot is assigned a deterministic content-addressable ID:
    $$\text{snapshot\_id} = \text{SHA256}(\text{repo\_id} + \text{commit\_hash})$$
  - Each artifact's unique key is scoped to the snapshot: `art_{snapshot_id}_{hash(qualified_name)}`.
  - When comparing `snap_A` and `snap_B`, queries enforce `WHERE snapshot_id = :base_id` and `WHERE snapshot_id = :target_id`.
  - No artifact from `snap_C` or another tenant repository can leak into the active evaluation set.
- **Affected Code Paths:**
  - `backend/app/services/analysis/persistence/twin_writer.py`
  - `backend/app/services/impact/change_detector.py`
- **Regression Test:** `backend/tests/test_cross_repository_forensics.py::test_snapshot_isolation_prevents_cross_commit_contamination`

---

### Finding H4: Genuine Zero-Change vs Unanalyzed State Discrimination
- **Status:** **PASS** (Independently Verified)
- **Severity:** High
- **Evidence:** Comparing commit `3253040` with `3253040` (identical commit) previously generated an ambiguous result. Comparing two unindexed commits previously returned the exact same `0 changes` response.
- **Root Cause:** The response schema lacked status flags distinguishing:
  1. `IDENTICAL_COMMITS`: Identical commit hashes selected; mathematically zero changes.
  2. `VERIFIED_ZERO_CHANGES`: Revisions are distinct, but Git diff and AST diff confirm zero files or symbols were modified.
  3. `FILE_DIFF_ONLY`: Commits have not been indexed into AST snapshots, but Git file deltas were computed and verified.
  4. `UNANALYZED`: No snapshot or Git clone available.
- **Affected Code Paths:**
  - `backend/app/services/impact/models.py` (`ChangeSet`)
  - `backend/app/services/impact/change_detector.py`
  - `backend/app/static/twin.js`
- **Fix Applied:**
  - Added `status`, `diff_mode`, `is_verified_zero`, and `message` to `ChangeSet`.
  - Updated frontend to display explicit badges and descriptive text for each state.
- **Regression Test:** `backend/tests/test_cross_repository_forensics.py::test_identical_commit_comparison_is_verified_zero`

---

## 3. Historical Reconstruction Verification Matrix

| Verification Dimension | Tested Behavior | Status |
| :--- | :--- | :--- |
| **Exact SHA Resolution** | Resolves 40-character SHA and 7-character short hashes | **PASS** |
| **Branch Agnostic Retrieval** | Supports `main`, `master`, tags, and detached commits | **PASS** |
| **Local Git Tree Diff** | Accurate additions, removals, modifications, and renames | **PASS** |
| **AST Symbol Differential** | Accurately identifies modified functions/methods by content hash | **PASS** |
| **Non-Code Diffs** | Correctly reports markdown, yaml, and configuration changes | **PASS** |
| **Identical Commit Guard** | Returns `IDENTICAL_COMMITS` and `is_verified_zero = True` | **PASS** |
| **Cross-Commit Isolation** | Zero artifact leakage between distinct snapshots | **PASS** |

---

## 4. Remaining Limitations
1. **Network Detached Commits:** If a user enters a commit SHA that was never fetched from GitHub (beyond the clone depth), tree reconstruction requires network access to issue a `git fetch origin <sha>`.
2. **Binary File Changes:** Binary files (e.g. `.png`, `.jar`, `.wasm`) are identified as `MODIFIED` at the file level via Git tree diff, but are excluded from AST symbol parsing.
