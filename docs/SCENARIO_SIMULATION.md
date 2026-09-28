# Phase 8: What-If / Scenario Simulation

## 1. Purpose & Core Product Concept

The Software Digital Twin fundamentally transforms from an analyzer of **historical or current changes** into a **predictive, exploratory simulation workbench**.

Prior to Phase 8, change impact analysis required actual commits or working-tree file modifications:
```
REAL CODE CHANGE → DIGITAL TWIN → BLAST RADIUS → TEST IMPACT → RISK → GUARDRAILS
```

With Phase 8 What-If / Scenario Simulation, engineers can explore proposed mutations against the Digital Twin before touching a single line of code:
```
PROPOSED CHANGE (Hypothetical)
       ↓
TEMPORARY DIGITAL TWIN SCENARIO
       ↓
SIMULATED IMPACT (Structural Traversal)
       ↓
SIMULATED TEST IMPACT (Direct, Indirect, Unknown)
       ↓
SIMULATED RISK (Deterministic scoring + Confidence)
       ↓
SIMULATED ARCHITECTURE GUARDRAILS (Boundary checks)
       ↓
STATE COMPARISON (Base vs. Scenario) & EXPLANATION
```

---

## 2. Critical Safety & Isolation Guarantees

The simulation framework operates under strict non-destructive isolation guarantees:
1. **Zero Source Modifications**: No repository files, working tree contents, or local git state are ever modified or written to.
2. **Zero Snapshot Overwrites**: Base `RepositorySnapshot` entities and their relational graph remain 100% immutable.
3. **In-Memory Virtual Twin**: The virtual scenario model (`VirtualTwinModel`) clones artifacts and relationships in memory. Mutations (`MODIFY_SYMBOL`, `ADD_DEPENDENCY`, `REMOVE_DEPENDENCY`, `MODIFY_API`, `MODIFY_COMPONENT_RELATIONSHIP`) exist strictly within the virtual twin context.
4. **Deterministic Base Immutability**: Verified by test `test_scenario_25_critical_base_twin_immutability` ensuring:
   $$\text{Base Twin}_{\text{after scenario}} \equiv \text{Base Twin}_{\text{before scenario}}$$
5. **No Production Deployments or Fake Incidents**: The engine does not trigger deployments, fabricate telemetry, or invent future failures.

---

## 3. Supported Scenario Mutations

Phase 8 deliberately supports bounded structural mutations that map cleanly to architectural primitives:

| Mutation Type | Description | Target Specification | Example |
| :--- | :--- | :--- | :--- |
| `MODIFY_SYMBOL` | Modifies an existing symbol (function, method, class) | `target_entity_name`: Symbol name<br>`target_entity_id`: Optional artifact ID | `PaymentService.calculate_tax` |
| `ADD_DEPENDENCY` | Introduces a proposed dependency edge between two components | `source_entity_name`: Caller<br>`target_entity_name`: Callee<br>`relationship_type`: Edge type | `CheckoutService` → `PaymentService` (`CALLS`) |
| `REMOVE_DEPENDENCY` | Simulates severing an existing dependency edge | `source_entity_name`: Caller<br>`target_entity_name`: Callee | `CheckoutService` -/-> `LegacyPaymentService` |
| `MODIFY_API` | Modifies an existing HTTP/API route or contract | `target_entity_name`: API route or symbol | `POST /payments` |
| `MODIFY_COMPONENT_RELATIONSHIP`| Adjusts architectural dependency between high-level components | `source_entity_name`: Component A<br>`target_entity_name`: Component B | `BillingModule` → `NotificationService` |

---

## 4. Scenario Validation

Before simulation execution, the deterministic `ScenarioValidator` checks:
- **Target / Source Existence**: Verifies whether specified targets and sources exist in the active base snapshot.
- **Relationship Integrity**: When removing dependencies, verifies that the edge actually exists in the base twin graph.
- **Ambiguity Detection**: Flags multiple entities sharing identical names if artifact IDs are not qualified.
- **Unknown Entities**: Validations flag non-existent entities as `UNKNOWN` rather than silently creating phantom records.
- **Cyclic / Invalid Changes**: Validates structural cycles and records warnings.

---

## 5. Simulation Pipeline & Reuse of Existing Engines

Rather than duplicating intelligence logic, the `ScenarioSimulationEngine` creates a virtual adapter that injects in-memory clones into the battle-tested deterministic engines from Phases 1–7:

