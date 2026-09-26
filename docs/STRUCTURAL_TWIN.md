# Phase 3: Structural Intelligence & Digital Twin Builder

## 1. Executive Architectural Overview

The Software Digital Twin for Pre-Deployment Risk and Test Impact Analysis converts arbitrary polyglot repositories into deterministic, explainable, snapshot-aware structural models.

```
Repository Source Code
        ↓
Phase 2 Discovery Brain (Language, Manifest, Framework, Capability, Plan)
        ↓
Phase 3 Analyzer Dispatcher & Runtime
        ↓
Parser Adapters (Tree-sitter AST & Specialized Parsers)
        ↓
Structural Extractors (Python, Java, TypeScript, JavaScript, COBOL, C++, SQL, Docker)
        ↓
Deterministic Normalization & Identity Engine (art_<hash>, rel_<hash>)
        ↓
PostgreSQL Persistence (Snapshots, Artifacts, Relationships, Evidence, Runs)
        ↓
Twin Query Service & NetworkX In-Memory MultiDiGraph Projection
```

### Core Architectural Principle
**Do NOT make the LLM responsible for understanding source-code structure.**
All structural facts (classes, methods, functions, API endpoints, test cases, divisions, dependencies) are extracted deterministically through concrete static syntax trees. AI agents in future phases will interpret, reason over, and explain this verified evidence without hallucinating structural links.

---

## 2. Structural Artifacts Specification

Every structural entity in the Twin is modeled in `StructuralArtifact` (`structural_artifacts` table):
- `id`: Stable deterministic hash `art_<sha256(snapshot_id:language:file_path:artifact_type:qualified_name)>`
- `repository_id`: Foreign key to `repositories.id`
- `snapshot_id`: Foreign key to `repository_snapshots.id`
- `file_id`: Foreign key to `files.id` (where applicable)
- `artifact_type`: Categorical discriminator:
  - `MODULE`: Source file or logical compilation module
  - `PACKAGE`: Logical namespace (e.g. Java package, Python namespace)
  - `CLASS`: Object-oriented class definition
  - `INTERFACE`: Interface contract (e.g. Java interface, TypeScript interface)
  - `FUNCTION`: Standalone top-level function
  - `METHOD`: Class/struct bound method
  - `CONSTRUCTOR`: Object constructor/initializer
  - `API_ENDPOINT`: Statically observable HTTP route (e.g. `GET /api/v1/orders`)
  - `DATABASE_ENTITY`: Database table or view
  - `SQL_TABLE`: Explicit SQL DDL table
  - `SQL_VIEW`: Explicit SQL DDL view
  - `DOCKER_STAGE`: Container stage or Docker Compose service
  - `TEST_CASE`: Test function or test class (Pytest, JUnit, Vitest)
  - `COBOL_DIVISION`: Mainframe structural division
  - `CPP_STRUCT`: C++ struct or class
  - `CPP_NAMESPACE`: C++ namespace definition
  - `EXTERNAL_DEPENDENCY`: Third-party imported package/symbol
- `name`: Local symbol identifier
- `qualified_name`: Canonical hierarchical name
- `location`: File path and start line (`services/app.py:42`)
- `line_start` / `line_end`: Source boundaries
- `confidence`: Deterministic static detection score (`1.0` for concrete AST nodes)
- `metadata_payload`: Raw structural metadata (annotations, decorators, parameters)

---

## 3. Snapshot Awareness & Idempotency

Software systems change over time. Every commit or analysis run is associated with a snapshot:
```
Repository
    ↓
Snapshot A (commit abc123) ──> Artifacts_A ──> Relationships_A
    ↓
Snapshot B (commit def456) ──> Artifacts_B ──> Relationships_B
```
Both snapshots remain fully queryable concurrently. Change-impact analysis compares Snapshot A with Snapshot B to compute diffs and blast radius without mutating historical state.

Analysis runs are strictly idempotent. Re-running analysis against the same repository snapshot produces matching deterministic IDs, preventing database pollution and duplicate edges.
