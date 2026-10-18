# PHASE 8.8 — Forensic Codebase & Product Reality Audit

**Audit Date**: October 4, 2026  
**Auditor**: Software Digital Twin System Verification Team  
**Scope**: Complete codebase inspection across ingestion, authentication, analysis, impact, tests, runtime, simulation, incidents, and frontend.  
**Classification Standards**: `PASS | PARTIAL | FAIL | NOT_IMPLEMENTED`

---

## 1. Capability Audit & Classification

| # | Product Capability | Current Classification | Findings & Evidence |
|---|---|---|---|
| 1 | **Repository Acquisition** | **PARTIAL** | GitHub HTTPS clone and local folder ingestion exist with SSRF DNS checks. **Defect**: Accepts arbitrary GitHub subpaths (`/blob/`, `/tree/`, `/pull/`, `/actions/`) instead of rejecting them with root-URL policy. |
| 2 | **Authentication & Authorization** | **PASS** | Multi-user PBKDF2 hashing, JWT verification, rate limiting, and zero-trust user ownership enforced across repositories, snapshots, incidents, and simulations. |
| 3 | **Snapshot Creation & Selection** | **PARTIAL** | Real Git commit introspection exists via `resolve_git_info`. **Defect**: Analysis and graph endpoints fell back to `snapshots[0]` when `snapshot_id` was omitted; frontend defaulted to `snapshots[0]` and `'snap_latest'`. |
| 4 | **Discovery & Ingestion** | **PASS** | Deterministic language detection, structural AST scanning, dependency extraction without code execution. Bounded runtime and file size limits enforced. |
| 5 | **Artifact Extraction** | **PASS** | Deterministic treesitter/AST parsing across Python, TypeScript, JavaScript, Java, Go, Rust, C/C++, etc. Extracted artifacts are persisted in PostgreSQL. |
| 6 | **Relationship Graph** | **PASS** | Typed edges (`CALLS`, `IMPORTS`, `INHERITS`, `TESTS`, etc.) with cycle protection, BFS projection, and level-based progressive disclosure. |
| 7 | **Snapshot Diff** | **PARTIAL** | Pairwise AST delta detection implemented. **Defect**: When diffing identical snapshots, system returned zero-valued `completed` status rather than truthful `NOT_READY` with explanation. |
| 8 | **Change Impact** | **PARTIAL** | Deterministic BFS propagation with cycle protection. **Defect**: Summary labeled metrics as "Direct + Indirect" which misleadingly summed overlapping multi-hop affected entities (29 unique, 7 multi-hop, 57 evidence paths). |
| 9 | **Test Impact** | **PASS** | Formal 5-state claim taxonomy implemented (`TEST_IS_AFFECTED`, `TEST_EXISTS_AND_IS_UNAFFECTED`, `TEST_EXISTS_BUT_COVERAGE_IS_UNKNOWN`, `NO_TEST_RELATIONSHIP_FOUND`, `NO_AUTOMATED_TEST_EXISTS`). |
| 10 | **Risk & Guardrails** | **PASS** | Deterministic risk scoring based on blast radius, test exposure ratio, and architectural drift violations without subjective scoring. |
| 11 | **Runtime Evidence** | **PARTIAL** | JSON/JSONL batch ingestion with entity correlation. **Defect**: Privacy gateway sanitized auth/passwords but lacked comprehensive PII regexes for phone, credit card, and customer IDs. No live telemetry claiming. |
| 12 | **Incident Investigation** | **PARTIAL** | Correlates runtime errors with modified artifacts and AST paths. **Defect**: Models used "root cause" language rather than truthful "Candidate Cause" / "Evidence-backed Candidate Path". |
| 13 | **Simulation Workspace** | **PASS** | Virtual in-memory twin isolation. Guarantees zero mutations to disk, Git working trees, or PostgreSQL base snapshot data. All findings marked `SIMULATED`. |
| 14 | **Ask Twin / Brain** | **FAIL** | Frontend implemented keyword routing in JavaScript (`qLower.includes(...)`) simulating intelligence. No deterministic backend `TwinKnowledgeService` existed. |
| 15 | **Frontend API Consumption** | **PARTIAL** | 100% of major UI views fetch real backend REST endpoints. **Defect**: Transient `snapshots[0]` and `'snap_latest'` string fallbacks masked missing data states. |
| 16 | **Workspace Persistence** | **PASS** | PostgreSQL backing stores for users, repositories, snapshots, artifacts, relationships, incidents, and scenarios. Clean session teardown. |

---

## 2. Authoritative Data Fallback Inventory

The forensic audit searched and cataloged all instances of forbidden fallbacks:

### A. `snapshots[0]` Fallbacks
- `backend/app/api/analysis.py` (lines 76, 150, 191, 285, 311): Defaulted to `snapshots[0]` when `snapshot_id` was not explicitly supplied.
- `backend/app/api/graph.py` (lines 652, 807, 862): Active snapshot fallback to `snapshots[0]`.
- `backend/app/static/twin.js` (lines 1516, 1598, 1606, 1607): Defaulted target snapshot selection to `snapshots[0]`.

### B. `snap_latest` and Fake Placeholder Fallbacks
- `backend/app/static/index.html` (line 709): Hardcoded placeholder `<span id="ov-snapshot">snap_latest</span>`.
- `backend/app/static/twin.js` (line 1736): `(snap?.id || state.currentSnapshotId || 'snap_latest')`.

### C. GitHub Non-Repository URL Ingestion
- `backend/app/services/acquisition/__init__.py`: Accepted any URL with `/` in the path, allowing URLs pointing to `/blob/`, `/tree/`, or `/pull/` to pass into `git clone`.

### D. Zero-Valued Successful Analysis on Identical/Single Snapshots
- `backend/app/services/impact/analyzer.py` (line 79): Returned `status="completed"` with 0 changed artifacts when identical snapshots were supplied.
- Lacked explicit `NOT_READY` state for single-snapshot pairwise requests.

---

## 3. Remediation Roadmap for Phase 8.8

1. **Eliminate GitHub Subpath Ingestion**: Enforce strict root-URL validation rejecting `/blob/`, `/tree/`, `/pull/`, etc. with exact policy message.
2. **Eliminate All Silent Snapshot Defaults**: Pairwise analyses must require two explicit distinct snapshots. Return `NOT_READY` for single or identical snapshots.
3. **Build `TwinKnowledgeService`**: Introduce a single, authoritative query engine in the backend exposing canonical evidence provenance.
4. **Canonical Evidence Contract**: Guarantee every response provides `evidence_id`, `provenance` (`OBSERVED`, `DERIVED`, `INFERRED`, `SIMULATED`, `UNKNOWN`), and explainable causal paths.
5. **Strengthen Privacy Gateway**: Add regex-based redaction for emails, phone numbers, credit card numbers, JWTs, and customer IDs with adversarial tests.
6. **Ground Ask Twin**: Replace client-side keyword simulation with backend `TwinKnowledgeService.ask_twin` deterministic queries.
7. **Prove Product Reality End-to-End**: Build Golden E2E fixture, Failure-Injection test suite, and CDP browser proof.
