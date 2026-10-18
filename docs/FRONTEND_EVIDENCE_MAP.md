# Frontend Evidence Map: UI-to-Database Traceability Matrix

**Specification Date**: October 4, 2026  
**Auditor & Verification**: Antigravity Full-Stack Verification Subsystem  
**Scope**: Complete screen-by-screen traceability from rendered UI DOM elements to authoritative PostgreSQL queries and evidence IDs.  
**Zero-Fabrication Guarantee**: Zero displayed numbers, badges, or paths originate from hardcoded mocks, random values, or fake fallbacks.

---

## 1. UI State Machine Discipline

Every major analytical dashboard view (`Overview`, `Changes`, `Impact`, `Tests`, `Risk`, `Runtime`, `Incidents`, `Simulation`, `Ask Twin`) strictly distinguishes and renders 5 distinct UI states:

| State | Visual Representation | Condition |
|---|---|---|
| `LOADING` | Pulsing skeleton spinner with message | Request in flight over REST API. |
| `EMPTY` | Informational empty state card with action prompt | Repository connected, but zero rows exist (e.g. 0 incidents). |
| `NOT_READY` | Amber warning notice with technical rationale | Analysis requirements unmet (e.g., single snapshot available, identical snapshots selected). |
| `ERROR` | Red error container with server error code & message | HTTP 4xx or 5xx returned from backend. |
| `COMPLETED` | Verified metrics grid with provenance badges and path tables | Successful analysis executed on distinct snapshots. |

> **Critical Rule**: The UI never displays `0 Changed` or `0 Blast Radius` when an analysis was never executed. It displays `NOT_READY` or `EMPTY`.

---

## 2. Screen-by-Screen Metric Traceability Matrix

### View 1: Overview (`#view-overview`)
| UI Element | Rendered Metric | API Endpoint | Response JSON Field | Backend Service | Authoritative Database Query | Provenance |
|---|---|---|---|---|---|---|
| `#ov-artifacts` | Topology Components | `GET /repositories/{id}/overview?snapshot_id={sid}` | `metrics.artifacts` | `twin_query_service` | `SELECT count(*) FROM structural_artifacts WHERE snapshot_id = :sid` | `OBSERVED` |
| `#ov-dependencies` | Dependency Edges | `GET /repositories/{id}/overview?snapshot_id={sid}` | `metrics.relationships` | `twin_query_service` | `SELECT count(*) FROM artifact_relationships WHERE snapshot_id = :sid` | `OBSERVED` |
| `#ov-tests` | Automated Tests | `GET /repositories/{id}/overview?snapshot_id={sid}` | `metrics.tests` | `twin_query_service` | `SELECT count(*) FROM structural_artifacts WHERE snapshot_id = :sid AND artifact_type IN ('TEST_CASE', 'TEST_SUITE')` | `OBSERVED` |
| `#ov-apis` | API Surface | `GET /repositories/{id}/overview?snapshot_id={sid}` | `metrics.apis` | `twin_query_service` | `SELECT count(*) FROM structural_artifacts WHERE snapshot_id = :sid AND artifact_type = 'API_ENDPOINT'` | `OBSERVED` |
| `#ov-violations` | Architecture Violations | `GET /repositories/{id}/overview?snapshot_id={sid}` | `metrics.violations` | `drift_detector` | `SELECT count(*) FROM architecture_drifts WHERE snapshot_id = :sid` | `DERIVED` |
| `#ov-commit` | Commit SHA | `GET /repositories/{id}/overview?snapshot_id={sid}` | `snapshot.commit_hash` | `acquisition.git_provider` | `SELECT commit_hash FROM repository_snapshots WHERE id = :sid` | `OBSERVED` |

### View 2: Architecture & Dependencies (`#view-architecture`, `#view-dependencies`)
| UI Element | Rendered Metric | API Endpoint | Response JSON Field | Backend Service | Authoritative Database Query | Provenance |
|---|---|---|---|---|---|---|
| `#graph-node-count` | Total Graph Nodes | `GET /repositories/{id}/graph?snapshot_id={sid}&level=2` | `summary.total_nodes` | `graph_projection_service` | Serialized node array from `structural_artifacts` | `OBSERVED` |
| `#graph-edge-count` | Total Graph Edges | `GET /repositories/{id}/graph?snapshot_id={sid}&level=2` | `summary.total_edges` | `graph_projection_service` | Serialized edge array from `artifact_relationships` | `OBSERVED` |

