# Phase 7 — Risk Intelligence & Architecture Guardrails

## 1. Executive Summary & Objective

**Risk Intelligence & Architecture Guardrails** answers the fundamental pre-deployment question:
> *"How significant is this change, what evidence contributes to that significance, and which architecture guardrails are relevant?"*

In high-velocity software engineering, changes often carry hidden systemic risks:
- modifying a high-centrality hub consumed across many modules,
- altering public API contracts,
- touching live production traffic paths,
- degrading test confidence or leaving changed entities without test coverage,
- introducing architectural layer drift, cyclic dependencies, or boundary bypasses.

Phase 7 moves beyond *"What may be affected?"* (Phase 4) and *"Which tests may be affected?"* (Phase 6) to produce an **explainable, deterministic, evidence-driven risk assessment**.

**Crucial Engineering Guardrail**:
- The risk engine is **100% deterministic** and grounded in empirical facts (AST relationships, test mappings, runtime telemetry, incident records, and architectural boundary rules).
- The system **never claims failure probabilities** (e.g. "87% chance of outage").
- The system uses transparent, explainable categories (`LOW`, `MODERATE`, `HIGH`, `CRITICAL`) and strictly separates **RISK** from **CONFIDENCE**.
- Zero black-box AI or LLM hallucinations are permitted in the calculation path.

---

## 2. Core Architecture & Evidence Pipeline

```
                               CODE CHANGE
                      (base -> target snapshots)
                                  ↓
                           CHANGE EVIDENCE
                      (ChangeSet: modified symbols)
                                  ↓
                           IMPACT EVIDENCE
                    (Phase 4 blast radius & depth)
                                  ↓
                             TEST IMPACT
                    (Phase 6 affected tests & coverage)
                                  ↓
                      ARCHITECTURE CONFORMANCE
                   (Phase 3 baseline & boundary rules)
                                  ↓
                        DEPENDENCY COUPLING
                     (hub centrality, in/out degree)
                                  ↓
                         RUNTIME EVIDENCE
                    (Phase 5 production telemetry)
                                  ↓
                         INCIDENT HISTORY
                    (Phase 5 past operational outages)
                                  ↓
                         9 RISK FACTORS
                                  ↓
                    EXPLAINABLE RISK ASSESSMENT
                                  +
                       ARCHITECTURE GUARDRAILS
                                  ↓
                          ENGINEER DECISION
```

---

## 3. The 9 Deterministic Risk Factors

Every factor produces structured evidence with complete provenance:

| Risk Factor | Source of Truth | What It Measures | Evidence Generated |
| :--- | :--- | :--- | :--- |
| **`IMPACT_BREADTH`** | Phase 4 `ImpactResult` & `ChangeSet` | Total quantity of entities in the blast radius | Directly modified count, downstream affected count, total blast radius |
| **`IMPACT_DEPTH`** | Phase 4 `ImpactPath` | Maximum graph traversal hops reached | Maximum depth, longest causal propagation path |
| **`TEST_IMPACT`** | Phase 6 `TestImpactResult` | Affected tests and coverage completeness | Directly affected tests, indirectly affected tests, unknown coverage warnings |
| **`ARCHITECTURE_DRIFT`** | Architecture Baseline Spec & Rules | Boundary violations, layer violations, cycles | Specific rule IDs violated, source/target, line coordinates |
| **`DEPENDENCY_COUPLING`** | `ArtifactRelationship` (AST Graph) | Hub centrality (caller fan-in, dependency fan-out) | Maximum in-degree, maximum out-degree, consumed hub symbols |
| **`RUNTIME_ACTIVITY`** | Phase 5 `RuntimeEvent` | Live production traffic on modified components | Event count, production flag, error severities, latest event timestamp |
| **`INCIDENT_HISTORY`** | Phase 5 `Incident` | Past operational outages linked to components | Linked incident titles, severity levels, outage dates |
| **`API_SURFACE`** | `APIEndpoint` & `EXPOSES` Edges | Public endpoints and exposed contracts touched | Directly modified API routes, downstream impacted APIs |
| **`UNKNOWN_EVIDENCE`** | Epistemic Gap Analysis | Unobserved tests, missing telemetry, or baseline | Explicit list of unobserved signals lowering assessment confidence |

---

## 4. Risk vs. Confidence: Epistemic Separation

A central design principle of our Digital Twin is the strict separation between:
1. **RISK**: How significant the available evidence indicates the change to be (`LOW`, `MODERATE`, `HIGH`, `CRITICAL`).
2. **CONFIDENCE**: How complete and reliable the supporting evidence is (`HIGH`, `MEDIUM`, `LOW`).

### Why this matters
- A change with **HIGH RISK** and **LOW CONFIDENCE** means: *"Significant blast radius or coupling is observed, but test coverage or runtime telemetry is missing or unverified."*
- Missing information is classified as **`UNKNOWN`**, never default to "low risk".

