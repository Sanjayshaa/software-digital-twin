# ADR 001: Immutable Snapshot Identity Specification

**Status**: ACCEPTED  
**Date**: 2026-10-05  
**Context**: Phase 8.9 Audit of Snapshot Identity & Cache Key Invariance  

---

## 1. Context & Problem Statement

In the Software Digital Twin, a `RepositorySnapshot` represents an immutable state of a software repository against which AST structural artifacts, typed relationships, and change diffs are evaluated.
Historically, snapshot identity was loosely bound to:
$$\text{Snapshot ID} = f(\text{commit\_hash})$$
with `branch_name` and `repository_id` stored as relational attributes.

However, in continuous software engineering research:
1. Two analysis runs on the **same commit** with **different analyzer parser versions** produce different ASTs.
2. Two analysis runs with **different extraction configurations** (e.g. `max_depth`, alias resolution flags) produce different relationship sets.
3. Branch names change constantly (e.g., fast-forward merges) and must **never** form part of the immutable snapshot identity.

---

## 2. Decision: Four-Tuple Snapshot Identity

The formal conceptual identity of a snapshot is defined as:

$$\text{SnapshotIdentity} = \mathcal{H}\Big(\text{RepositoryID} \parallel \text{CommitSHA} \parallel \text{ExtractorVersion} \parallel \text{ConfigurationHash}\Big)$$

Where:
- **`RepositoryID`**: Unique immutable UUID of the ingested repository.
- **`CommitSHA`**: Exact 40-character hexadecimal Git commit hash (or content tree hash).
- **`ExtractorVersion`**: Version tag of the AST analyzer engine (e.g., `ast-ts-2.4.0`, `ast-py-1.8.0`).
- **`ConfigurationHash`**: SHA-256 of the active analysis configuration parameters.

### Current Implementation Gap:
In the current PostgreSQL schema, `RepositorySnapshot` stores:
- `id`: `snap_<hash>` (UUID / hex)
- `repository_id`: UUID
- `commit_hash`: 40-character SHA
- `branch_name`: string
- `snapshot_metadata`: JSONB

### Remediation Path:
To avoid breaking backward compatibility with existing snapshots:
1. `extractor_version` and `configuration_hash` are persisted inside `snapshot_metadata` JSONB:
   ```json
   {
     "extractor_version": "tree-sitter-8.9.0",
     "configuration_hash": "a1b2c3d4e5f6...",
     "is_content_addressed": true
   }
   ```
2. Any equality check between snapshots compares `(repository_id, commit_hash, metadata.extractor_version)`.
3. In Phase 9+, a dedicated database column `extractor_version` will be migrated with index support.
