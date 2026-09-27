# Process Twin Architecture & Specification

## 1. Core Objective

The **Process Twin** extends the Software Digital Twin from static topology ("what components exist") to workflow semantics ("how does the software execute meaningful operations").

A **Process** represents a deterministic or inferred sequence of software steps executing a purposeful operation (e.g., checkout, authentication, order dispatch, data ingestion).

```
   [API Endpoint / Handler / Entrypoint]
                   │
                   ▼ (CALLS / TRANSITIONS_TO)
          [Service Routine]
                   │
                   ▼ (CALLS / DEPENDS_ON)
       [Data Repository / Worker]
                   │
                   ▼ (PERSISTS_TO)
          [Database / Storage]
```

## 2. Process Discovery Engine

Process discovery is completely **deterministic**, driven by static AST structural artifacts and invocation relationships:

1. **Entrypoint Identification**:
   - Explicit API endpoints (`API_ENDPOINT`, `@GetMapping`, `@PostMapping`, FastAPI routes).
   - Controller or Handler methods (`*Controller`, `*Handler`, `*Router`, `*Dispatch`).
   - In-degree 0 root functions and public service methods.
2. **Topological Call Chain Traversal**:
   - Breadth-first traversal up to depth 4 following `CALLS`, `DEPENDS_ON`, `EXPOSES`, `CONSUMES`, and `PERSISTS_TO` relationships.
   - Guarded against cyclic dependencies using visited-node sets and maximum step limits.
3. **Traceable Evidence Attribution**:
   - Every process step captures `source_file`, `line_number`, and `operation`.
   - Never represent an inferred process as directly observed. Every process step and transition records an explicit `ProcessEvidenceStatus`:
     - `OBSERVED`: Directly verified via runtime trace/span execution.
     - `DERIVED`: Topologically computed from verified structural invocations.
     - `INFERRED`: Derived from static AST inspection and call hierarchy.
     - `UNKNOWN`: Unresolved link or dynamic dispatch target.

## 3. Data Model

- **`ProcessDefinition`**:
  - `id`: Stable deterministic UUID (`uuid5` seeded by repo, snapshot, entrypoint).
  - `repository_id`, `snapshot_id`: Snapshot immutability binding.
  - `name`: Workflow title (e.g. `Process: dispatch_order`).
  - `process_type`: `api_workflow`, `service_workflow`, or `batch_workflow`.
  - `metadata_payload`: Contains evidence status, entrypoint ID, and confidence factor.
- **`ProcessStep`**:
  - `id`, `process_id`, `step_order`: Explicit sequence index (`UNKNOWN_ORDER` if non-deterministic).
  - `component_artifact_id`: Link to concrete `StructuralArtifact`.
  - `step_type`: `entrypoint`, `service_logic`, `persistence`, `client_call`, `step`.
  - `metadata_payload`: Source file, line number, detection method, operation type.
- **`ProcessTransition`**:
  - `from_step_id`, `to_step_id`.
  - `transition_type`: `CALLS`, `DEPENDS_ON`, `EXPOSES`, `CONSUMES`, `PERSISTS_TO`, `TRANSITIONS_TO`.
  - `transition_condition`: Optional branching condition where statically resolvable.

## 4. API Endpoints

- `GET /repositories/{id}/processes`: Lists all discovered processes for a repository snapshot.
- `GET /repositories/{id}/processes/{process_id}`: Retrieves complete process topology including ordered steps, linked components, and transitions.
- `POST /repositories/{id}/processes/discover`: Triggers deterministic process discovery on a target snapshot.

## 5. Architectural Boundaries

- Process discovery runs on the **Digital Twin** as source of truth.
- Process transitions do not modify or corrupt the structural artifact graph.
- Graph projection views can overlay process paths on top of the structural twin without creating secondary sources of truth.
