# TwinCore Frontend UX Known Limitations & Backend Dependencies

**Milestone:** Enterprise Frontend UX, Interaction Design & Product Finishing  
**Date:** 2026-10-19  
**Scope:** Strict Frontend-Only  

---

## 1. Overview

In adherence to the **Strict Frontend-Only Scope**, no backend endpoints, database schemas, or analysis algorithms were modified or fabricated. Where frontend capabilities intersect with backend constraints, the frontend has been designed to communicate real status honestly rather than manufacturing synthetic results.

This document records all established backend boundaries, architectural dependencies, and operational limitations for future engineering milestones.

---

## 2. Established Backend Constraints & Dependencies

### 2.1 What-If Scenario Mutation Support
- **Supported Mutation Archetypes:**
  The backend orchestrator (`/repositories/{id}/scenarios/orchestrate`) currently supports 5 mutation types:
  1. `MODIFY_SYMBOL`
  2. `ADD_DEPENDENCY`
  3. `REMOVE_DEPENDENCY`
  4. `MODIFY_API`
  5. `MODIFY_COMPONENT_RELATIONSHIP`
- **Frontend Handling:**
  The guided What-If workflow restricts archetype selection strictly to these supported types. Arbitrary free-form AST mutations outside this list are not suggested to prevent execution failures.

### 2.2 Historical Snapshot Reconstruction from Git
- **Backend Dependency:**
  When comparing commits in Change Impact that do not yet have an indexed Twin snapshot, the frontend triggers `/snapshots/reconstruct` with the target `commit_sha`.
- **Limitation:**
  Reconstruction succeeds only if the repository's `.git` tree is intact and readable on disk by the backend worker. If the commit has been pruned or rebased out of Git history, the frontend catches the `404/500` error and displays a clear explanation indicating that historical reconstruction requires a reachable Git commit object.

### 2.3 Runtime Telemetry & Live Incident Feeds
- **Honest Telemetry Policy:**
  Runtime Evidence and Incident response views display telemetry only when actual events have been posted to `/runtime/events` or `/incidents`.
- **Limitation:**
  If a repository has not been instrumented with the TwinCore runtime tracer, the Runtime Evidence view displays an honest empty state ("No runtime telemetry ingested yet for this snapshot") rather than simulating artificial traffic or CPU load curves.

### 2.4 True Deletion vs. Client Session Disconnection
- **Operational Reality:**
  The Safe Disconnect workflow clears all client-side session state (`selected_repo_id`, `selected_snapshot_id`, active in-memory graphs).
- **Backend Dependency:**
  The existing backend does not expose a destructive cascading DELETE route for entire knowledge graphs on disconnect. The frontend transparently discloses this to developers in `#modal-disconnect-repo`:
  > *"Disconnecting removes the repository from your active session. All generated knowledge graphs, historical snapshots, and AST caches remain safely preserved on disk."*

### 2.5 Single-Page Navigation & Browser Deep-Linking
- **Router Implementation:**
  TwinCore uses a hash-based client router (`#overview`, `#architecture`, `#impact`, `#simulation`, `#tests`, etc.).
- **Limitation:**
  If users enter an unrecognized hash (e.g. `#/unknown-tool`), `getInitialRequestedView()` gracefully falls back to `#overview` to prevent blank view states.

### 2.6 Pairwise Snapshot Diffing Prerequisites
- **Operational Reality:**
  Differential comparison in Changes and Change Impact requires two distinct Git snapshots (Baseline != Target).
- **Frontend Handling:**
  If a developer selects identical snapshots or a repository has only one snapshot, the UI clearly explains the prerequisite via `#impact-lifecycle-banner` and disables execution buttons to prevent meaningless duplicate computation.

### 2.7 Relationship Indexing & Model Readiness
- **Backend Dependency:**
  Macro architecture packages and topological transaction flows depend on call and import relationships extracted during ingestion.
- **Frontend Handling:**
  If symbols are cataloged but 0 relationships are indexed, Overview does not report false synchronization or hang on indefinite loading. It displays a clear "Structural Symbols Discovered, Relations Pending" status card with direct navigation to Run Technical Assessment.

