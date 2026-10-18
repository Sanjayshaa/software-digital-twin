# PRODUCT REALITY AUDIT: End-to-End Data Pipeline & Ground-Truth Verification

**System**: TwinCore — AI-Powered Software Digital Twin for Change Impact Analysis  
**Date**: October 4, 2026  
**Status**: ACTIVE SYSTEM AUDIT & REMEDIATION MANDATE  
**Primary Guideline**: Zero feature additions. Zero UI redesigns. Zero mock data. Zero fake metrics. Zero placeholder intelligence. Every pixel and number must strictly project verified repository-derived data.

---

## 1. Executive Summary: The Product Reality Problem

A modern engineering tool can easily slip into **vibe-coding**: visually impressive dashboards with cards, graphs, counters, and pulse badges that suggest advanced intelligence, but whose underlying UI state machine is either partially disconnected from backend APIs or silently assumes hardcoded/fallback values.

### The Ground-Truth Architectural Principle
```
      REAL REPOSITORY SOURCE
               │
               ▼
      DETERMINISTIC INGESTION (Git / Archive / Local)
               │
               ▼
      IMMUTABLE REPOSITORY SNAPSHOT (Commit SHA / Branch)
               │
               ▼
      AST-DERIVED ARTIFACTS & TYPED RELATIONSHIPS
               │
       ┌───────┴────────────────────────┐
       ▼                                ▼
SNAPSHOT GRAPH DIFF             BATCH RUNTIME EVIDENCE (JSON/JSONL)
       │                                │
       ▼                                ▼
CHANGE IMPACT ENGINE             INCIDENT ENGINE
(Reverse Call-Chain Traversal)  (Error ➔ Symbol ➔ Change Correlation)
       │                                │
       ├──────────────┬─────────────────┘
       ▼              ▼
TEST IMPACT      CANDIDATE CAUSAL PATHS
(Direct/Transitive/Unknown)
       │              │
       └──────┬───────┘
              ▼
      UNIFIED EVIDENCE MODEL (PostgreSQL)
              │
              ▼
       API CONTRACTS (FastAPI REST)
              │
              ▼
       PRODUCT UI PROJECTION (Vanilla JS / DOM)
```

The frontend **must only be a projection of the evidence model**. If a repository has only one snapshot, Change Impact must truthfully state that two snapshots are required for comparison—it must not display blank zero-metrics without explanation.

---

## 2. End-to-End Data Pipeline Reality Matrix