### Confidence Scoring
- Confidence score begins at `1.0` (100% evidence completeness).
- Penalties are applied for epistemic gaps:
  - `-0.35` if zero test suites exist for repository,
  - `-0.10` per changed entity with unknown coverage (up to `-0.30`),
  - `-0.20` if runtime telemetry is unavailable for affected components,
  - `-0.20` if architecture baseline specification is missing or unconfigured.
- Thresholds:
  - `HIGH`: Confidence score ≥ 0.80
  - `MEDIUM`: Confidence score ≥ 0.50
  - `LOW`: Confidence score < 0.50

---

## 5. Architecture Boundary Guardrails

Architecture guardrails evaluate changes against defined baseline specifications (`docs/architecture-baseline.yaml`):

| Guardrail Type | Status | Meaning |
| :--- | :--- | :--- |
| **`FORBIDDEN_DEPENDENCY`** | `VIOLATION` / `PASS` | Checks explicit forbidden edges (e.g. `domain` importing `services`). |
| **`LAYER_VIOLATION`** | `VIOLATION` / `PASS` | Checks layer boundary contracts (e.g. `discovery` importing `analysis`). |
| **`BOUNDARY_VIOLATION`** | `VIOLATION` / `PASS` | Checks defined package/module boundary crossings. |
| **`CIRCULAR_DEPENDENCY`** | `VIOLATION` / `PASS` | Detects dependency cycles across modules (`A -> B -> A`). Critical severity. |
| **`UNEXPECTED_EXTERNAL_DEPENDENCY`** | `VIOLATION` / `PASS` | Prohibits unauthorized cloud or database vendor imports (e.g. Rule-06). |
| **`UNEXPECTED_COUPLING`** | `WARN` / `PASS` | Detects high fan-out coupling (>8 outbound dependencies) from changed entities. |
| **`ARCHITECTURE_BYPASS`** | `VIOLATION` / `PASS` | Detects upper layers bypassing service boundaries directly to low-level parsers or DBs. |

If baseline configuration is absent, status is truthfully reported as **`UNKNOWN`**.

---

## 6. Scoring Formulas & Category Derivation

### Factor Weighting
Each active risk factor contributes to a normalized composite score (0 to 100):
- `ARCHITECTURE_DRIFT`: 1.5
- `API_SURFACE`: 1.2
- `TEST_IMPACT`: 1.2
- `IMPACT_BREADTH`: 1.1
- `DEPENDENCY_COUPLING`: 1.0
- `RUNTIME_ACTIVITY`: 1.0
- `INCIDENT_HISTORY`: 1.0
- `IMPACT_DEPTH`: 0.8
- `UNKNOWN_EVIDENCE`: 0.6

$$\text{Composite Score} = \frac{\sum (\text{Score}_i \times \text{Weight}_i)}{\sum \text{Weight}_i}$$

### Deterministic Category Rules
- **`CRITICAL`**:
  - Any critical guardrail violation (e.g. `CIRCULAR_DEPENDENCY` or critical layer breach), OR
  - Composite score $\ge 75.0$, OR
  - Broad blast radius ($\ge 8$ entities) with active production traffic AND architecture violation.
- **`HIGH`**:
  - Any guardrail violation, OR
  - Composite score $\ge 50.0$, OR
  - Broad blast radius ($\ge 8$ entities) with active production traffic, OR
  - Impact breadth factor score $\ge 75.0$.
- **`MODERATE`**:
  - Composite score $\ge 25.0$, OR
  - Multi-hop propagation (depth $\ge 2$), OR
  - Moderate test impact.
- **`LOW`**:
  - Isolated change, composite score $< 25.0$, zero architectural violations, low coupling.

---

## 7. API Reference

### 7.1 Run Risk Analysis
`POST /repositories/{repository_id}/risk-analysis`

**Request Body**:
```json
{
  "target_snapshot_id": "snap_target_uuid",
  "base_snapshot_id": "snap_base_uuid",
  "max_depth": 6,
  "environment": "production"
}
```

