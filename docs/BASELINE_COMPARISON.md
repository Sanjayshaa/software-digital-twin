# Baseline Comparison: Algorithmic Architecture & Assumptions

**System**: TwinCore Software Digital Twin  
**Document Version**: 1.0.0  
**Phase**: 8.9  

---

## 1. Overview of Comparative Baselines & Fair Evaluation Architecture

To rigorously evaluate the added value of the Software Digital Twin, four distinct algorithms are evaluated against identical change sets and evaluated against strictly **independent ground truth**:

```
                         SAME INPUT
                             │
       ┌─────────────────────┼─────────────────────┐
       ▼                     ▼                     ▼
  [BASELINE 1 & 2]      [BASELINE 3]          [FULL TWIN]
Changed Files / Imports  Call Closure     ImpactPropagator
       │                     │                     │
       └─────────────────────┼─────────────────────┘
                             ▼
                 INDEPENDENT GROUND TRUTH
             (Test / Runtime / Manual Audit)
                             │
                             ▼
                      FAIR METRICS
```

**Anti-Pattern Prohibited by Protocol**:
```
             FULL TWIN
                 │
                 ▼
            GROUND TRUTH
                 │
                 ▼
       evaluate FULL TWIN
    (CIRCULAR TARGET LEAKAGE - STRICTLY FORBIDDEN)
```


---

## 2. Formal Baseline Definitions

### Baseline 1: Changed-Files Set (`CHANGED_FILES_SET`)
- **Philosophy**: Standard git commit inspection (what naive CI scripts use).
- **Prediction Rule**: An entity is affected if and only if its declaration or source file was directly added, modified, or removed in the commit diff.
- **Assumptions**: Changes have no ripple effects; developers must manually know what else to test.
- **Strengths**: $O(1)$ computation time, zero false positives on direct change locations.
- **Weaknesses**: Complete blindness to callers, API consumers, database dependents, and tests.

### Baseline 2: Import / Dependency Closure (`IMPORT_CLOSURE`)
- **Philosophy**: Static file-level dependency analysis (what Webpack/Vite and some monorepo tools like Nx or Turborepo use for affected project calculation).
- **Prediction Rule**: Changed entities plus all files that directly `import` or `require` them (1-hop reverse `IMPORTS` / `DEPENDS_ON`).
- **Assumptions**: Impact is module-scoped; if file $B$ imports file $A$, changing $A$ impacts all of $B$.
- **Strengths**: Fast graph lookup, catches direct module users.
- **Weaknesses**: Misses function-level granularity, misses multi-hop transitive dependencies beyond depth 1, ignores reverse call-chain dynamics, and does not model API or database links.

### Baseline 3: Simple Call Closure (`CALL_CLOSURE`)
- **Philosophy**: Classic 1-hop static call-graph reachability (compiler dead-code/caller analysis).
- **Prediction Rule**: Changed symbols plus all functions/methods that directly invoke them (1-hop reverse `CALLS`).
- **Assumptions**: Impact is restricted to direct callers.
- **Strengths**: Symbol-level granularity (functions, methods), higher semantic relevance than file imports.
- **Weaknesses**: Does not propagate through intermediate callers (depth $\ge 2$), ignores structural interface implementations, fails on dynamic dispatch / alias paths.

### Full Digital Twin (`FULL_TWIN`)
- **Philosophy**: Unified multi-tier causal propagation across typed relational edges with bounded depth and cycle protection.
- **Prediction Rule**: Traverses `CALLS`, `IMPORTS`, `DEPENDS_ON`, `CONSUMES`, `EXTENDS`, `IMPLEMENTS`, `PERSISTS_TO`, `EXPOSES`, `TESTS`, and `PARTICIPATES_IN` with relationship-specific directionality (`REVERSE` vs `FORWARD`), alias path resolution, and epistemic uncertainty preservation.
- **Assumptions**: Changes propagate through functional, structural, data, and testing layers until bounded by maximum depth or terminal boundaries.
- **Strengths**: Catches multi-hop chains (e.g. `TaxCalculator` $\leftarrow$ `PaymentService` $\leftarrow$ `CheckoutController` $\to$ `Checkout API`), identifies affected test cases, and maintains machine-verifiable evidence chains.

---

## 3. Comparative Summary Matrix

| Capability | Baseline 1 (Diff) | Baseline 2 (Imports) | Baseline 3 (Calls) | Full Digital Twin |
| :--- | :--- | :--- | :--- | :--- |
| **Granularity** | File | File / Module | Symbol | Symbol & File |
| **Direct Callers** | No | Incidental | Yes (1-hop) | Yes (1-hop & Multi-hop) |
| **Transitive Reachability** | No | No | No | Yes (up to Depth 5) |
| **Inheritance & Interfaces** | No | No | No | Yes (`EXTENDS`, `IMPLEMENTS`) |
| **API Endpoints Exposed** | No | No | No | Yes (`EXPOSES` FORWARD) |
| **Automated Tests Affected**| No | No | No | Yes (`TESTS` REVERSE) |
| **Cycle Protection** | N/A | No | No | Yes (Path-set pruning) |
| **Evidence Traceability** | Git SHA only | Import link | Call link | Full Path Evidence IDs |
| **Runtime Latency** | $< 1\text{ms}$ | $1\text{–}5\text{ms}$ | $2\text{–}10\text{ms}$ | $15\text{–}45\text{ms}$ |

---

## 4. Evaluation Protocol & Anti-Circularity Guarantees

All comparative evaluations are subject to the strict fairness invariants established in Phase 8.9.1:
1. **Identical Inputs**: Every baseline and the Full Twin process the exact same base snapshot, target snapshot, and detected change items.
2. **Identical Ground Truth**: All four algorithms are scored against the same immutable `GroundTruthSet`.
3. **No Twin Influence on Ground Truth**: Ground truth generated or influenced by Twin propagation is rejected (`status = INVALID_GROUND_TRUTH`).
4. **Three Evaluation Modes**:
   - `PATCH_ONLY`: Direct file overlap only. Marked partial.
   - `INDEPENDENT_LABELS`: Independently verified test, runtime, or manual architect labels.
   - `NO_GROUND_TRUTH`: Prediction reporting only, no accuracy claims.
5. **Academic Status of Historical Result**: The previous $1.00 / 1.00 / 1.00$ result on `LAB-RECORD-SYSTEM` was circular and is formally classified as **INVALID**. It has been replaced with: *"Evaluation result not yet suitable for accuracy claims."*

