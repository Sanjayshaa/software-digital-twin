# FRONTEND DATA PROVENANCE: Screen-by-Screen API Trace

**Date**: October 4, 2026  
**Audited System**: TwinCore Web Client (`backend/app/static/twin.js`)  
**Core Invariant**: Every number, badge, table row, and graph node rendered on screen must trace directly to an authenticated REST API response field. No client fabrication.

---

## 1. Screen-by-Screen API Provenance Matrix

### View 1: Overview (`#view-overview`)
- **API Endpoint**: `GET /repositories/{id}/overview?snapshot_id={snap_id}`
- **Originating Service**: `app.services.analysis.engine` via `backend/app/api/graph.py`
- **Rendered Fields & DB Provenance**:
  - `Topology Components`: `res.metrics.artifacts` ➔ Count of `StructuralArtifact` rows for snapshot.
  - `APIs Registered`: `res.metrics.apis` ➔ Filtered `StructuralArtifact` with `artifact_type == "API_ENDPOINT"`.
  - `Dependencies`: `res.metrics.relationships` ➔ Count of `ArtifactRelationship` rows for snapshot.
  - `Verification Tests`: `res.metrics.tests` ➔ Filtered `StructuralArtifact` with `artifact_type in ("TEST_CASE", "TEST_SUITE")`.
  - `Architecture Conformance`: `res.metrics.violations` ➔ Count of `ArchitectureDrift` rows with `status == "DETECTED"`.
  - `Macro Packages`: `res.architecture_packages` ➔ Top-level module groupings computed from artifact qualified paths.

### View 2: Architecture (`#view-architecture`) & Dependencies (`#view-dependencies`)
- **API Endpoint**: `GET /repositories/{id}/graph?snapshot_id={snap_id}&level={1|2|3}&depth={k}`
- **Originating Service**: `app.services.analysis.projection.twin_graph_projection`
- **Rendered Fields & DB Provenance**:
  - `Nodes`: `res.nodes` ➔ Serialized `StructuralArtifact` entries with AST type, language, location, and confidence.
  - `Edges`: `res.edges` ➔ Serialized `ArtifactRelationship` entries with source, target, relationship type (`CALLS`, `IMPORTS`, `TESTS`, etc.).
  - `Legend & Metrics`: Node and edge counters derived strictly from the returned `res.summary.total_nodes` and `res.summary.total_edges`.

### View 3: Components (`#view-components`)
- **API Endpoint**: `GET /repositories/{id}/components?snapshot_id={snap_id}`
- **Originating Service**: `backend/app/api/graph.py:get_repository_components`
- **Rendered Fields & DB Provenance**:
  - Table rows: `res.components[]` ➔ Direct dump of `StructuralArtifact` rows containing `name`, `artifact_type`, `qualified_name`, `language`, and `location`.

### View 4: Changes (`#view-changes`)
- **API Endpoint**: `GET /repositories/{id}/snapshot-diff?base_snapshot_id={base}&target_snapshot_id={target}`
- **Originating Service**: `app.services.impact.diff_engine.snapshot_diff_engine`
- **Rendered Fields & DB Provenance**:
  - `Diff Table`: `res.changes[]` ➔ Pairwise delta comparison between base and target snapshots:
    - Added: Present in target snapshot, absent in base snapshot.
    - Removed: Present in base snapshot, absent in target snapshot.
    - Modified: Matching qualified name but differing AST `source_hash` or lines.
  - `Breaking Drifts`: `res.drifts[]` ➔ Signatures with altered public interfaces or contract violations.

