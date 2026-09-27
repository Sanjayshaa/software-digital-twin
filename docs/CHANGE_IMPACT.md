# Change Impact & Blast-Radius Analysis

## 1. Purpose
The Change Impact Engine deterministically evaluates the blast radius of code modifications between two immutable Digital Twin repository snapshots (Baseline Snapshot A and Target Snapshot B). It answers the core engineering question:
> *"If this software change is introduced between snapshot A and snapshot B, what existing software entities, APIs, processes, dependencies, and tests may be affected, and what evidence supports each impact path?"*

The engine is 100% deterministic, reproducible, explainable, snapshot-aware, and strictly backed by empirical Digital Twin evidence. It contains zero probabilistic LLM generation, heuristics without provenance, or artificial hallucinations.

---

## 2. Architecture
The Change Impact engine strictly consumes Digital Twin snapshots without modifying them:

```
REAL REPOSITORY
        ↓
DISCOVERY BRAIN
        ↓
PROJECT PROFILE
        ↓
ANALYZER RUNTIME
        ↓
STRUCTURAL DIGITAL TWIN (PostgreSQL)
        ↓
SNAPSHOT A + SNAPSHOT B (Immutable)
        ↓
SNAPSHOT DIFF (ChangeDetector)
        ↓
NORMALIZED CHANGE SET (ChangeSet, ChangeItem)
        ↓
CHANGED SYMBOLS / ARTIFACTS
        ↓
CENTRALIZED PROPAGATION RULES (RelationshipRuleRegistry)
        ↓
BOUNDED GRAPH PROPAGATOR (ImpactPropagator: BFS + Cycle Guard)
        ↓
CANONICAL IMPACT PATHS (ImpactPathFinder)
        ↓
CLASSIFIED IMPACT REPORT (ImpactSummary, Findings, Paths)
        ↓
PERSISTENCE (AnalysisRun, run_type="change_impact")
        ↓
FASTAPI REST API & OBSIDIAN-STYLE CANVAS PROJECTION
```

---

## 3. Input Contract
- **Repository ID**: Target project repository UUID.
- **Base Snapshot ID (A)**: Prior immutable snapshot baseline.
- **Target Snapshot ID (B)**: Subsequent immutable snapshot candidate.
- **Configuration (`ImpactConfig`)**:
  - `max_depth` (default: 5): Maximum relationship traversal depth.
  - `include_tests` (default: True): Propagate into test case artifacts.
  - `include_processes` (default: True): Propagate into processes and transitions.
  - `include_apis` (default: True): Propagate into exposed API endpoints.

---

## 4. Normalized Change Set
The engine compares the artifacts present in Snapshot A against Snapshot B using qualified names, source hashes, and signatures:
- `ChangeType`: `ADDED`, `REMOVED`, `MODIFIED`, `RENAMED`, `MOVED`.
- `ChangeItem`:
  - `artifact_id`, `symbol_name`, `qualified_name`, `artifact_type`.
  - `base_location`, `target_location`.
  - `base_hash`, `target_hash`.
  - `confidence`: Evidence confidence score (e.g., 0.95 for static AST diffs).
  - `evidence`: AST line offsets and comparison details.
  - `is_symbol_level`: Flag indicating whether symbol-level resolution was achieved.

---

## 5. Symbol-Level Detection & Fallback
For deep-supported languages (Python, Java, TypeScript, JavaScript):
- When a file is modified, the engine inspects functions, methods, and classes within the file.
- If a specific function/method body changes (e.g. `calculate_tax`), the modification is localized directly to the `METHOD` or `FUNCTION` symbol rather than reporting the whole file blindly.
- If AST parsing is unavailable or ambiguous, the engine gracefully falls back:
  `symbol-level unavailable → file-level change`
  with explicit provenance (`is_symbol_level=False, detection_method="file_level_fallback"`).

---

## 6. Relationship Propagation Rules
Relationship propagation semantics are centrally registered in `RelationshipRuleRegistry`:

| Relationship | Direction | Traversal Semantics | Default Edge Confidence |
| :--- | :--- | :--- | :--- |
| `CALLS` | REVERSE | Callee changed → Caller potentially affected | 0.85 |
| `IMPORTS` | REVERSE | Imported module changed → Importer potentially affected | 0.95 |
| `DEPENDS_ON` | REVERSE | Dependency changed → Dependent potentially affected | 0.90 |
| `CONSUMES` | REVERSE | Service provider changed → Consumer potentially affected | 0.85 |
| `TESTS` | REVERSE | Tested entity changed → Test suite potentially affected | 0.90 |
| `EXTENDS` | REVERSE | Base class changed → Derived class potentially affected | 0.95 |
| `IMPLEMENTS` | REVERSE | Interface changed → Implementation potentially affected | 0.95 |
| `EXPOSES` | FORWARD | Internal service changed → Public API route affected | 0.90 |
| `PARTICIPATES_IN` | FORWARD | Component/endpoint changed → Process workflow affected | 0.85 |
| `TRANSITIONS_TO` | FORWARD | Preceding process step changed → Downstream step affected | 0.90 |
| `CONTAINS` | NONE / CONTROLLED | Structural hierarchy navigation only (not blind blast-radius) | 1.00 |