**Response Body**:
```json
{
  "analysis_id": "risk_a1b2c3d4e5f6",
  "repository_id": "repo-uuid",
  "base_snapshot_id": "snap_base_uuid",
  "target_snapshot_id": "snap_target_uuid",
  "status": "completed",
  "overall_category": "HIGH",
  "overall_score": 62.4,
  "confidence": "HIGH",
  "confidence_score": 0.85,
  "explanation": "HIGH — based on significant factors (impact breadth, test impact & coverage), 1 architecture guardrail violation(s), 4 potentially affected test(s), active production runtime traffic.",
  "risk_factors": [
    {
      "factor_id": "IMPACT_BREADTH",
      "name": "Impact Breadth",
      "score": 75.0,
      "weight": 1.1,
      "severity": "HIGH",
      "status": "OBSERVED",
      "evidence": [
        "1 directly modified entity/entities",
        "8 directly affected downstream entity/entities",
        "3 indirectly affected entity/entities",
        "Total affected blast radius: 12 entities"
      ],
      "details": { "total_affected": 12, "changed": 1 },
      "description": "Measures the total quantity and scope of entities reached in the dependency blast radius."
    }
  ],
  "guardrail_results": [
    {
      "rule_id": "RULE-01",
      "rule_name": "Discovery Isolation",
      "guardrail_type": "LAYER_VIOLATION",
      "status": "VIOLATION",
      "severity": "CRITICAL",
      "affected_entities": ["app.services.discovery.scanner", "app.services.analysis.engine"],
      "source": "app.services.discovery",
      "target": "app.services.analysis",
      "evidence": ["Forbidden cross-layer IMPORTS: scanner -> engine (discovery/scanner.py:5)"],
      "explanation": "Layer boundary violation: Code in layer 'discovery' directly depends on forbidden layer 'analysis'."
    }
  ],
  "affected_components": ["core.CoreConfig", "services.Comp1"],
  "affected_apis": ["POST /api/v1/checkout"],
  "affected_tests": ["tests.test_auth_0", "tests.test_auth_1"],
  "runtime_evidence": ["PaymentGateway: auth_failed (production)"],
  "incident_evidence": ["High Error Rate in Billing [CRITICAL]"],
  "unknown_evidence": [],
  "recommendations": [
    "Resolve architectural boundary violations before merging into release branch.",
    "Execute mandatory directly affected tests and verify regression test suites.",
    "Ensure deployment uses canary rollout or staging validation due to active production traffic."
  ],
  "execution_time_ms": 18.42,
  "created_at": "2026-09-28T17:48:00.000000"
}
```

### 7.2 Retrieve Stored Risk Analysis
`GET /repositories/{repository_id}/risk-analysis/{analysis_id}`

### 7.3 Architecture Guardrails
`GET /repositories/{repository_id}/architecture/guardrails?snapshot_id={id}`

---

## 8. Verification & Test Strategy

Phase 7 is validated by 19 unit, integration, and property tests in `backend/tests/test_risk_intelligence.py`:
- `test_scenario_01_low_impact_change`: Validates isolated local changes yield `LOW` category.
- `test_scenario_02_broad_impact_change`: Validates blast radius >8 entities yields `HIGH`/`CRITICAL`.
- `test_scenario_03_deep_impact_change`: Validates 3+ hop propagation escalates depth factor score $\ge 70$.
- `test_scenario_04_high_test_exposure`: Confirms affected tests are linked and direct assertions counted.
- `test_scenario_05_unknown_test_coverage`: Confirms missing tests penalize confidence and raise warnings.
- `test_scenario_06_architecture_violation`: Confirms layer violations trigger guardrail `VIOLATION`.
- `test_scenario_07_architecture_warning`: Confirms anomalous coupling triggers guardrail `WARN`.
- `test_scenario_08_architecture_pass`: Confirms clean architecture graphs produce 0 violations and 0 drift score.
- `test_scenario_09_runtime_evidence_contribution`: Validates production runtime telemetry elevates risk.
- `test_scenario_10_incident_evidence_contribution`: Validates linked historical incidents contribute evidence.
- `test_scenario_11_api_exposure`: Confirms public API modifications are flagged with high severity.
- `test_scenario_12_unknown_runtime_evidence`: Confirms missing telemetry is reported as `UNKNOWN`.
- `test_scenario_13_unknown_architecture_state`: Confirms missing baseline reports status `UNKNOWN`.
- `test_scenario_14_multiple_risk_factors`: Validates combined multi-factor risk synthesis.
- `test_scenario_15_no_evidence_identical_snapshots`: Confirms zero changes produce score `0.0` and `LOW`.
- `test_scenario_16_cyclic_graph`: Confirms graph cycle safety and termination without infinite loops.
- `test_scenario_17_multiple_changed_entities`: Confirms disparate multi-symbol change aggregation.
- `test_scenario_18_deterministic_repeatability`: Verifies identical inputs yield identical outputs.
- `test_risk_service_and_api_endpoints`: Verifies REST API lifecycle, database persistence in `AnalysisRun` and `RiskAssessment`.

---

## 9. Limitations & Planned Evolution

1. **Static Baseline Resolution**: Baseline layer rules are evaluated against static AST imports and relationships; dynamic reflection-based invocations require runtime telemetry correlation.
2. **Deterministic Risk vs. Probabilistic Modeling**: The engine produces explainable risk assessments from observable facts, not simulated machine-learning failure predictions.
3. **What-If Simulation**: Phase 7 evaluates actual snapshot changes; virtual "What-If" simulated mutation of code without saving snapshots is scheduled for **Phase 8**.