### View 5: Change Impact (`#view-impact`)
- **API Endpoint**: `POST /repositories/{id}/impact-analysis`
- **Payload**: `{ "base_snapshot_id": base, "target_snapshot_id": target, "max_depth": 5 }`
- **Originating Service**: `app.services.impact.engine.change_impact_engine`
- **Rendered Fields & DB Provenance**:
  - `Changed`: `res.summary.changed` ➔ Direct count of changed artifacts.
  - `Direct`: `res.summary.directly_affected` ➔ Immediate 1-hop dependencies along incoming call/import edges.
  - `Indirect`: `res.summary.indirectly_affected` ➔ Multi-hop ($k \ge 2$) dependencies.
  - `Components`: `res.summary.affected_components`.
  - `APIs`: `res.summary.affected_apis` ➔ API endpoints reachable from modified code.
  - `Tests`: `res.summary.affected_tests` ➔ Test suites connected via `TESTS` edges.
  - `Causal Propagation Tree`: `res.propagation_paths[]` ➔ Breadth-first traversal paths formatted as:
    `[Changed Artifact] ──(RELATION)──► [Node A] ──(RELATION)──► [Final Node]`.

### View 6: Tests (`#view-tests`)
- **API Endpoint**: `POST /repositories/{id}/test-impact`
- **Payload**: `{ "base_snapshot_id": base, "target_snapshot_id": target }`
- **Originating Service**: `app.services.testing.engine.test_impact_engine`
- **Rendered Fields & DB Provenance**:
  - `Affected Tests`: `res.test_impact.affected_tests[]` with classification (`DIRECT` vs `TRANSITIVE`).
  - `Unaffected Tests`: `res.test_impact.unaffected_tests[]` with safety justification.
  - `Unknown Coverage`: `res.test_impact.unknown_coverage_count` ➔ Artifacts with no reverse call chain to tests.

### View 7: Risk & Guardrails
- **API Endpoint**: `POST /repositories/{id}/risk-analysis`
- **Originating Service**: `app.services.impact.risk_engine`
- **Rendered Fields & DB Provenance**:
  - `Risk Score`: `res.risk_score` (0–100) computed deterministically from change blast radius, test exposure ratio, and architectural boundary violations.
  - `Violations`: `res.violations[]` ➔ Conformance checks against architectural tiers.

### View 8: Incidents (`#view-incidents`)
- **API Endpoint**: `GET /repositories/{id}/incidents` and `POST /repositories/{id}/incidents/{inc_id}/investigate`
- **Originating Service**: `app.services.incidents.engine`
- **Rendered Fields & DB Provenance**:
  - Incident list: `incidents` table in PostgreSQL.
  - Candidate Causal Paths: Correlated runtime errors matched by stack trace symbol to recently modified structural artifacts and test coverage.

### View 9: Runtime Evidence (`#view-runtime`)
- **API Endpoint**: `GET /repositories/{id}/runtime-events`
- **Originating Service**: `app.services.runtime.service`
- **Rendered Fields & DB Provenance**:
  - Ingested Events: `runtime_events` table in PostgreSQL (populated via batch JSON/JSONL upload).

### View 10: What-If Simulation (`#view-simulation`)
- **API Endpoint**: `POST /repositories/{id}/simulation/evaluate`
- **Payload**: `{ "snapshot_id": snap, "proposed_changes": [{ "file_path": ..., "mutation_type": ... }] }`
- **Originating Service**: `app.services.simulation.engine`
- **Rendered Fields & DB Provenance**:
  - In-memory virtual snapshot mutation predicting blast radius and affected tests with zero database or Git mutation.

---

## 2. Identified Frontend Disconnections & Resolutions

| UI Screen | Symptom | Ground Truth Cause | Resolution |
| :--- | :--- | :--- | :--- |
| **Change Impact (`#view-impact`)** | Displays all 0s when clicking "Execute Impact Propagation" | Selectors `diff-base-select` and `diff-target-select` were located on `#view-changes`, invisible from `#view-impact`. | Add Base and Target snapshot selectors directly to `#view-impact`. |
| **Overview Screen** | Showed 0 breaking changes and unselected snapshot | Overview endpoint returned 0s when query parameter `snapshot_id` was omitted. | Default to active snapshot in endpoint and auto-select active snapshot in client. |
| **Single Snapshot Repos** | User clicking Impact has no second snapshot to compare | Single snapshot repositories cannot produce pairwise git diffs without a second commit. | Render explicit truthful empty state with 1-click What-If simulation fallback. |