---

## 7. Impact Levels
Impact levels quantify topological distance from the source modification:
- **Level 0 (CHANGED)**: The entity that was modified, added, or removed.
- **Level 1 (DIRECTLY_AFFECTED)**: Entities with a direct propagation relationship to a Level 0 changed entity (1 hop).
- **Level 2+ (INDIRECTLY_AFFECTED)**: Transitive dependencies reached via valid propagation paths (≥ 2 hops).

*Note: Impact distance represents topological graph distance, not operational severity.*

---

## 8. Confidence Model
Confidence quantifies empirical evidence strength, strictly separated from risk or severity:
- `1.00`: Direct observed AST relationship.
- `0.95`: Strong static structural relationship (e.g., explicit imports, class inheritance).
- `0.85`: Verified call-graph traversal / Framework-inferred dependency.
- Multi-hop path confidence is computed deterministically as the continuous product of edge confidences along the chain.

---

## 9. Evidence Traceability
Every `ImpactFinding` links directly to:
- Source and Target qualified names.
- Relationship type and propagation direction.
- Evidence references (file paths, line numbers, extraction mechanism).
- Detection method (`tree_sitter_ast_diff`, `static_call_graph`, `dependency_link`).

---

## 10. Canonical Path Calculation
Impact paths are first-class report entities. Rather than presenting isolated nodes, the engine preserves complete causal causal chains:
`PaymentService.calculate_tax` → `CALLS` → `OrderService.calculate_total` → `TESTS` → `test_calculate_total`
- Paths are canonicalized into `ImpactPath` objects.
- Deduplication prevents path explosion when multiple redundant routes reach the same target.
- Output sorting is 100% deterministic (sorted by depth ascending, then target name alphabetically).

---

## 11. Cycle Protection
Real software architectures contain cyclic dependencies (`A → B → C → A`).
- `ImpactPropagator` maintains an active path set for branch traversal.
- If a target node already exists within the current traversal branch, the branch terminates immediately.
- Traversal terminates safely without infinite loops or stack overflows.

---

## 12. Max Depth Bounding
Graph traversals are bounded by `ImpactConfig.max_depth` (default: 5).
- Prunes traversal beyond the designated depth boundary.
- Prevents runaway traversals across enterprise codebases.

---

## 13. Deleted Artifacts Handling
When a symbol or file is removed in Snapshot B (`change_type = REMOVED`):
- Snapshot B no longer contains the entity.
- The engine queries Snapshot A's historical relationships to determine what previously depended on the deleted entity.
- Deprecations and breaking deletions are accurately surfaced to callers and tests.

---

## 14. Snapshot Immutability
- Neither Snapshot A nor Snapshot B is ever modified during impact analysis.
- The analysis result is persisted independently as an `AnalysisRun` with `run_type="change_impact"`.
- Repeated executions against the same snapshots produce byte-for-byte identical output.

---

## 15. REST API & Endpoints
1. `POST /repositories/{id}/impact-analysis`
   - Request: `{"base_snapshot_id": "...", "target_snapshot_id": "...", "max_depth": 5}`
   - Returns full `ImpactResult` (Summary, Changes, Findings, Paths).
2. `GET /repositories/{id}/impact-analysis/{analysis_id}`
   - Retrieves previously computed impact analysis.
3. `GET /repositories/{id}/impact-analysis/{analysis_id}/graph`
   - Projects an impact-focused subgraph (Changed nodes, Direct/Indirect affected nodes, and connecting causal edges).

---

## 16. UI Workflow
Located in the **Changes** view of the Digital Twin application:
1. Select **Baseline Snapshot (A)** and **Target Snapshot (B)**.
2. Select **Max Traversal Depth** (1–10).
3. Click **⚡ Run Blast-Radius Analysis**.
4. View real-time **Impact Summary Metrics** (Changed, Direct, Indirect, Components, APIs, Processes, Tests).
5. Explore the interactive **Causal Impact Paths Tree**; clicking any node badge opens the Digital Twin Inspector.
6. Switch tabs to inspect **Evidence & Findings Table** or **Affected Categories Breakdown**.
7. Click **🌐 Project Impact Subgraph** to project the blast radius directly onto the Obsidian-style canvas.

---

## 17. Limitations & Scope Constraints
- **Dynamic Reflection / Dynamic Dispatch**: Python `getattr()` or Java dynamic proxies without static call targets cannot be resolved statically.
- **Runtime Telemetry**: Runtime traffic distribution and production invocation frequency are out of scope for Phase 4 (reserved for runtime telemetry integration).
- **Process Reconstruction**: Complex cross-service saga workflows are limited to explicit declared endpoints and transitions.

---

## 18. Future AI / Agent / RAG Integration
Phase 4 provides the deterministic foundation for future intelligence layers:
```
NATIVE IMPACT ENGINE (Phase 4)
        ↓
STRUCTURED EVIDENCE & FINDINGS (JSON / REST API)
        ↓
AGENTIC AI LAYER (Future)
        ↓
RAG OVER ARCHITECTURE DOCS & ADRs (Future)
        ↓
ENGINEERING EXPLANATION & RISK RECOMMENDATION (Future)
```
No LLM, RAG, or agent framework was introduced into the native engine.
