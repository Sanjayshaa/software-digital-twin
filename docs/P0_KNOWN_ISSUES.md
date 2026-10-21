# TwinCore P0 Known Issues & Defect Tracking Log

**Project:** TwinCore — AI-Powered Software Digital Twin for Change Impact Analysis  
**Milestone:** P0 Core Workflow Reliability, Correctness & Verification  
**Last Updated:** October 19, 2026  
**Status:** ALL P0 BLOCKERS RESOLVED & VERIFIED  

---

## Defect Matrix Summary

| Defect ID | Workflow Area | Severity | Initial Status | Resolution Status | Verified By |
|---|---|:---:|:---:|:---:|---|
| **ISSUE-01** | What-If Simulation Target Resolution | P0 - Blocker | Open | **RESOLVED** | Unit & Integration Suite (`test_p0_workflow_reliability.py`) |
| **ISSUE-02** | Test Impact Commit SHA Snapshot Resolution | P0 - Blocker | Open | **RESOLVED** | Test Impact Regression Suite |
| **ISSUE-03** | Scenario Report Generation & Persistence | P0 - Blocker | Open | **RESOLVED** | Report Serialization & Persistence Suite |
| **ISSUE-04** | Architecture Graph Inbound Degree Projection | P0 - Blocker | Open | **RESOLVED** | Graph API & UI Inspector Verification |
| **LIMIT-01** | Natural Language Ambiguous Symbol Disambiguation | P2 - Limitation | Known | **BY DESIGN** | Interactive Candidate Resolution Modal |
| **LIMIT-02** | Test Execution Runtime Timing Dependency | P2 - Limitation | Known | **BY DESIGN** | Static Test Metadata Fallback |

---

## Detailed Issue Tracking

### ISSUE-01: What-If Target Resolution & False Zero-Impact Rendering
- **Severity:** P0 (Critical Core Functional Blocker)
- **Component:** `backend/app/services/simulation/validator.py`, `backend/app/api/simulation.py`, `backend/app/static/twin.js`
- **Symptom:** Entering `"What happens if we remove studentgamificationservice.ts?"` rendered `"undefined"` in form inputs and produced a false successful result showing 0 mutations, 0 affected nodes, 0 findings, and 0/100 risk score.
- **Root Cause:**
  1. The validator in `validator.py` strictly checked exact string matches against `by_name` and `by_qual`. Raw inputs containing file extensions (`.ts`, `.js`, etc.) or lowercase casings failed to match `StudentGamificationService` located at `src/services/studentgamificationservice.ts`.
  2. Frontend `twin.js` transmitted `target_override` and `mutation_type_override` while `NaturalLanguageScenarioRequest` expected `explicit_target` and `explicit_type`.
  3. Frontend `handleScenarioPlanResult()` coerced `plan.target_entities[0]` to `"undefined"`.
  4. Frontend unwrapped `data.proposed_changes` directly from root response instead of `data.simulation.proposed_changes`. JavaScript evaluated `undefined` to `0`, deceptively rendering a successful zero-impact simulation.
- **Fix:**
  - Extended `resolve_entity()` with regex extension stripping, alphanumeric normalization, and location stem search.
  - Normalized payload parameters in `NaturalLanguageScenarioRequest`.
  - Added safe extraction in `twin.js`, explicitly displaying resolution failure cards with suggested candidates instead of false zero metrics.
- **Verification:** `backend/tests/test_p0_workflow_reliability.py::test_whatif_target_resolution_with_extension`.

---

### ISSUE-02: Test Impact Snapshot Resolution & False Pass on Failure
- **Severity:** P0 (Critical Core Functional Blocker)
- **Component:** `backend/app/api/testing.py`, `backend/app/services/testing/service.py`, `backend/app/static/twin.js`
- **Symptom:** UI displays 3 tests in catalog, but analysis produces "Analysis error: Test impact computation failed" while metric cards remain initialized at 0, mimicking a clean zero-impact pass.
- **Root Cause:**
  1. UI commit selector passed 40-character Git commit SHAs into `POST /repositories/{id}/test-impact`. Backend queried `RepositorySnapshot.id == req.target_snapshot_id`. Since `id` is a UUID, the query returned `None`, triggering an HTTP 404 / exception.
  2. In `backend/app/services/testing/service.py`, `AnalysisRun` insertion used `target_snapshot_id` instead of canonical UUID, causing referential integrity issues.
  3. Frontend catch block left metric cards at `0` rather than indicating an error state.