### View 3: Components Catalog (`#view-components`)
| UI Element | Rendered Metric | API Endpoint | Response JSON Field | Backend Service | Authoritative Database Query | Provenance |
|---|---|---|---|---|---|---|
| `#components-table` | Architectural Components Table | `GET /repositories/{id}/components?snapshot_id={sid}` | `components[]` (`name`, `type`, `location`, `confidence`) | `graph.py:get_repository_components` | `SELECT * FROM structural_artifacts WHERE snapshot_id = :sid ORDER BY artifact_type, name` | `OBSERVED` |

### View 4: Changes / Snapshot Diff (`#view-changes`)
| UI Element | Rendered Metric | API Endpoint | Response JSON Field | Backend Service | Authoritative Database Query | Provenance |
|---|---|---|---|---|---|---|
| `#diff-table-body` | Structural Changes | `GET /repositories/{id}/snapshot-diff?base_snapshot_id={base}&target_snapshot_id={target}` | `changes[]` (`symbol_name`, `change_type`, `location`) | `change_detector` | Pairwise comparison between `base_snapshot` and `target_snapshot` artifacts | `DERIVED` |
| `#diff-added-count` | Added Symbols | `GET /repositories/{id}/snapshot-diff` | `summary.added` | `change_detector` | Count of target artifacts absent in base | `DERIVED` |
| `#diff-removed-count` | Removed Symbols | `GET /repositories/{id}/snapshot-diff` | `summary.removed` | `change_detector` | Count of base artifacts absent in target | `DERIVED` |
| `#diff-modified-count` | Modified Symbols | `GET /repositories/{id}/snapshot-diff` | `summary.modified` | `change_detector` | Count of matching qualified names with differing `source_hash` | `DERIVED` |

### View 5: Change Impact & Blast Radius (`#view-impact`)
| UI Element | Rendered Metric | API Endpoint | Response JSON Field | Backend Service | Authoritative Database Query | Provenance |
|---|---|---|---|---|---|---|
| `#impact-changed-count` | Changed Artifacts | `POST /repositories/{id}/impact-analysis` | `summary.changed` | `change_impact_service` | Count of changed symbols in `ChangeSet` | `OBSERVED` |
| `#impact-unique-count` | Unique Affected Entities | `POST /repositories/{id}/impact-analysis` | `summary.unique_affected` | `change_impact_service` | Set size of `directly_affected ∪ indirectly_affected` | `DERIVED` |
| `#impact-multihop-count` | Multi-Hop Affected | `POST /repositories/{id}/impact-analysis` | `summary.multi_hop_affected` | `change_impact_service` | Count of entities reachable at depth $\ge 2$ | `DERIVED` |
| `#impact-paths-count` | Evidence Paths | `POST /repositories/{id}/impact-analysis` | `summary.total_evidence_paths` | `change_impact_service` | Count of causal paths constructed by BFS traversal | `DERIVED` |
| `#impact-depth1-count` | Depth-1 Paths | `POST /repositories/{id}/impact-analysis` | `summary.depth_1_paths` | `change_impact_service` | Paths with `depth == 1` | `DERIVED` |
| `#impact-depth2-count` | Depth-2 Paths | `POST /repositories/{id}/impact-analysis` | `summary.depth_2_paths` | `change_impact_service` | Paths with `depth == 2` | `DERIVED` |
| `#impact-depth3-count` | Depth-3 Paths | `POST /repositories/{id}/impact-analysis` | `summary.depth_3_paths` | `change_impact_service` | Paths with `depth == 3` | `DERIVED` |
| `#impact-paths-table` | Causal Propagation Tree | `POST /repositories/{id}/impact-analysis` | `paths[]` (`root_symbol`, `target_symbol`, `nodes`, `relationships`, `depth`) | `change_impact_service` | Traversals across `artifact_relationships` | `DERIVED` |

