# Phase 9: Project Discovery & Technical Assessment — Known Limitations & Forensic Boundaries

**Project:** TwinCore — AI-Powered Software Digital Twin for Change Impact Analysis  
**Milestone:** Phase 9 — Project Discovery & Technical Assessment  
**Author:** Antigravity Agentic Engineer  
**Date:** 2026-10-19  
**Status:** ACTIVE SPECIFICATION  

---

## 1. Executive Summary of Limitations

The Phase 9 Project Discovery & Technical Assessment engine is designed to be **evidence-backed, truthful, and strictly non-destructive**. It operates on deterministic static analysis, graph traversal, and persisted architectural digital twin state.

In accordance with Phase 9 Non-Negotiable Rules, TwinCore explicitly discloses all known architectural, linguistic, operational, and forensic boundaries.

---

## 2. Language & AST Parsing Boundaries

### Supported Languages (Deep Semantic AST Analysis)
The following languages are supported with full structural AST extraction (classes, interfaces, methods, functions, services, calls, and imports):
- **TypeScript / JavaScript** (`.ts`, `.tsx`, `.js`, `.jsx`) via Tree-Sitter & custom AST visitors
- **Python** (`.py`) via Python `ast` parser
- **Java** (`.java`) via Java Tree-Sitter AST parser
- **Go** (`.go`) via Go AST parser
- **Rust** (`.rs`) via Tree-Sitter parser

### Partially Supported Languages (Manifest & File Discovery Only)
- **C / C++** (`.c`, `.cpp`, `.h`, `.hpp`): Discovered in file inventory; semantic dependency extraction is bounded to manifest inspection (`CMakeLists.txt`, `Makefile`) unless compiled with clang compilation database.
- **Polyglot Monorepos**: Discovered and profiled per-directory; cross-language IPC/gRPC calls are resolved only when explicit protocol buffer or OpenAPI schemas are indexed.

### Unsupported Languages (Classified as `UNSUPPORTED`)
- **COBOL, Fortran, Pascal, Assembly, Legacy Mainframe**:
  - Repositories consisting exclusively of unsupported languages or non-code documentation (e.g. `edt-community/awesome-digital-twins`, `cobol_legacy`) are truthfully classified as **`UNSUPPORTED`**.
  - **Invariant:** TwinCore never returns false zero-risk or fabricated 100/100 health metrics when structural code is absent or unparseable.

---

## 3. Repository Acquisition & Shallow Clone Boundaries

1. **Git History Depth:**
   - Repositories cloned with `--depth=1` restrict `git log` traversal to the commit shallow boundary.
   - TwinCore's historical commit discovery (`git_provider.discover_repository_commits`) dynamically unshallows the repository up to $N=30$ commits via `git fetch --depth=N origin <branch>`.
   - In air-gapped environments without network access to the origin remote, historical commit traversal is strictly bounded to commits present in the local Git pack.

2. **Source Code Immutability Guarantee:**
   - Historical commit extraction (`extract_commit_source_tree`) uses `git archive <commit_sha> | tar -x -C <dest>` to extract trees into isolated scratch directories.
   - The active working tree is never mutated or checked out during discovery.

---

## 4. Advisory Remediation Roadmap Scope & Governance

1. **Strictly Non-Destructive Advisory Recommendations:**
   - All remediation roadmaps generated during Phase 9 are **advisory only**.
   - TwinCore **never** automatically edits source files, writes commits, opens pull requests, or triggers builds without explicit engineer approval.
   - Every recommendation contains:
     - `priority`: `P0_IMMEDIATE`, `P1_HIGH`, `P2_MEDIUM`, `P3_LONG_TERM`
     - `technical_rationale`: Root-cause technical justification
     - `expected_benefit`: Quantifiable stabilization outcome
     - `verification_criteria`: Objective test or metric to confirm remediation
     - `known_limitations`: Scope boundary

2. **Absence of Calibrated Failure Probabilities:**
   - Deterministic risk scores ($0 - 100$) measure structural coupling density, circular cycles, and test deficits. They are **not** calibrated empirical probabilities of production failure.

---

## 5. Testing & Test-Linkage Limits

1. **Static Linkage vs Dynamic Coverage:**
   - TwinCore links test suites to source components through:
     - Direct AST imports (`import { OrderService } from './order.service'`)
     - Causal test relationship graph (`RELATIONSHIP_TYPE = 'TESTS'`)
     - Standard test directory conventions (`tests/`, `__tests__/`, `*.test.ts`, `*Test.java`)
   - TwinCore does **not** assume 100% line coverage merely because a test file references a component. Dynamic line and branch coverage are reported only when lcov/cobertura execution evidence is ingested.

2. **Untracked Runtime Callers:**
   - Unregistered third-party microservices or client applications making HTTP REST calls to API endpoints cannot be statically detected unless runtime telemetry traces or OpenAPI manifests are ingested.

---

## 6. Multi-Tenant Authorization & Non-Disclosure

- Repositories belonging to tenant $A$ are strictly inaccessible to tenant $B$.
- When an unauthorized or unauthenticated principal requests assessment data for a repository they do not own, TwinCore returns `HTTP 404 Not Found` (non-disclosure invariant) rather than `403 Forbidden`, preventing enumeration of existing repository IDs.