- **Fix:**
  - Integrated `_ensure_snapshot` in `api/testing.py` to resolve both UUIDs and Git commit hashes.
  - Updated `service.py` to query `or_(RepositorySnapshot.id == id, RepositorySnapshot.commit_hash == id)`.
  - Updated `AnalysisRun` insertion to store `canonical_target_id`.
  - Updated `twin.js` catch block to reset metric cards to `—` (dash) and display an explicit error alert with a retry button.
- **Verification:** `backend/tests/test_p0_workflow_reliability.py::test_test_impact_with_commit_sha_and_snapshot_resolution`.

---

### ISSUE-03: Scenario Report Generation 404 & Key Divergence
- **Severity:** P0 (Critical Core Functional Blocker)
- **Component:** `backend/app/services/simulation/orchestration.py`, `backend/app/api/simulation.py`, `backend/app/static/twin.js`
- **Symptom:** Clicking "Download Engineering Report" failed with HTTP 404 and toast error: "Engineering report could not be generated for this scenario".
- **Root Cause:**
  1. `MultiAgentScenarioOrchestrator.orchestrate_scenario()` synthesized report markdown in memory but never inserted the `Scenario` and `ScenarioResult` rows into PostgreSQL with the generated `scenario_id`.
  2. `GET /repositories/{id}/scenarios/{scenario_id}/report` queried the database for the scenario, returning 404.
  3. Frontend looked for `report_markdown` while `ScenarioEngineeringReport` serialized under `markdown_content`.
- **Fix:**
  - Added atomic database persistence of `Scenario` and `ScenarioResult` within `orchestrate_scenario()`.
  - Added secret sanitization and dual key serialization (`markdown_content` and `report_markdown`).
  - Added fallback on-demand synthesis in `api/simulation.py`.
  - Updated `downloadScenarioReport` in `twin.js` to inspect both keys with API fallback.
- **Verification:** `backend/tests/test_p0_workflow_reliability.py::test_whatif_orchestration_end_to_end_and_persistence`.

---

### ISSUE-04: Architecture Graph Inbound Caller Ambiguity
- **Severity:** P0 (User Comprehension & Correctness)
- **Component:** `backend/app/static/twin.js`
- **Symptom:** Architecture graph displays 296 nodes and 448 connections. Selecting top-level services or components reports "No inbound callers".
- **Root Cause:**
  1. The inspector panel calculated incoming callers strictly from `state.edges.filter(e => e.target === node.id)`. At Level 2 (services/components), calls originating from granular functions/methods (Levels 3 and 4) are collapsed, so `incoming.length` in the current view projection evaluates to 0 even though `node.in_degree > 0` in the database.
  2. Top-level routers and entry points legitimately receive external HTTP traffic (in-degree 0, out-degree > 0). The UI displayed a generic "No inbound callers" message without clarifying that the node is a system entry point.
- **Fix:**
  - Updated `inspectNode()` in `twin.js` to distinguish:
    - Visible callers: Interactive navigation chips.
    - Collapsed granular callers (`node.in_degree > 0`): Explains that callers exist at deeper zoom levels (`${inDeg} callers at granular level`).
    - Root entry points (`in_degree === 0 && out_degree > 0`): Badged as `Root Entry Point / Top-level Component`.
    - Truly isolated entities (`in_degree === 0 && out_degree === 0`): Badged as `No inbound callers (Isolated entity)`.
- **Verification:** `backend/tests/test_p0_workflow_reliability.py::test_architecture_graph_inbound_outbound_metrics`.

---

## Known Product Limitations (Non-Blocking / By Design)

### LIMIT-01: Disambiguation of Highly Shared Symbol Names
- **Description:** When a user queries a short or generic entity name (e.g., `Config`, `Handler`) that appears in dozens of files without specifying a module or path, deterministic parsing cannot select a single target with 100% confidence.
- **Behavior:** The system returns `status: "AMBIGUOUS"` and renders candidate options with module locations for user selection.
- **Classification:** Working as intended; prevents hallucinated or arbitrary mutations.

### LIMIT-02: Test Execution Duration Estimation
- **Description:** When dynamic test execution profiling traces are not ingested for a repository, execution duration falls back to static test metadata defaults (0 ms / tier baseline).
- **Classification:** Working as intended; static analysis guarantees safety without requiring unsandboxed test execution.