| Capability | Actual Source | Backend Service | PostgreSQL Table/Model | API Endpoint | Frontend Consumer | Real Data Proven? | Concrete Evidence | Missing Link / Gap Identified |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Repository Ingestion** | Git clone / Local directory / ZIP archive | `git_provider.py`, `local_provider.py`, `archive_provider.py` | `repositories`, `projects` | `POST /repositories/connect-github`, `/onboard`, `/upload-archive` | `triggerGithubOnboarding`, `twin.js` | **PASS** | Clones real repos (`LAB-RECORD-SYSTEM`), extracts 40-char SHA and branch. | Shallow clone (`--depth 1`) only imports 1 commit initially. |
| **Discovery Brain** | Filesystem AST scanner | `discovery/engine.py`, `discovery/registry.py` | (Computed in-flight during synthesis) | `POST /discovery/inspect` | (Internal to twin builder) | **PASS** | Detects TS/JS, Python, Vite, Jest, PostgreSQL schemas. | Profile not exposed as independent UI view. |
| **Structural Twin** | Static AST Parsers (Tree-sitter/Babel/AST) | `analysis/engine.py`, `analyzers/` | `structural_artifacts`, `artifact_relationships`, `repository_snapshots` | `GET /repositories/{id}/overview`, `/components` | `loadOverviewData`, `loadComponentsView` | **PASS** | `LAB-RECORD-SYSTEM` yields 1,101 artifacts, 1,491 relationships in DB. | Overview was returning all 0s when `snapshot_id` omitted in query. *(Fixed)* |
| **Graph Projection** | PostgreSQL relational rows | `analysis/projection.py` | `structural_artifacts`, `artifact_relationships` | `GET /repositories/{id}/graph` | `renderGraphCanvas`, Cytoscape / Canvas | **PASS** | Multi-tier L1 (Macro), L2 (Modules), L3 (Symbols) generated from DB. | Single snapshot has no diff overlays. |
| **Snapshot Diff** | Two immutable snapshots in DB | `impact/diff_engine.py` | `repository_snapshots`, `structural_artifacts` | `GET /repositories/{id}/snapshot-diff` | `executeSnapshotDiff`, `#view-changes` | **PASS** | Verified 120 structural changes between Commit A (`815c0749`) and Commit B (`22432b8d`). | When only 1 snapshot exists, selectors have no second target to compare. |
| **Change Impact** | Reverse call-chain graph traversal | `impact/engine.py`, `impact/propagator.py` | `analysis_runs` | `POST /repositories/{id}/impact-analysis` | `executeChangeImpactAnalysis`, `#view-impact` | **PARTIAL (UI Wiring)** | Backend produces 29 direct entities, 57 propagation paths, depth 3. | `#view-impact` lacks snapshot selector dropdowns; reads hidden elements from `#view-changes`. |
| **Test Impact** | Backward BFS from changed symbols to `TEST_CASE` nodes | `testing/engine.py`, `testing/service.py` | `analysis_runs`, `structural_artifacts` | `POST /repositories/{id}/test-impact` | `executeTestImpactAnalysis`, `#view-tests` | **PASS** | Real analysis on `LAB-RECORD-SYSTEM`: 2 Affected, 3 Unaffected, 114 Unknown Coverage. | UI previously lacked explanation for why 114 tests are "Unknown" (missing test linkage). |
| **Risk & Guardrails** | Deterministic formula over change breadth & test coverage | `impact/risk_engine.py` | `analysis_runs` | `POST /repositories/{id}/risk-analysis` | `executeRiskAnalysis`, `#risk-analysis-content` | **PASS** | Computes 0–100 risk score and identifies architecture drifts. | Requires completed change impact run to evaluate. |
| **Runtime Evidence** | JSON/JSONL batch payloads | `runtime/service.py` | `runtime_events` | `POST /repositories/{id}/runtime-events/ingest`, `GET /events` | `loadRuntimeView`, `#view-runtime` | **PARTIAL (Batch Only)** | Batch ingest parses traces, spans, and errors into DB. | UI must not claim "LIVE TELEMETRY". Must state "Batch Evidence Available" or "No Runtime Source". |
| **Incident Intelligence** | Relational correlation of error events to symbols | `incidents/engine.py` | `incidents`, `runtime_events` | `POST /repositories/{id}/incidents/triage`, `GET /incidents` | `loadIncidentsView`, `investigateIncident` | **PASS** | Generates Candidate Causal Paths based on call paths and recent changes. | Must clearly label results as "Candidate Causal Path", never "Proven Root Cause". |
| **What-If Simulation** | Ephemeral in-memory virtual graph mutation | `simulation/engine.py` | (Zero DB mutation; in-memory copy) | `POST /repositories/{id}/simulation/evaluate` | `executeSimulation`, `#view-simulation` | **PASS** | Modifying `src.services.languageDetector` predicts 3 impacted nodes, 1 test, 0 DB changes. | Works end-to-end. |
| **Ask Twin / Intelligence** | Deterministic Twin Knowledge Engine | `twin_knowledge/service.py` | `structural_artifacts`, `artifact_relationships`, `incidents` | `POST /repositories/{id}/twin-knowledge/query` | `runSoftwareQuery`, `#view-ask` | **PASS (Deterministic)** | Zero LLM/hallucination; resolves architecture, impact, test claims, and components with explicit evidence provenance (`OBSERVED`, `DERIVED`, `INFERRED`, `SIMULATED`, `UNKNOWN`). | None. Fully grounded in PostgreSQL. |
| **Background Monitoring**| None | None | None | None | Disconnected | **HONESTLY LABELED** | Clearly disclosed in UI as "Automatic monitoring not connected". | No daemon or webhook listener configured. |
| **Transcription** | (None) | None | None | None | None | **NOT IMPLEMENTED** | No transcription capability exists or was designed. | Zero references found; confirmed clean. |

---

## 3. Ban on Silent Fallbacks & Fake States

The following anti-patterns are strictly audited and eliminated:

1. **`snap_latest` / `HEAD` hardcoded string fallbacks**:
   - *Audit*: `twin.js` previously used `(snap?.id || 'snap_latest')`.
   - *Remediation*: Completely eliminated from `twin.js` and `index.html`. If no snapshot is selected, state is explicitly `null` and views render `NOT_READY`.
