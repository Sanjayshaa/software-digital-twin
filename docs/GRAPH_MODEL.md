# Typed Relationship & Graph Model

## 1. Typed Semantic Relationships

Relationships in the Digital Twin are never untyped edges. Every edge represents a well-defined software engineering relationship:

| Relationship Type | Description | Example |
| :--- | :--- | :--- |
| `CONTAINS` | Structural containment / namespace nesting | Module contains Class; Class contains Method |
| `IMPORTS` | Static symbol or package import | Python `from fastapi import FastAPI`; Java `import ...` |
| `EXPORTS` | Explicit module export | JavaScript `module.exports = { app }`; TS `export default` |
| `CALLS` | Statically observable function/method invocation | `create_order` calls `calculate_total` |
| `EXTENDS` | Class/struct inheritance | `class OrderService extends BaseService` |
| `IMPLEMENTS` | Interface implementation | `class OrderServiceImpl implements OrderService` |
| `REFERENCES` | Structural symbol reference | Method references table/field |
| `DEPENDS_ON` | General software component dependency | Service depends on another service |
| `EXPOSES` | Endpoint or capability exposure | Controller method exposes `POST /orders` |
| `CONSUMES` | Downstream client consumption | Service consumes an external API endpoint |
| `PERSISTS_TO` | Persistence interaction | Model persists to SQL table |
| `CONFIGURES` | Configuration entity wiring | YAML sets database URL |
| `TESTS` | Test suite assertion coverage | Test function `test_create_order` tests `create_order` |
| `PART_OF` | Component hierarchy membership | Method is part of Class |
| `INCLUDES` | File inclusion directive | C/C++ `#include "engine.hpp"` |
| `COPY_DEPENDS_ON` | Mainframe copybook dependency | COBOL program `COPY COPYBOOK.` |
| `USES` | General utility usage | Class uses helper function |

---

## 2. Graph Projection Architecture

```
PostgreSQL (Source of Truth)
        │
        ▼ (on-demand query via TwinQueryService)
TwinGraphProjection Service
        │
        ▼
NetworkX MultiDiGraph (In-Memory Analysis Engine)
```

- **Source of Truth**: PostgreSQL remains the canonical persistent source of truth.
- **Reproducibility**: The graph projection is constructed deterministically from `StructuralArtifact` nodes and `ArtifactRelationship` edges for any given snapshot.
- **Graph Topology**: Directed multi-graph (`MultiDiGraph`) supporting multiple typed edges between the same pair of nodes (e.g. `CALLS` and `REFERENCES`).
- **Graph Algorithms**: Enables cycle detection, ego-network extraction, shortest-path dependency traversal, and centrality calculation for future blast-radius and change-impact analysis.

---

## 3. Phase 3.X — Interactive Visualization Layer (Obsidian-Style Architecture View)

```
                    ┌─────────────────────┐
                    │   REAL REPOSITORY   │
                    └──────────┬──────────┘
                               ↓
                    ┌─────────────────────┐
                    │  DISCOVERY BRAIN    │
                    └──────────┬──────────┘
                               ↓
                    ┌─────────────────────┐
                    │  STRUCTURAL TWIN    │
                    └──────────┬──────────┘
                               ↓
             ┌─────────────────┴─────────────────┐
             ↓                                   ↓
     ┌───────────────┐                   ┌───────────────┐
     │ PROCESS TWIN  │                   │ EVIDENCE TWIN │
     └───────┬───────┘                   └───────┬───────┘
             └─────────────────┬─────────────────┘
                               ↓
                    ┌─────────────────────┐
                    │   GRAPH PROJECTION  │
                    │ (TwinGraphProjection)│
                    └──────────┬──────────┘
                               ↓
                 ┌───────────────────────────┐
                 │   INTERACTIVE TWIN VIEW   │
                 │                           │
                 │  📁 Repo Explorer         │
                 │  🕸 Architecture Graph    │
                 │  🔄 Process Graph         │
                 │  🔍 Dependency Explorer   │
                 │  🆚 Snapshot Diff          │
                 │  ⚠️ Drift Overlay         │
                 └───────────────────────────┘
```

### 3.1. Main Views
1. **Architecture Graph (Primary)**: Interactive node-edge graph powered by force-directed physics.
2. **Repository Explorer**: Dual-pane file-tree synchronized with graph node spotlighting.
3. **Process Graph**: Statically inferred and observed execution flows with evidence tags (`OBSERVED`, `STATICALLY_INFERRED`, `HEURISTIC`, `UNKNOWN`).
4. **Dependency Explorer**: Inward/outward dependency trees with hop counts.
5. **Snapshot Diff**: Side-by-side structural diffing with `+` ADDED, `-` REMOVED, and `~` MODIFIED markers.
6. **Architecture Drift Overlay**: Rule violation badges and red dashed edges linking to file/line evidence.

### 3.2. Progressive Hierarchical Disclosure
- **Level 1**: Packages and Major Modules
- **Level 2**: Classes, Services, API Endpoints, Databases, Tests
- **Level 3**: Methods, Functions, Constructors, Detailed Calls
- **Level 4**: Complete fine-grained source locations and AST evidence

### 3.3. REST API Contract
- `GET /repositories/{id}/graph`: Query parameters: `snapshot_id`, `level`, `depth`, `focus`, `artifact_type`, `relationship_type`, `diff_snapshot_id`, `impact_artifact_id`.
- `GET /repositories/{id}/process-graph`: Query parameters: `snapshot_id`.
- `GET /repositories/{id}/file-tree`: Query parameters: `snapshot_id`.
- `GET /repositories/{id}/graph/snapshots`: Lists available immutable snapshots with metrics.