### View 6: Test Impact Intelligence (`#view-tests`)
| UI Element | Rendered Metric | API Endpoint | Response JSON Field | Backend Service | Authoritative Database Query | Provenance |
|---|---|---|---|---|---|---|
| `#test-affected-count` | Affected Tests | `POST /repositories/{id}/test-impact` | `summary.affected_tests` | `test_impact_engine` | Tests reachable via `TESTS` edges from changed entities | `DERIVED` |
| `#test-unaffected-count` | Unaffected Tests | `POST /repositories/{id}/test-impact` | `summary.unaffected_tests` | `test_impact_engine` | Mapped tests with zero intersection to change blast radius | `DERIVED` |
| `#test-unknown-count` | Unknown Coverage | `POST /repositories/{id}/test-impact` | `summary.unknown_coverage_count` | `test_impact_engine` | Changed entities with no incoming/outgoing test relationships | `UNKNOWN` |
| `#test-claim-badge` | Coverage Claim | `POST /repositories/{id}/test-impact` | `evaluation.coverage_claim` | `test_impact_engine` | Strict 5-state claim evaluation | `DERIVED` / `UNKNOWN` |

### View 7: Risk & Architecture Guardrails (`#view-risk`)
| UI Element | Rendered Metric | API Endpoint | Response JSON Field | Backend Service | Authoritative Database Query | Provenance |
|---|---|---|---|---|---|---|
| `#risk-composite-score` | Composite Risk (0-100) | `POST /repositories/{id}/risk-analysis` | `composite_score` | `risk_intelligence_engine` | Deterministic formula from blast radius, test exposure, and drift | `DERIVED` |
| `#risk-category-badge` | Risk Category | `POST /repositories/{id}/risk-analysis` | `overall_category` | `risk_intelligence_engine` | `LOW`, `MEDIUM`, `HIGH`, `CRITICAL` | `DERIVED` |
| `#risk-findings-table` | Risk Findings | `POST /repositories/{id}/risk-analysis` | `findings[]` | `risk_intelligence_engine` | Factor breakdowns with evidence explanations | `DERIVED` |

### View 8: Runtime Evidence (`#view-runtime`)
| UI Element | Rendered Metric | API Endpoint | Response JSON Field | Backend Service | Authoritative Database Query | Provenance |
|---|---|---|---|---|---|---|
| `#runtime-events-table` | Batch Ingested Events | `GET /repositories/{id}/runtime-events` | `events[]` (`service`, `route`, `method`, `status`, `latency_ms`) | `runtime_evidence_service` | `SELECT * FROM runtime_events WHERE repository_id = :id ORDER BY timestamp DESC` | `OBSERVED` |
| `#runtime-mode-badge` | Ingestion Mode | `GET /repositories/{id}/twin-knowledge/runtime-evidence` | `ingestion_mode` | `twin_knowledge_service` | Truthful disclosure: `"BATCH_JSON_JSONL"`, `live_streaming: false` | `OBSERVED` |

### View 9: Incidents & Triage (`#view-incidents`)
| UI Element | Rendered Metric | API Endpoint | Response JSON Field | Backend Service | Authoritative Database Query | Provenance |
|---|---|---|---|---|---|---|
| `#incidents-list` | Open Incidents | `GET /repositories/{id}/incidents` | `incidents[]` | `incident_service` | `SELECT * FROM incidents WHERE repository_id = :id` | `OBSERVED` |
| `#incident-causal-path` | Candidate Causal Path | `POST /repositories/{id}/incidents/{inc_id}/investigate` | `candidate_paths[]` | `incident_investigator` | Correlation between runtime error stacks, changed symbols, and test coverage | `DERIVED` |

### View 10: Virtual Simulation Workspace (`#view-simulation`)
| UI Element | Rendered Metric | API Endpoint | Response JSON Field | Backend Service | Authoritative Database Query | Provenance |
|---|---|---|---|---|---|---|
| `#sim-results-panel` | Simulated Blast Radius | `POST /repositories/{id}/simulate` | `summary` & `findings` | `scenario_simulation_engine` | In-memory graph cloning and mutation; 0 writes to production database | `SIMULATED` |

### View 11: Ask Twin Intelligence Console (`#view-ask`)
| UI Element | Rendered Metric | API Endpoint | Response JSON Field | Backend Service | Authoritative Database Query | Provenance |
|---|---|---|---|---|---|---|
| `#ask-results-container` | Grounded Answer & Evidence | `POST /repositories/{id}/twin-knowledge/query` | `answer`, `evidence_ids[]`, `grounded_entities[]`, `provenance` | `twin_knowledge_service` | Deterministic resolution against authoritative PostgreSQL tables; zero LLM hallucination | Dynamic (`OBSERVED`, `DERIVED`, `UNKNOWN`) |
