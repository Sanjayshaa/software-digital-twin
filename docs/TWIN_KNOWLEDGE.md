# Twin Knowledge & Deterministic Intelligence Architecture

**Specification Date**: October 4, 2026  
**Auditor & Verification**: Antigravity Intelligence Architecture Subsystem  
**Scope**: Deterministic `TwinKnowledgeService`, Object-Level Multi-Tenant Authorization, and Zero-Hallucination Query Engine  
**Status**: ACTIVE & VERIFIED  

---

## 1. System Architecture

The `TwinKnowledgeService` provides a unified, authoritative query boundary over the Software Digital Twin without introducing external vector stores, LLMs, or autonomous agents in Phase 8.8.

```
Client (Browser UI / CLI / REST Client)
                   │
                   ▼ (Bearer JWT / Session Identity)
       [ Twin Knowledge API Router ]
                   │
                   ▼
       [ Multi-Tenant Authorization Gateway ]
       (authenticated user ➔ repo ownership ➔ snapshot ownership ➔ entity ownership)
                   │
                   ▼
       [ TwinKnowledgeService ]
        ├── Repository & Snapshot Overviews
        ├── Structural Artifacts & Topologies
        ├── Dependency & Dependent Chains (CALLS, IMPORTS, TESTS)
        ├── Verified API Surface
        ├── Change Sets & Structural Diffs
        ├── Causal Impact Paths & Evidence IDs
        ├── Risk Intelligence & Architecture Guardrails
        ├── Batch Runtime Telemetry (Zero PII)
        ├── Incidents & Candidate Causal Paths
        ├── Virtual Simulation Scenarios
        └── Grounded "Ask Twin" Query Engine
                   │
                   ▼
       [ PostgreSQL Authoritative Tables ]
```

---

## 2. Strict Zero-Trust Authorization Model

Every single knowledge query authoritatively validates:
1. **User Identity**: Extracted from signed HMAC-SHA256 JWT access token.
2. **Repository Ownership**: `Repository.owner_id == principal.user_id` (or administrator override). Guests access only their explicitly provisioned ephemeral repositories.
3. **Snapshot Ownership**: `RepositorySnapshot.repository_id == repo.id`. Cross-repository snapshot queries are rejected with HTTP 404 (non-disclosure).
4. **Entity Ownership**: Artifacts, relationships, drifts, incidents, and scenarios must belong to the authorized snapshot/repository.
5. **No Direct Frontend Database Access**: The web UI and CLI communicate exclusively through authenticated REST endpoints.

---

## 3. Query Taxonomy & API Surface

| Endpoint | Method | Response Model | Provenance Guarantee |
|---|---|---|---|
| `/repositories/{id}/twin-knowledge/overview` | `GET` | `TwinKnowledgeOverview` | `OBSERVED` |
| `/repositories/{id}/twin-knowledge/snapshots/{snap_id}` | `GET` | Snapshot Topology Summary | `OBSERVED` |
| `/repositories/{id}/twin-knowledge/artifacts/{art_id}` | `GET` | `CanonicalEvidence` + Artifact Syntax | `OBSERVED` |
| `/repositories/{id}/twin-knowledge/artifacts/{art_id}/dependencies` | `GET` | Direct Dependencies & Dependents | `OBSERVED` |
| `/repositories/{id}/twin-knowledge/artifacts/{art_id}/tests` | `GET` | Mapped Test Claims | `DERIVED` / `UNKNOWN` |
| `/repositories/{id}/twin-knowledge/api-surface` | `GET` | Verified HTTP Route Registry | `OBSERVED` |
| `/repositories/{id}/twin-knowledge/changes` | `GET` | Pairwise AST Structural Diffs | `OBSERVED` / `DERIVED` |
| `/repositories/{id}/twin-knowledge/impact-paths` | `GET` | `ImpactPathFinding` list | `DERIVED` |
| `/repositories/{id}/twin-knowledge/guardrails` | `GET` | Conformance & Drift Violations | `DERIVED` |
| `/repositories/{id}/twin-knowledge/runtime-evidence` | `GET` | Batch Sanitized Runtime Events | `OBSERVED` |
| `/repositories/{id}/twin-knowledge/incidents` | `GET` | Incidents & Candidate Causal Paths | `OBSERVED` / `DERIVED` |
| `/repositories/{id}/twin-knowledge/scenarios` | `GET` | Virtual What-If Scenarios | `SIMULATED` |
| `/repositories/{id}/twin-knowledge/query` | `POST` | `TwinKnowledgeQueryResult` | Dynamic Provenance |

---

## 4. Ask Twin Grounding & Non-Hallucination Policy

The "Ask Twin" query engine in Phase 8.8 operates under strict truthfulness contracts:
- **No LLM Synthesizer**: Does not route questions to probabilistic language models.
- **Deterministic Intent Classification**: Parses developer queries against topological entities, active incidents, change blast radius, test claims, and architecture guardrails.
- **Evidence Attachment**: Every generated answer includes explicit `evidence_ids` linking directly to database rows.
- **Truthful Failure & Gap Disclosure**: If coverage is missing or no path connects two entities, the engine returns `Provenance.UNKNOWN` and states that no evidence exists, rather than guessing.
