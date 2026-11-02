"""
Phase 4 — Change Detector.
Computes a normalized ChangeSet between baseline Snapshot A and target Snapshot B.
Performs symbol-level change resolution where supported, combined with verified
file-level changes from Git tree diff with explicit provenance.
Distinguishes verified zero-change comparisons from missing snapshots or unindexed commits.
"""

import os
import re
import hashlib
import subprocess
from typing import List, Dict, Any, Optional, Set, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.entities import Repository, RepositorySnapshot, StructuralArtifact, File
from app.services.impact.models import ChangeSet, ChangeItem, ChangeType


def _get_sanitized_git_env() -> dict:
    safe_keys = {
        "PATH", "HOME", "TMPDIR", "TEMP", "TMP", "USER",
        "LOGNAME", "LANG", "LC_ALL", "LC_CTYPE", "SYSTEMROOT", "COMSPEC"
    }
    clean_env = {k: v for k, v in os.environ.items() if k.upper() in safe_keys}
    clean_env["GIT_TERMINAL_PROMPT"] = "0"
    clean_env["GIT_OPTIONAL_LOCKS"] = "0"
    return clean_env


def run_git_tree_diff(
    workspace_path: str,
    base_ref: str,
    target_ref: str,
) -> Tuple[bool, List[Tuple[str, str, Optional[str]]], Optional[str]]:
    """
    Executes `git diff --name-status -M base_ref target_ref` on workspace_path.
    Returns (success, [(change_type, file_path, old_path_if_renamed)], error_message).
    """
    if not workspace_path or not os.path.isdir(workspace_path):
        return False, [], "Workspace path does not exist."

    dot_git = os.path.join(workspace_path, ".git")
    if not os.path.exists(dot_git):
        return False, [], "Directory is not a Git repository."

    clean_env = _get_sanitized_git_env()

    try:
        proc = subprocess.run(
            ["git", "diff", "--name-status", "-M", base_ref, target_ref],
            cwd=workspace_path,
            env=clean_env,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if proc.returncode != 0:
            err_msg = proc.stderr.strip() or f"Git diff exited with code {proc.returncode}"
            return False, [], err_msg

        entries: List[Tuple[str, str, Optional[str]]] = []
        for line in proc.stdout.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            status_code = parts[0]
            if status_code.startswith("R") and len(parts) >= 3:
                # Rename: old_path, new_path
                entries.append(("RENAMED", parts[2], parts[1]))
            elif status_code.startswith("A") and len(parts) >= 2:
                entries.append(("ADDED", parts[1], None))
            elif status_code.startswith("D") and len(parts) >= 2:
                entries.append(("REMOVED", parts[1], None))
            elif status_code.startswith("M") and len(parts) >= 2:
                entries.append(("MODIFIED", parts[1], None))
            elif len(parts) >= 2:
                entries.append(("MODIFIED", parts[1], None))

        return True, entries, None
    except Exception as exc:
        return False, [], str(exc)


def run_git_working_tree_diff(
    workspace_path: str,
    base_ref: Optional[str] = "HEAD",
) -> Tuple[bool, List[Tuple[str, str, Optional[str]]], Dict[str, List[Tuple[int, int]]], Optional[str]]:
    """
    Executes live working tree inspection using:
    1. `git status --porcelain=v1 -uall` (captures staged, unstaged, untracked modifications)
    2. `git diff -U0 <base_ref>` (captures modified line intervals in working tree & staging)
    Returns:
      (success, [(change_type, file_path, old_path_if_renamed)], {file_path: [(start_line, end_line)]}, error_message)
    """
    if not workspace_path or not os.path.isdir(workspace_path):
        return False, [], {}, "Workspace path does not exist."

    dot_git = os.path.join(workspace_path, ".git")
    if not os.path.exists(dot_git):
        return False, [], {}, "Directory is not a Git repository."

    clean_env = _get_sanitized_git_env()
    effective_base = base_ref or "HEAD"

    try:
        # Step 1: Detect all changed/untracked/deleted files via porcelain status
        proc_status = subprocess.run(
            ["git", "status", "--porcelain=v1", "-uall"],
            cwd=workspace_path,
            env=clean_env,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if proc_status.returncode != 0:
            err = proc_status.stderr.strip() or f"git status exited with {proc_status.returncode}"
            return False, [], {}, err

        entries: List[Tuple[str, str, Optional[str]]] = []
        seen_paths: Set[str] = set()

        for line in proc_status.stdout.splitlines():
            line = line.rstrip()
            if not line or len(line) < 3:
                continue
            code = line[:2]
            rest = line[3:].strip()

            # Handle renames e.g. "R  old -> new"
            if " -> " in rest:
                old_p, new_p = rest.split(" -> ", 1)
                clean_old = old_p.strip('"')
                clean_new = new_p.strip('"')
                entries.append(("RENAMED", clean_new, clean_old))
                seen_paths.add(clean_new)
            elif code == "??" or "A" in code:
                p = rest.strip('"')
                if p not in seen_paths:
                    entries.append(("ADDED", p, None))
                    seen_paths.add(p)
            elif "D" in code:
                p = rest.strip('"')
                if p not in seen_paths:
                    entries.append(("REMOVED", p, None))
                    seen_paths.add(p)
            else:
                p = rest.strip('"')
                if p not in seen_paths:
                    entries.append(("MODIFIED", p, None))
                    seen_paths.add(p)

        # Step 2: Extract modified line ranges using git diff against effective_base
        line_ranges: Dict[str, List[Tuple[int, int]]] = {}
        proc_diff = subprocess.run(
            ["git", "diff", "-U0", effective_base],
            cwd=workspace_path,
            env=clean_env,
            capture_output=True,
            text=True,
            timeout=20,
        )
        if proc_diff.returncode == 0:
            current_file = None
            hunk_re = re.compile(r"^@@\s+-(?P<old_start>\d+)(?:,(?P<old_count>\d+))?\s+\+(?P<new_start>\d+)(?:,(?P<new_count>\d+))?\s+@@")
            for dline in proc_diff.stdout.splitlines():
                if dline.startswith("+++ b/"):
                    current_file = dline[6:].strip()
                elif dline.startswith("@@ ") and current_file:
                    m = hunk_re.match(dline)
                    if m:
                        n_start = int(m.group("new_start"))
                        n_cnt = int(m.group("new_count") or 1)
                        if n_cnt == 0:
                            line_ranges.setdefault(current_file, []).append((n_start, n_start))
                        else:
                            line_ranges.setdefault(current_file, []).append((n_start, n_start + max(1, n_cnt) - 1))

        return True, entries, line_ranges, None
    except Exception as exc:
        return False, [], {}, str(exc)



class ChangeDetector:
    """
    Deterministic detector of additions, removals, and modifications between two snapshots.
    Integrates Git tree deltas with AST symbol extraction for deep, multi-language coverage.
    """

    def detect_changes(
        self,
        db: Session,
        repository_id: str,
        base_snapshot_id: str,
        target_snapshot_id: Optional[str] = None,
        base_artifacts: Optional[List[StructuralArtifact]] = None,
        target_artifacts: Optional[List[StructuralArtifact]] = None,
    ) -> ChangeSet:
        """
        Builds a normalized ChangeSet between base_snapshot_id and target_snapshot_id.
        Resolves commit SHAs or snapshot IDs transparently.
        """
        if target_snapshot_id is None:
            target_snapshot_id = base_snapshot_id
            base_snapshot_id = repository_id
            snap = db.query(RepositorySnapshot).filter_by(id=base_snapshot_id).first()
            repository_id = snap.repository_id if snap else "repo_unknown"

        repo = db.query(Repository).filter_by(id=repository_id).first()

        # 1. Resolve snapshots from database (by ID, full commit SHA, or prefix)
        base_snap = db.query(RepositorySnapshot).filter(
            RepositorySnapshot.repository_id == repository_id,
            or_(
                RepositorySnapshot.id == base_snapshot_id,
                RepositorySnapshot.commit_hash == base_snapshot_id,
                RepositorySnapshot.commit_hash.startswith(base_snapshot_id),
            ),
        ).first()

        target_snap = db.query(RepositorySnapshot).filter(
            RepositorySnapshot.repository_id == repository_id,
            or_(
                RepositorySnapshot.id == target_snapshot_id,
                RepositorySnapshot.commit_hash == target_snapshot_id,
                RepositorySnapshot.commit_hash.startswith(target_snapshot_id),
            ),
        ).first()

        # 1. Immediate check for identical commit / snapshot selection
        if base_snapshot_id and target_snapshot_id and base_snapshot_id == target_snapshot_id:
            return ChangeSet(
                repository_id=str(repository_id),
                base_snapshot_id=str(base_snapshot_id),
                target_snapshot_id=str(target_snapshot_id),
                status="IDENTICAL_COMMITS",
                is_verified_zero=True,
                diff_mode="IDENTICAL",
                message=f"Baseline and Target refer to the identical revision ({str(base_snapshot_id)[:7]}).",
                summary={"total_changes": 0, "added": 0, "removed": 0, "modified": 0, "status": "IDENTICAL_COMMITS"},
            )

        canonical_base_id = (
            str(base_snap.id)
            if (base_snap and isinstance(getattr(base_snap, "id", None), str))
            else str(base_snapshot_id)
        )
        canonical_target_id = (
            str(target_snap.id)
            if (target_snap and isinstance(getattr(target_snap, "id", None), str))
            else str(target_snapshot_id)
        )

        base_ref = (
            str(base_snap.commit_hash)
            if (base_snap and isinstance(getattr(base_snap, "commit_hash", None), str))
            else str(base_snapshot_id)
        )
        target_ref = (
            str(target_snap.commit_hash)
            if (target_snap and isinstance(getattr(target_snap, "commit_hash", None), str))
            else str(target_snapshot_id)
        )

        # 2. Check for identical commit / snapshot selection
        if (
            canonical_base_id == canonical_target_id
            or (base_snap and target_snap and getattr(base_snap, "id", None) == getattr(target_snap, "id", None))
            or (base_ref and target_ref and base_ref == target_ref)
        ):
            return ChangeSet(
                repository_id=str(repository_id),
                base_snapshot_id=canonical_base_id,
                target_snapshot_id=canonical_target_id,
                status="IDENTICAL_COMMITS",
                is_verified_zero=True,
                diff_mode="IDENTICAL",
                message=f"Baseline and Target refer to the identical revision ({base_ref[:7] if base_ref else 'same'}).",
                summary={"total_changes": 0, "added": 0, "removed": 0, "modified": 0, "status": "IDENTICAL_COMMITS"},
            )

        change_set = ChangeSet(
            repository_id=str(repository_id),
            base_snapshot_id=canonical_base_id,
            target_snapshot_id=canonical_target_id,
        )

        # 3. Compute Git tree diff if workspace is available
        git_entries: List[Tuple[str, str, Optional[str]]] = []
        git_diff_ok = False
        git_error = None
        if repo and getattr(repo, "local_path", None):
            git_diff_ok, git_entries, git_error = run_git_tree_diff(
                workspace_path=str(repo.local_path),
                base_ref=base_ref,
                target_ref=target_ref,
            )

        # If both snapshots are missing from DB and Git diff failed, report missing revision
        if not base_snap and not target_snap and not git_diff_ok:
            change_set.status = "REVISION_RESOLUTION_FAILED"
            change_set.is_verified_zero = False
            change_set.diff_mode = "FAILED"
            change_set.message = f"Failed to resolve Git revisions or snapshots: {git_error or 'Unknown revision error'}"
            change_set.summary = {"total_changes": 0, "added": 0, "removed": 0, "modified": 0, "status": "REVISION_RESOLUTION_FAILED"}
            return change_set

        # 4. If Git diff is valid and shows zero changes:
        if git_diff_ok and len(git_entries) == 0:
            change_set.status = "VERIFIED_ZERO_CHANGES"
            change_set.is_verified_zero = True
            change_set.diff_mode = "VERIFIED_CLEAN"
            change_set.message = f"Zero differences detected between Git revisions {base_ref[:7]} and {target_ref[:7]}."
            change_set.summary = {"total_changes": 0, "added": 0, "removed": 0, "modified": 0, "status": "VERIFIED_ZERO_CHANGES"}
            return change_set

        # 5. Extract symbol-level differences if snapshots are indexed
        changes: List[ChangeItem] = []
        files_with_symbols: Set[str] = set()
        symbol_added_count = 0
        symbol_removed_count = 0
        symbol_modified_count = 0

        has_indexed_snapshots = bool(
            (base_snap and target_snap)
            or (base_artifacts is not None and target_artifacts is not None)
        )

        if has_indexed_snapshots:
            if base_artifacts is None and base_snap:
                base_artifacts = (
                    db.query(StructuralArtifact)
                    .filter_by(snapshot_id=base_snap.id)
                    .all()
                )
            if target_artifacts is None and target_snap:
                target_artifacts = (
                    db.query(StructuralArtifact)
                    .filter_by(snapshot_id=target_snap.id)
                    .all()
                )

            # Strict snapshot scoping to prevent cross-commit contamination
            valid_base_ids = {canonical_base_id, str(base_snapshot_id)}
            if base_snap and hasattr(base_snap, "id") and isinstance(base_snap.id, str):
                valid_base_ids.add(base_snap.id)
            valid_target_ids = {canonical_target_id, str(target_snapshot_id)}
            if target_snap and hasattr(target_snap, "id") and isinstance(target_snap.id, str):
                valid_target_ids.add(target_snap.id)

            base_arts = [
                a for a in (base_artifacts or [])
                if getattr(a, "snapshot_id", None) in valid_base_ids or (base_snap is None and base_artifacts is not None)
            ]
            target_arts = [
                a for a in (target_artifacts or [])
                if getattr(a, "snapshot_id", None) in valid_target_ids or (target_snap is None and target_artifacts is not None)
            ]

            base_qual_map: Dict[str, StructuralArtifact] = {a.qualified_name: a for a in base_arts}
            target_qual_map: Dict[str, StructuralArtifact] = {a.qualified_name: a for a in target_arts}

            base_quals = set(base_qual_map.keys())
            target_quals = set(target_qual_map.keys())

            added_quals = target_quals - base_quals
            removed_quals = base_quals - target_quals
            common_quals = base_quals & target_quals

            # 5a. Added Symbols
            for q in sorted(added_quals):
                art = target_qual_map[q]
                # Filter out synthetic external dependency placeholders for relative import paths
                if art.artifact_type == "EXTERNAL_DEPENDENCY" and (
                    art.location == "<external>" or art.qualified_name.startswith((".", "/"))
                ):
                    continue
                is_symbol = art.artifact_type not in ("MODULE", "PACKAGE", "DIRECTORY", "EXTERNAL_DEPENDENCY")
                src_file = (art.location or "").split(":")[0]
                if src_file:
                    files_with_symbols.add(src_file)
                changes.append(
                    ChangeItem(
                        artifact_id=art.id,
                        qualified_name=art.qualified_name,
                        symbol_name=art.name,
                        artifact_type=art.artifact_type,
                        source_file=src_file,
                        change_type=ChangeType.ADDED,
                        target_location=art.location,
                        target_hash=art.source_hash,
                        line_start=art.line_start,
                        line_end=art.line_end,
                        confidence=1.0,
                        detection_method="structural_symbol_diff" if is_symbol else "file_manifest_diff",
                        is_symbol_level=is_symbol,
                        evidence=[f"Added artifact {art.qualified_name} ({art.artifact_type}) in target snapshot"],
                    )
                )
                symbol_added_count += 1

            # 5b. Removed Symbols
            for q in sorted(removed_quals):
                art = base_qual_map[q]
                if art.artifact_type == "EXTERNAL_DEPENDENCY" and (
                    art.location == "<external>" or art.qualified_name.startswith((".", "/"))
                ):
                    continue
                is_symbol = art.artifact_type not in ("MODULE", "PACKAGE", "DIRECTORY", "EXTERNAL_DEPENDENCY")
                src_file = (art.location or "").split(":")[0]
                if src_file:
                    files_with_symbols.add(src_file)
                changes.append(
                    ChangeItem(
                        artifact_id=art.id,
                        qualified_name=art.qualified_name,
                        symbol_name=art.name,
                        artifact_type=art.artifact_type,
                        source_file=src_file,
                        change_type=ChangeType.REMOVED,
                        base_location=art.location,
                        base_hash=art.source_hash,
                        line_start=art.line_start,
                        line_end=art.line_end,
                        confidence=1.0,
                        detection_method="structural_symbol_diff" if is_symbol else "file_manifest_diff",
                        is_symbol_level=is_symbol,
                        evidence=[f"Removed artifact {art.qualified_name} ({art.artifact_type}) absent in target snapshot"],
                    )
                )
                symbol_removed_count += 1

            # 5c. Modified Symbols
            for q in sorted(common_quals):
                b_art = base_qual_map[q]
                t_art = target_qual_map[q]
                if t_art.artifact_type == "EXTERNAL_DEPENDENCY" and (
                    t_art.location == "<external>" or t_art.qualified_name.startswith((".", "/"))
                ):
                    continue

                is_modified = False
                mod_reasons = []

                if b_art.source_hash and t_art.source_hash and b_art.source_hash != t_art.source_hash:
                    is_modified = True
                    mod_reasons.append("source_hash_differs")

                if (b_art.signature or "") != (t_art.signature or ""):
                    is_modified = True
                    mod_reasons.append(f"signature_changed: '{b_art.signature}' -> '{t_art.signature}'")

                if (b_art.line_start != t_art.line_start) or (b_art.line_end != t_art.line_end):
                    is_modified = True
                    mod_reasons.append(f"lines_shifted: {b_art.line_start}-{b_art.line_end} -> {t_art.line_start}-{t_art.line_end}")

                if is_modified:
                    is_symbol = t_art.artifact_type not in ("MODULE", "PACKAGE", "DIRECTORY")
                    src_file = (t_art.location or "").split(":")[0]
                    if src_file:
                        files_with_symbols.add(src_file)
                    changes.append(
                        ChangeItem(
                            artifact_id=t_art.id,
                            qualified_name=t_art.qualified_name,
                            symbol_name=t_art.name,
                            artifact_type=t_art.artifact_type,
                            source_file=src_file,
                            change_type=ChangeType.MODIFIED,
                            base_location=b_art.location,
                            target_location=t_art.location,
                            base_hash=b_art.source_hash,
                            target_hash=t_art.source_hash,
                            line_start=t_art.line_start,
                            line_end=t_art.line_end,
                            confidence=0.95 if is_symbol else 0.85,
                            detection_method="structural_ast_comparison" if is_symbol else "file_level_fallback",
                            is_symbol_level=is_symbol,
                            evidence=[f"Modified {t_art.qualified_name}: {', '.join(mod_reasons)}"],
                        )
                    )
                    symbol_modified_count += 1

        # 6. Complement symbol changes with verified file-level diffs from Git
        # This captures non-code files (markdown, configs, manifests, workflows) and files not yet indexed
        file_added_count = 0
        file_removed_count = 0
        file_modified_count = 0

        for change_kind, fpath, old_path in git_entries:
            # If this file already produced concrete symbol changes, skip duplicate file-level item
            if fpath in files_with_symbols:
                continue

            fname = os.path.basename(fpath)
            path_hash = hashlib.sha256(fpath.encode("utf-8")).hexdigest()[:12]

            if change_kind == "ADDED":
                c_type = ChangeType.ADDED
                file_added_count += 1
                ev = f"Added file {fpath} in Git revision {target_ref[:7]}"
            elif change_kind == "REMOVED":
                c_type = ChangeType.REMOVED
                file_removed_count += 1
                ev = f"Removed file {fpath} absent in Git revision {target_ref[:7]}"
            elif change_kind == "RENAMED":
                c_type = ChangeType.RENAMED
                file_modified_count += 1
                ev = f"Renamed file from {old_path} to {fpath} in Git revision {target_ref[:7]}"
            else:
                c_type = ChangeType.MODIFIED
                file_modified_count += 1
                ev = f"Modified file {fpath} in Git revision delta"

            changes.append(
                ChangeItem(
                    artifact_id=f"file_{path_hash}",
                    qualified_name=fpath,
                    symbol_name=fname,
                    artifact_type="FILE",
                    source_file=fpath,
                    change_type=c_type,
                    base_location=old_path or fpath,
                    target_location=fpath,
                    confidence=1.0,
                    detection_method="git_tree_diff",
                    is_symbol_level=False,
                    evidence=[ev],
                )
            )

        # Sort deterministically
        changes.sort(key=lambda c: (c.change_type.value, c.source_file, c.qualified_name))

        change_set.changes = changes
        change_set.status = "COMPLETED" if has_indexed_snapshots else "FILE_DIFF_ONLY"
        change_set.diff_mode = "SYMBOL_AND_FILE" if has_indexed_snapshots else "FILE_DIFF_ONLY"
        change_set.is_verified_zero = (len(changes) == 0)

        if not has_indexed_snapshots:
            change_set.message = (
                f"File-level revision delta computed directly from Git source tree ({len(changes)} files changed). "
                "Historical commit has not yet been indexed into a full AST snapshot."
            )
        else:
            change_set.message = f"Successfully computed change set ({len(changes)} total changed artifacts)."

        total_added = symbol_added_count + file_added_count
        total_removed = symbol_removed_count + file_removed_count
        total_modified = symbol_modified_count + file_modified_count

        change_set.summary = {
            "total_changes": len(changes),
            "added": total_added,
            "removed": total_removed,
            "modified": total_modified,
            "symbol_level_count": len([c for c in changes if c.is_symbol_level]),
            "file_level_count": len([c for c in changes if not c.is_symbol_level]),
            "status": change_set.status,
            "diff_mode": change_set.diff_mode,
        }

        return change_set

    def detect_live_changes(
        self,
        db: Session,
        repository_id: str,
        base_snapshot_id: Optional[str] = None,
    ) -> ChangeSet:
        """
        Inspects the live working tree of repository_id against the active or specified baseline snapshot.
        Identifies uncommitted file modifications, line additions, and deleted files, mapping them
        to AST symbols (functions, classes, endpoints) in the baseline Digital Twin.
        """
        repo = db.query(Repository).filter(
            or_(
                Repository.id == repository_id,
                Repository.name == repository_id,
            )
        ).first()

        if not repo:
            return ChangeSet(
                repository_id=str(repository_id),
                base_snapshot_id="unknown",
                target_snapshot_id="working-tree",
                status="REPOSITORY_NOT_FOUND",
                is_verified_zero=False,
                diff_mode="FAILED",
                message=f"Repository '{repository_id}' could not be found.",
                summary={"total_changes": 0, "status": "REPOSITORY_NOT_FOUND"},
            )

        # 1. Resolve baseline snapshot
        base_snap = None
        if base_snapshot_id:
            base_snap = db.query(RepositorySnapshot).filter(
                RepositorySnapshot.repository_id == repo.id,
                or_(
                    RepositorySnapshot.id == base_snapshot_id,
                    RepositorySnapshot.commit_hash == base_snapshot_id,
                    RepositorySnapshot.commit_hash.startswith(base_snapshot_id),
                ),
            ).first()

        if not base_snap:
            base_snap = (
                db.query(RepositorySnapshot)
                .filter_by(repository_id=repo.id)
                .order_by(RepositorySnapshot.created_at.desc())
                .first()
            )

        canonical_base_id = str(base_snap.id) if base_snap else "none"
        base_commit_ref = str(base_snap.commit_hash) if (base_snap and base_snap.commit_hash) else "HEAD"
        canonical_target_id = f"{canonical_base_id}:working-tree"

        change_set = ChangeSet(
            repository_id=str(repo.id),
            base_snapshot_id=canonical_base_id,
            target_snapshot_id=canonical_target_id,
        )

        if not repo.local_path or not os.path.isdir(str(repo.local_path)):
            change_set.status = "WORKSPACE_UNAVAILABLE"
            change_set.is_verified_zero = True
            change_set.diff_mode = "LIVE_WORKING_TREE"
            change_set.message = f"Local workspace directory '{repo.local_path}' is not accessible on disk."
            change_set.summary = {"total_changes": 0, "added": 0, "removed": 0, "modified": 0, "status": "WORKSPACE_UNAVAILABLE"}
            return change_set

        # 2. Run working tree git inspection
        ok, entries, line_ranges, git_err = run_git_working_tree_diff(
            workspace_path=str(repo.local_path),
            base_ref=base_commit_ref,
        )

        if not ok:
            change_set.status = "GIT_DIFF_ERROR"
            change_set.is_verified_zero = False
            change_set.diff_mode = "FAILED"
            change_set.message = f"Failed to inspect working tree: {git_err or 'Unknown git error'}"
            change_set.summary = {"total_changes": 0, "status": "GIT_DIFF_ERROR"}
            return change_set

        # 3. Clean working tree check
        if not entries:
            change_set.status = "VERIFIED_CLEAN"
            change_set.is_verified_zero = True
            change_set.diff_mode = "LIVE_WORKING_TREE"
            change_set.message = f"Working tree is clean. Zero uncommitted changes detected vs baseline {base_commit_ref[:7]}."
            change_set.summary = {
                "total_changes": 0,
                "added": 0,
                "removed": 0,
                "modified": 0,
                "symbol_level_count": 0,
                "file_level_count": 0,
                "working_tree_status": "CLEAN",
                "status": "VERIFIED_CLEAN",
                "diff_mode": "LIVE_WORKING_TREE",
            }
            return change_set

        # 4. Map changes to StructuralArtifacts
        base_artifacts = []
        if base_snap:
            base_artifacts = db.query(StructuralArtifact).filter_by(snapshot_id=base_snap.id).all()

        file_to_artifacts: Dict[str, List[StructuralArtifact]] = {}
        for a in base_artifacts:
            loc = a.location or ""
            fpath = loc.split(":")[0] if ":" in loc else loc
            fpath = fpath.lstrip("./")
            file_to_artifacts.setdefault(fpath, []).append(a)

        changes: List[ChangeItem] = []
        files_with_symbols: Set[str] = set()
        symbol_added_count = 0
        symbol_removed_count = 0
        symbol_modified_count = 0
        file_added_count = 0
        file_removed_count = 0
        file_modified_count = 0

        for change_kind, raw_fpath, old_path in entries:
            norm_fpath = raw_fpath.lstrip("./")
            mod_intervals = line_ranges.get(raw_fpath) or line_ranges.get(norm_fpath) or []

            candidate_artifacts = file_to_artifacts.get(norm_fpath) or file_to_artifacts.get(raw_fpath) or []
            matched_in_file = False

            if change_kind == "REMOVED":
                for art in candidate_artifacts:
                    is_symbol = art.artifact_type not in ("MODULE", "PACKAGE", "DIRECTORY")
                    changes.append(
                        ChangeItem(
                            artifact_id=art.id,
                            qualified_name=art.qualified_name,
                            symbol_name=art.name,
                            artifact_type=art.artifact_type,
                            source_file=norm_fpath,
                            change_type=ChangeType.REMOVED,
                            base_location=art.location,
                            line_start=art.line_start,
                            line_end=art.line_end,
                            confidence=0.95,
                            detection_method="working_tree_file_deletion",
                            is_symbol_level=is_symbol,
                            evidence=[f"Uncommitted file deletion removed {art.qualified_name} ({art.artifact_type})"],
                        )
                    )
                    symbol_removed_count += 1
                    files_with_symbols.add(norm_fpath)
                    matched_in_file = True

            elif change_kind in ("MODIFIED", "RENAMED") and candidate_artifacts:
                for art in candidate_artifacts:
                    is_symbol = art.artifact_type not in ("MODULE", "PACKAGE", "DIRECTORY")
                    intersects = False
                    intersecting_hunks = []
                    if mod_intervals and art.line_start is not None:
                        a_start = art.line_start
                        a_end = art.line_end or art.line_start
                        for h_start, h_end in mod_intervals:
                            if not (a_end < h_start or a_start > h_end):
                                intersects = True
                                intersecting_hunks.append(f"{h_start}-{h_end}")
                    elif not mod_intervals:
                        intersects = True

                    if intersects:
                        matched_in_file = True
                        files_with_symbols.add(norm_fpath)
                        hunk_desc = f" at lines {', '.join(intersecting_hunks)}" if intersecting_hunks else ""
                        changes.append(
                            ChangeItem(
                                artifact_id=art.id,
                                qualified_name=art.qualified_name,
                                symbol_name=art.name,
                                artifact_type=art.artifact_type,
                                source_file=norm_fpath,
                                change_type=ChangeType.MODIFIED,
                                base_location=art.location,
                                target_location=f"{norm_fpath} (working tree)",
                                line_start=art.line_start,
                                line_end=art.line_end,
                                confidence=0.95 if intersecting_hunks else 0.85,
                                detection_method="working_tree_hunk_intersection" if intersecting_hunks else "working_tree_file_change",
                                is_symbol_level=is_symbol,
                                evidence=[f"Uncommitted working tree edit intersects {art.qualified_name} ({art.artifact_type}){hunk_desc}"],
                            )
                        )
                        symbol_modified_count += 1

            if not matched_in_file or norm_fpath not in files_with_symbols:
                fname = os.path.basename(norm_fpath)
                path_hash = hashlib.sha256(norm_fpath.encode("utf-8")).hexdigest()[:12]
                if change_kind == "ADDED":
                    c_type = ChangeType.ADDED
                    file_added_count += 1
                    ev = f"Uncommitted new file added in working tree: {norm_fpath}"
                elif change_kind == "REMOVED":
                    c_type = ChangeType.REMOVED
                    file_removed_count += 1
                    ev = f"Uncommitted file deleted in working tree: {norm_fpath}"
                elif change_kind == "RENAMED":
                    c_type = ChangeType.RENAMED
                    file_modified_count += 1
                    ev = f"Uncommitted file rename: {old_path} -> {norm_fpath}"
                else:
                    c_type = ChangeType.MODIFIED
                    file_modified_count += 1
                    ev = f"Uncommitted file modification in working tree: {norm_fpath}"

                changes.append(
                    ChangeItem(
                        artifact_id=f"file_{path_hash}",
                        qualified_name=norm_fpath,
                        symbol_name=fname,
                        artifact_type="FILE",
                        source_file=norm_fpath,
                        change_type=c_type,
                        base_location=old_path or norm_fpath,
                        target_location=norm_fpath,
                        confidence=0.9,
                        detection_method="working_tree_git_status",
                        is_symbol_level=False,
                        evidence=[ev],
                    )
                )

        changes.sort(key=lambda c: (c.change_type.value, c.source_file, c.qualified_name))
        change_set.changes = changes
        change_set.status = "COMPLETED"
        change_set.diff_mode = "LIVE_WORKING_TREE"
        change_set.is_verified_zero = (len(changes) == 0)
        change_set.message = (
            f"Live incremental analysis detected {len(changes)} changed artifacts "
            f"({len([c for c in changes if c.is_symbol_level])} symbol-level, {len([c for c in changes if not c.is_symbol_level])} file-level) "
            f"in local workspace."
        )

        change_set.summary = {
            "total_changes": len(changes),
            "added": symbol_added_count + file_added_count,
            "removed": symbol_removed_count + file_removed_count,
            "modified": symbol_modified_count + file_modified_count,
            "symbol_level_count": len([c for c in changes if c.is_symbol_level]),
            "file_level_count": len([c for c in changes if not c.is_symbol_level]),
            "working_tree_status": "DIRTY" if len(changes) > 0 else "CLEAN",
            "status": "COMPLETED",
            "diff_mode": "LIVE_WORKING_TREE",
        }

        return change_set


def map_changes_to_proposed_mutations(changes: List[ChangeItem]) -> List[Dict[str, Any]]:
    """
    Converts detected live change items into ProposedMutation payloads suitable for
    one-click What-If virtual twin scenario simulation.
    """
    mutations: List[Dict[str, Any]] = []
    seen_targets: Set[str] = set()

    for idx, c in enumerate(changes):
        target_name = c.qualified_name or c.symbol_name or c.source_file
        if not target_name or target_name in seen_targets:
            continue
        seen_targets.add(target_name)

        if c.artifact_type == "API_ENDPOINT":
            mut_type = "MODIFY_API"
        elif c.change_type == ChangeType.REMOVED:
            mut_type = "REMOVE_COMPONENT"
        elif c.change_type == ChangeType.ADDED and not c.is_symbol_level:
            mut_type = "ADD_DEPENDENCY"
        else:
            mut_type = "MODIFY_SYMBOL"

        mutations.append({
            "mutation_id": f"live_mut_{idx + 1}_{hashlib.sha256(target_name.encode()).hexdigest()[:8]}",
            "mutation_type": mut_type,
            "target": target_name,
            "target_entity": target_name,
            "description": f"Live change: {c.change_type.value} on {target_name} ({c.source_file})",
            "parameters": {
                "source_file": c.source_file,
                "artifact_type": c.artifact_type,
                "is_symbol_level": c.is_symbol_level,
                "detection_method": c.detection_method,
                "confidence": c.confidence,
                "line_start": c.line_start,
                "line_end": c.line_end,
            },
        })
    return mutations


change_detector = ChangeDetector()