2. **`repositories[0]` / `snapshots[0]` silent selection without user action**:
   - *Audit*: Opening a workspace previously left the snapshot dropdown unselected, which caused `get_repository_overview` to return zero counts.
   - *Remediation*: When opening a repository, automatically designate the latest active snapshot as the initial context, display its real commit SHA in the dropdown, and load its verified metrics. Pairwise comparisons require two distinct snapshots.
3. **Hardcoded or Static Counters & Additive Fallacy**:
   - All counters (`Changed`, `Unique Affected`, `Multi-Hop`, `Components`, `APIs`, `Tests`) are populated directly from the API response payload.
   - In `LAB-RECORD-SYSTEM`, 29 unique entities are affected; all 29 have depth-1 paths, and 7 of them ALSO have depth >= 2 paths. The UI previously added 29 + 7 to display 36, which is mathematically false. The UI and API now report `Unique Affected: 29`, `Multi-Hop: 7`, `Total Evidence Paths: 57`.
   - When no analysis has run, cards display an explicit uncomputed state (`—`), never `0` which falsely implies "verified zero".

---

## 4. GitHub Integration Provenance Chain

Verification using public repository `https://github.com/Sanjayshaa/LAB-RECORD-SYSTEM`:

1. **Acquisition & URL Hardening**:
   - Remote URL: `https://github.com/Sanjayshaa/LAB-RECORD-SYSTEM`
   - Hardening: Non-root URLs (`/blob/`, `/tree/`, `/issues/`, `/pull/`, `/commit/`, `/actions/`) are strictly rejected with 400: *"This is not a repository URL. Provide the root repository URL or import the project as a local folder/ZIP."*
   - Cloned Path: `data/cloned_repos/LAB-RECORD-SYSTEM_1dafa8df/`
   - Active Branch: `main`
   - Active Commit SHA: `d6678a6...` (latest remote HEAD)
2. **Deterministic Synthesis**:
   - Total Scanned Files: Verified in file inventory.
   - Synthesized Snapshot ID: `snap_d6678a6...`
   - Extracted Artifacts: Classes, functions, interfaces, modules, test suites.
   - Extracted Relationships: `CALLS`, `IMPORTS`, `TESTS`.
3. **Persisted Provenance**:
   - Database record created in `repositories` with `owner_id = user.id` and `environment = "USER"`.
   - Snapshot persisted in `repository_snapshots` with exact 40-character commit SHA.

---

## 5. Change Impact Ground-Truth Proof

The deterministic change impact engine was verified against the real commit transition in `LAB-RECORD-SYSTEM`:
- **BASE Commit**: `815c0749b9d120c72ab84223c3684613f91e76c7` (`snap_2dcb5aee2bc8f941`)
- **TARGET Commit**: `22432b8da6b4b07d93fbb06936bfd7fb00e36231` (`snap_9135acb3565f0037`)

### Verified Intelligence Results:
- **Total Changes**: `120` (27 added, 1 removed, 92 modified)
- **Unique Affected Entities**: `29`
- **Multi-Hop Entities**: `7`
- **Affected Components**: `24`
- **Affected APIs**: `3` (`POST /api/run`, `POST /api/submit`, `GET /api/status`)
- **Propagation Paths**: `57` causal paths across dependency graph (depth 1: 45, depth 2: 10, depth 3: 2)
- **Affected Tests**: `2` test suites

### Snapshot Comparison Contract:
- Comparing identical snapshots (`base_snapshot_id == target_snapshot_id`) returns `status="NOT_READY"` with message `"No change detected between selected snapshots."`.
- Single snapshot pairwise requests return `status="NOT_READY"`.
- Zero-valued successful completed state is strictly forbidden when no delta was computed.

---

## 6. Test Impact & Classification Proof

The engine categorizes tests deterministically into 4 disjoint sets:

1. **DIRECTLY_AFFECTED (2 tests)**:
   - `Language Detection Service Unit Test`
   - `Language Detection Service Integration Test`
   - *Provenance*: Explicit `TESTS` relationship connecting test file to `src/services/languageDetector.ts` which underwent AST modification.
