# Software Digital Twin — Intended Architecture & Baseline Specification

## 1. Executive Summary & Purpose
This document establishes the official intended architectural baseline, layer definitions, subsystem boundaries, and database design for the **AI-Powered Software Digital Twin for Pre-Deployment Risk and Test Impact Analysis**. It serves as the canonical contract against which the automated **Architecture Drift Detection Engine** validates repository code via deterministic AST evidence.

---

## 2. Intended Architectural Flow

```
                      USER / ENGINEER
                             │
                             ▼
                         WEB / CLI
                             │
                             ▼
                    FASTAPI APPLICATION
                             │
                             ▼
                    APPLICATION SERVICES
                             │
                             ▼
                      DISCOVERY BRAIN
                             │
                             ▼
                      PROJECT PROFILE
                             │
                             ▼
                    CAPABILITY REGISTRY
                             │
                             ▼
                      ANALYSIS PLANNER
                             │
                             ▼
                      ANALYZER RUNTIME
                             │
                             ▼
             PARSER / STATIC ANALYSIS ADAPTERS
                             │
                             ▼
                    STRUCTURAL EXTRACTION
                             │
                             ▼
                        NORMALIZATION
                             │
                             ▼
                        DIGITAL TWIN
                             │
                             ▼
                  EVIDENCE + SNAPSHOT MODEL
                             │
                             ▼
                         POSTGRESQL
                             │
                             ▼
                      GRAPH PROJECTION
                             │
                             ▼
             FUTURE IMPACT / TEST / RISK ENGINES
                             │
                             ▼
                   FUTURE AI INTELLIGENCE
```

---

## 3. Strict Architectural Boundaries

The architecture enforces strict decoupling between distinct intelligence engines:

$$\text{Discovery} \neq \text{Structural Analysis} \neq \text{Digital Twin} \neq \text{Graph} \neq \text{Impact Analysis} \neq \text{Risk Analysis} \neq \text{AI}$$

### Core Isolation Rules:
1. **Discovery Isolation**:
   `Discovery Brain` must inspect repository manifests, directory structures, and file contents to determine project profiles and plan capabilities. It must **never** import or depend on AST analyzers, Graph engines, Impact engines, Risk engines, or AI agents.
2. **Analysis Subsystem Decoupling**:
   - `Parsers`: Pure syntactic adapters (e.g., Tree-sitter C-grammar adapters, Python AST visitors) with zero database or service dependencies.
   - `Analyzers`: Language-specific workers implementing `BaseAnalyzer`. They receive normalized contexts and emit raw structural artifacts and relationships.
   - `Normalizers`: Deterministic schema identity transformers with zero side effects.
   - `Runtime & Dispatcher`: Coordinates execution order without knowing downstream persistence details.
3. **Domain & Twin Decoupling**:
   The Digital Twin domain models (`app.models.entities`) define the structural and relational source of truth. Models must **never** import application services, API routers, or CLI components.
4. **Presentation Decoupling**:
   APIs (`app.api`) and CLI (`cli`) must interact with the application through application service facades. They must not invoke raw parsers directly or bypass service boundaries.
5. **No Direct Vendor-Locked SDKs**:
   The domain and data layers must rely on standard SQLAlchemy 2.0 and PostgreSQL drivers (`psycopg2`, `psycopg3`). No core services may depend on proprietary cloud APIs (`supabase-py`, AWS SDKs, etc.).

---

## 4. Database Architecture

The persistence layer guarantees complete portability across standard PostgreSQL-compatible providers:

```
                      Application Services
                               │
                               ▼
                        SQLAlchemy 2.0
                               │
                               ▼
                          PostgreSQL
                               │
                               ▼
                   Digital Twin Source of Truth
```