```
Proposed Changes
       ↓
ScenarioValidator (Deterministic check)
       ↓
VirtualTwinModel (In-memory cloning & mutation)
       ↓
Virtual ChangeSet (Synthesizes structural diff without disk git changes)
       ↓
ImpactPropagator (In-memory target graph traversal)
       ↓
TestImpactEngine (In-memory test correlation & coverage classification)
       ↓
ArchitectureGuardrails (Virtual topology boundary checks)
       ↓
RiskEngine (Simulated risk score, confidence, and factor breakdown)
       ↓
State Comparator (Base vs. Scenario topology diff)
       ↓
ScenarioResult (Persisted scenario report)
```

---

## 6. Strict Evidence Separation & Wording

Simulation outputs strictly distinguish observed facts from simulated predictions:

| Evidence Category | Source | Allowed Language | Prohibited Language |
| :--- | :--- | :--- | :--- |
| `SIMULATED_STRUCTURAL` | Graph propagation through virtual twin | *"Potentially affected"*, *"Simulated impact"*, *"Proposed dependency"* | *"Definitely breaks"*, *"Will fail"* |
| `OBSERVED_RUNTIME` | Historical telemetry on base entities | *"Observed runtime evidence"*, *"Intersects component with recent production activity"* | *"Scenario caused high traffic"*, *"Predicted 500 errors"* |
| `HISTORICAL_INCIDENT`| Recorded incidents on base entities | *"Historical incident evidence"*, *"Touching component associated with past incident INC-8088"* | *"Guaranteed outage"*, *"Future incident forecasted"* |
| `UNKNOWN_EVIDENCE` | Unmapped test coverage or missing telemetry | *"Unknown coverage"*, *"Untested boundary"* | *"100% bug free"* |

---

## 7. REST API Endpoints

All endpoints adhere to existing project conventions under `/repositories/{repository_id}/scenarios`:

- `POST /repositories/{id}/scenarios`: Creates a new scenario definition with proposed mutations.
- `GET /repositories/{id}/scenarios`: Lists all scenarios created for the repository.
- `GET /repositories/{id}/scenarios/{scenario_id}`: Retrieves scenario details and simulation results.
- `POST /repositories/{id}/scenarios/{scenario_id}/analyze`: Executes simulation on an existing scenario.
- `DELETE /repositories/{id}/scenarios/{scenario_id}`: Deletes a temporary scenario and its simulation records.
- `POST /repositories/{id}/simulate`: Direct one-shot simulation API (creates, validates, analyzes, and returns results in a single call).

---

## 8. User Interface Experience

The UI features a dedicated **What-If Simulation** workspace view (`view-simulation`):
1. **Simulation Designer**:
   - Scenario Name & Description input.
   - Proposed Mutation builder: selects Mutation Type (`MODIFY_SYMBOL`, `ADD_DEPENDENCY`, etc.), Source and Target entities, and Relationship type.
   - Multi-mutation scenario support.
2. **Simulation Results Workspace**:
   - **Scenario Overview**: Title, simulation status, base snapshot reference.
   - **Simulation Metric Cards**:
     - *Simulated Risk*: Risk tier badge, score (0–100), confidence level.
     - *Potentially Affected Components*: Direct vs. indirect count.
     - *Potentially Affected APIs*: Contract impact tally.
     - *Simulated Test Impact*: Directly affected, indirectly affected, and unknown coverage breakdown.
     - *Simulated Guardrails*: Violations and warnings against architectural governance rules.
   - **State Comparison (Current vs. Proposed)**:
     - Clear structural delta breakdown (added/removed relationships, newly affected components).
   - **Explainable Evidence Breakdown**:
     - Tabs for Simulated Structural Evidence, Observed Runtime Evidence, Historical Incident Evidence, and Assumptions/Unknowns.
3. **Scenario History Drawer**:
   - Displays past simulation runs for quick comparison and reloading.

---

## 9. Limitations & Explicit AI Boundary

- **No Arbitrary Source-Code Synthesis**: The system does not write synthetic code or guess AST bodies. It operates on architectural, API, and symbol contracts.
- **No LLM / Generative AI**: All simulation analysis is 100% deterministic graph logic. (Natural-language-to-scenario translation is deferred to Phase 9).
- **No Telemetry Synthesis**: Runtime evidence is contextualized from past observations, not fabricated for hypothetical futures.
