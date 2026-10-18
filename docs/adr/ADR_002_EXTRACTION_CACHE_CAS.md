# ADR 002: Content-Addressed Storage (CAS) & Incremental Extraction Cache Design

**Status**: PROPOSED / ARCHITECTURAL DESIGN NOTE  
**Date**: 2026-10-05  
**Context**: Phase 8.9 Architecture Review for Scaling Beyond 50,000 Artifacts  

---

## 1. Context & Motivation

Currently, when a new snapshot of a repository is synthesized, the AST analyzer parses the entire working tree of files, creating new rows in `structural_artifacts` and `artifact_relationships`.
In typical software development workflows:
- A Git commit alters between 1 and 15 files out of thousands ($< 1\%$ of the codebase).
- Re-parsing 99% of unchanged files wastes CPU cycles and bloats the PostgreSQL database with redundant rows.
- Full re-indexing also slows down CI/CD analysis from seconds to minutes.

---

## 2. Proposed Architecture: Two-Phase Content-Addressed Extraction

```
COMMIT SHA
    │
    ▼
TREE OBJECT ────> Path ──> Blob SHA-256
                                │
                 ┌──────────────┴──────────────┐
                 ▼                             ▼
       [CACHE HIT: Blob SHA]         [CACHE MISS: New Blob]
       Load cached FileFact           Run Tree-sitter / AST
       (Symbols, Local Edges)         Generate FileFact
                 │                             │
                 └──────────────┬──────────────┘
                                ▼
                   [GLOBAL LINKING PHASE]
                   (Cross-File Symbol Resolution)
                                │
                                ▼
                   [SNAPSHOT ADJACENCY MATRIX]
```

### 1. Phase 1: Local File Facts (Content-Addressed)
- Keyed by: `CacheKey = SHA256(BlobContent || ExtractorVersion || FilePath)`
- Contains:
  - Exported classes, functions, interfaces, methods, constants.
  - Internal call edges within the file.
  - Unresolved external references (`import { X } from './y'`).
- Invariant: A `FileFact` is completely immutable. If `Blob SHA` is identical across 500 commits, it is extracted **exactly once**.

### 2. Phase 2: Incremental Global Resolution (Linker)
- When a commit changes file $A$:
  1. Only $A$'s `FileFact` is recomputed.
  2. The linker identifies which files import or depend on $A$ (the "invalidation frontier").
  3. Cross-file edges are re-resolved only along the invalidation frontier.
  4. All other cross-file edges from the parent snapshot are inherited by reference.

---

## 3. Storage Efficiency Gains

| Metric | Current Model (Full Snapshot) | Proposed CAS Model |
| :--- | :--- | :--- |
| **Storage per Commit (1,000 files)** | 1,100 rows ($100\%$) | ~15 rows ($1.5\%$) |
| **Analysis Latency** | $2.5\text{s}$ | $< 80\text{ms}$ |
| **Memory Footprint** | Re-instantiates full graph | Shares immutable subtrees |
| **Database De-duplication** | None (UUID per snapshot) | Global deduplication by content hash |

---

## 4. Implementation Phasing

- **Phase 8.9 (Current)**: Architecture frozen; design formally recorded in this ADR.
- **Phase 9.1**: Introduce `file_facts_cas` table in PostgreSQL; implement blob-hash lookup in `discovery/engine.py`.
- **Phase 9.2**: Implement invalidation-frontier linker.