### Supported PostgreSQL Deployment Targets:
- **Local Containerized PostgreSQL**: Docker `postgres:16-alpine` running locally on port `5434:5432`.
- **Supabase PostgreSQL**: Standard PostgreSQL connection string over TCP/SSL.
- **Enterprise Managed PostgreSQL**: AWS RDS, Google Cloud SQL, Azure Database for PostgreSQL.

> **Design Invariant**: Core Digital Twin tables, migrations, and queries utilize standard ANSI SQL / PostgreSQL relational constructs (Foreign Keys, Cascades, JSONB, composite indexes). No proprietary Supabase client libraries are imported into the backend engine.

---

## 5. Actual Architecture vs. Intended Architecture Comparison

In accordance with architectural audit requirements, the existing codebase was inspected and compared directly against the intended baseline:

| Subsystem / Layer | Intended Architecture | Actual Implementation | Status | Difference Classification |
|---|---|---|---|---|
| **Presentation (Web API)** | `USER -> API -> SERVICES` | `backend/app/api/` routes delegate to `services/` | **CONFORMANT** | Confirmed 100% |
| **Presentation (CLI)** | `USER -> CLI -> SERVICES` | `cli/main.py` invokes services in-process, directly instantiates `SessionLocal()` for local repo init | **DIFFERENCE** | `INTENTIONAL (CLI In-Process Mode)`: Allows local offline scanning without requiring background HTTP daemon. |
| **Discovery Brain** | Standalone discovery & planning | `backend/app/services/discovery/` has zero dependencies on `analysis`, `graph`, `risk`, or `ai` | **CONFORMANT** | Confirmed 100% |
| **Structural Analysis** | Ingests Discovery profile/plan; AST parsing | `backend/app/services/analysis/` imports `FileInventory` and `AnalyzerInterface` from discovery | **CONFORMANT** | `INTENTIONAL (Contract Sharing)`: Shared contracts for scan inventory and analyzer registration. |
| **Domain Models** | Pure entity source of truth | `backend/app/models/entities.py` imports only `Base` and SQLAlchemy standard primitives | **CONFORMANT** | Zero service or presentation imports. |
| **Architecture Drift Engine** | Deterministic AST drift detector | `backend/app/services/architecture/` with zero LLM guesswork | **CONFORMANT** | Confirmed 100% |
| **Database Portability** | Pure PostgreSQL / SQLAlchemy | Port 5434 PostgreSQL container, Alembic migrations, no vendor SDKs | **CONFORMANT** | Confirmed 100% |
| **Cycle Prevention** | Zero circular dependencies | NetworkX cycle detection evaluated 56 boundaries: 0 cycles detected | **CONFORMANT** | Confirmed 100% |

---

## 6. Architecture Drift Detection Specification

The architecture drift engine detects the following 7 drift categories:

1. **`FORBIDDEN_DEPENDENCY`**: An import explicitly banned by architectural contract (e.g. `presentation -> infrastructure`).
2. **`LAYER_VIOLATION`**: An import crossing layer boundaries improperly (e.g. `discovery -> analysis`).
3. **`CIRCULAR_DEPENDENCY`**: Circular import cycle $A \to B \to C \to A$ (Severity: `CRITICAL`).
4. **`UNEXPECTED_EXTERNAL_DEPENDENCY`**: Unauthorized third-party or cloud vendor SDK (e.g. `supabase`, `boto3`).
5. **`BOUNDARY_VIOLATION`**: Subsystem accessing another subsystem's private internal state.
6. **`UNEXPECTED_COUPLING`**: Unrelated subsystems tightly coupled.
7. **`ARCHITECTURE_BYPASS`**: Presentation bypassing service facade to execute raw parser adapters.

### Structural Conformance Formula:
$$\text{Architecture Conformance} = \max\left(0.0, 1.0 - \frac{\text{Violations}}{\max(1, \text{Expected Boundaries})}\right) \times 100\%$$

> **Critical Distinction**: Architecture Conformance is an objective structural measurement of codebase boundary integrity. It is decoupled from Project Execution Progress % in all logs and reports.
