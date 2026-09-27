# Incident Intelligence & Causal Investigation Foundation

## 1. Core Objective & Architectural Principles

The **Incident Intelligence** subsystem connects production incidents with the Digital Twin, runtime evidence, and recent deployment code diffs:

```
 Incident Declaration / Ingestion
                │
                ▼
      [Linked Runtime Events]  (Errors, Traces, Spans)
                │
                ▼
      [Affected Component]  (StructuralArtifact in Twin)
                │
                ├─────────────────────────────┬─────────────────────────────┐
                ▼                             ▼                             ▼
    [Recent Code Diffs]              [Affected Processes]             [Covering Tests]
(Phase 4 ChangeDetector)            (Process Twin Workflows)         (AST TESTS Relations)
                │                             │                             │
                └─────────────────────────────┼─────────────────────────────┘
                                              ▼
                        [Candidate Causal Paths Engine]
                                              │
                                              ▼
                             Investigation Result Report
                      (Candidate causal paths + Uncertainties)
```

### Architectural Principles:
1. **No Speculative Truth**: The engine produces **"Candidate causal paths"** or **"Evidence-backed investigation paths"**. It never claims "this definitely caused the incident" without deterministic proof.
2. **Re-use Working Systems**: Utilizes Phase 4 `ChangeDetector` for symbol-level AST diffing rather than duplicating change logic.
3. **Strict Separation of Confidence and Risk**: Confidence measures evidence quality (trace vs. heuristic); risk measures structural blast-radius impact.
4. **No LLM Hallucination**: All correlations and graph walks are deterministic. Future LLM/agent layers (Phase 9) will consume this verified evidence substrate.

## 2. Evidence Hierarchy

Evidence confidence is derived strictly from observable provenance:

| Level | Evidence Type | Baseline Confidence | Description |
|:---:|:---|:---:|:---|
| 1 | Observed runtime trace / span | 0.95 | Directly captured invocation or exception stack frame |
| 2 | Executed test trace | 0.90 | Concrete test execution failure against target component |
| 3 | Explicit deployment / change event | 0.85 | Git commit diff or release event modifying symbol AST |
| 4 | Explicit API / dependency declaration | 0.85 | Statically defined route, import, or build dependency |
| 5 | Static code relationship | 0.80 | AST call graph or reference |
| 6 | Documentation | 0.60 | Inferred from docstrings or project documentation |
| 7 | Heuristic inference | 0.50 | Naming convention or probabilistic matching |
| 8 | LLM hypothesis | **Future Only** | Interpretive hypothesis (Phase 9 only) |

## 3. Causal Investigation Workflow

When an investigation is requested for `incident_id`:
1. **Resolve Incident Context**: Identifies the affected component, target snapshot, and associated runtime events (by `incident_id` or matching service/trace).
2. **Detect Recent Changes**: Reuses Phase 4 `ChangeDetector` to compute normalized `ChangeSet` between the baseline snapshot and target snapshot.
3. **Trace Structural Causal Paths**:
   - Direct modification: If the affected component itself was changed in the recent commit, creates a direct candidate path (confidence 0.95).
   - Topological traversal: Performs directional graph traversal from each recently changed symbol to the incident component along `CALLS`, `DEPENDS_ON`, and `EXPOSES` edges (depth-bounded).
4. **Correlate Impacted Processes**: Identifies all `ProcessDefinition` workflows traversing the affected component.
5. **Correlate Related Tests**: Queries all test cases (`relationship_type='TESTS'`) covering the affected component or candidate changed symbols.
6. **Synthesize Uncertainties**: Explicitly documents missing evidence, untested paths, or unanchored correlations.

## 4. API Endpoints

- `GET /repositories/{id}/incidents`: Lists incidents with status, severity, and environment filters.
- `POST /repositories/{id}/incidents`: Creates a new incident, automatically correlating runtime errors.
- `GET /repositories/{id}/incidents/{incident_id}`: Retrieves complete incident details and linked evidence.
- `POST /repositories/{id}/incidents/{incident_id}/investigate`: Executes deterministic investigation and generates candidate causal paths.

## 5. Security & Safety

- Incident investigation results are completely reproducible: repeating an investigation against the same snapshot and telemetry produces identical deterministic findings.
- Payloads and explanations adhere to sanitized credentials guidelines.