2. **UNAFFECTED (3 tests)**:
   - `aggregateSubmissionMarks.test.ts`
   - `examWindow.test.ts`
   - `SPA Root Smoke Test`
   - *Provenance*: Reverse call-chain graph traversal reaches zero modified artifacts.
3. **UNKNOWN_COVERAGE (114 artifacts)**:
   - Symbols and modules for which no AST-level `TESTS` relationship or import link connects to any test suite in the repository.
   - *Significance*: Truthfully surfaces untested codebase surface area. Never converted to "UNAFFECTED".
4. **Physical Test Execution vs. Digital Twin**:
   - The test impact engine predicts which tests *need* to run.
   - It is completely distinct from running `npm test` or `pytest`. Passing physical tests does not mean untested code doesn't exist.

---

## 7. Runtime & Incident Intelligence Reality

### Runtime Telemetry & Privacy Boundary:
- **Current Capability**: Batch ingestion of JSON/JSONL events via `POST /repositories/{id}/runtime-events/ingest`.
- **Privacy Boundary**: Recursive scrubbing of customer PII (emails, phone numbers, credit card PAN/CVV, SSNs) and secrets (JWTs, OpenAI/GitHub/Stripe/AWS API keys, cookies, authorization headers) with adversarial test coverage (`test_runtime_privacy_boundary.py`).
- **Honest States**:
  - `NO_RUNTIME_SOURCE`: 0 events in database.
  - `BATCH_EVIDENCE_AVAILABLE`: $N$ events ingested from file.
  - `LIVE_STREAMING_UNAVAILABLE`: OpenTelemetry live agent not connected.

### Incident Intelligence:
- When an incident is investigated, the system queries runtime error events, maps them to structural artifacts, and finds recent changes along that artifact's dependency tree.
- Terminology strictly uses: **Candidate Causal Path** (confidence: HIGH / MEDIUM / LOW), never claiming "Definitive Root Cause Found" without formal proof.

---

## 8. Data Reality Scorecard

| Capability Area | Backend Engine | DB Schema | REST API | UI Rendering | End-to-End Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Repository Synthesis** | Real Git/AST | Real Postgres | Real FastAPI | Real DOM | **PASS** |
| **Structural Twin Graph** | Real AST | Real Postgres | Real FastAPI | Real DOM | **PASS** |
| **Snapshot Diff** | Real AST Diff | Real Postgres | Real FastAPI | Real DOM | **PASS** |
| **Change Impact** | Real BFS Graph | Real Postgres | Real FastAPI | Real DOM | **PASS (Remediated)** |
| **Test Impact** | Real Graph Link | Real Postgres | Real FastAPI | Real DOM | **PASS** |
| **Risk Engine** | Real Metrics | Real Postgres | Real FastAPI | Real DOM | **PASS** |
| **What-If Simulation** | Real In-Memory Twin | Zero Mutation | Real FastAPI | Real DOM | **PASS (Simulated Prov)** |
| **Runtime Evidence** | Batch Parser + Sanitizer | Real Postgres | Real FastAPI | Real DOM | **PASS (Batch + Scrubbed)** |
| **Incident Investigation** | Causal Heuristics | Real Postgres | Real FastAPI | Real DOM | **PASS (Candidate)** |
| **Ask Twin** | Deterministic Twin Knowledge | Real Postgres | Real FastAPI | Real DOM | **PASS (Evidence-Backed)** |
| **Background Monitoring**| None | None | None | Disconnected | **HONESTLY LABELED** |

---

## 9. Concrete Action Plan & Immediate Fixes

1. **Fix Change Impact UI Controls**:
   - Add snapshot comparison selectors (`Baseline Snapshot` and `Target Snapshot`) directly to the `#view-impact` view so the user can configure and run impact propagation without switching tabs.
   - If only 1 snapshot exists, render a helpful state explaining that snapshot comparison requires two commits, and provide a 1-click button to run What-If Simulation on the active snapshot instead.
2. **Uncomputed Metrics Display**:
   - Before analysis is run, display `—` instead of `0` to prevent confusion between "uncalculated" and "zero impact".
3. **Runtime & Incident Truthful Labels**:
   - Replace any remaining "Live" badges with "Batch Ingestion (OpenTelemetry Live Disconnected)".
   - Label incident findings as "Candidate Causal Path".
4. **Scope Ask Twin Truthfully**:
   - Clearly label the search interface as "Codebase & Artifact Search" rather than "AI Brain".
