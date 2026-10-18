# ADR 003: Impact Directionality & Epistemic Uncertainty Formalism

**Status**: ACCEPTED  
**Date**: 2026-10-05  
**Context**: Phase 8.9 Formalization of Reverse Graph Traversal and 5-State Test Impact Taxonomy  

---

## 1. Context & Problem Statement

Early static analysis tools often conflated edge direction with impact direction, or treated all edges as symmetric.
For example, if function $A$ calls function $B$ ($A \to B$):
- Traversing forward ($A \to B$) identifies what $A$ depends upon.
- When $B$ is modified, traversing forward would ask "What does $B$ call?", missing $A$ completely!
To find who is impacted by a change to $B$, the traversal must find all nodes that have an edge pointing **into** $B$ (reverse reachability).

Additionally, many industrial tools classify unmapped tests as "safe to skip" or "unaffected".
In dynamic languages (TypeScript, Python), dynamic dispatch, monkey-patching, and reflection mean that an absence of a static edge does not guarantee absence of a runtime dependency. Treating unmapped tests as `UNAFFECTED` creates dangerous regression escapes.

---

## 2. Decision: Explicit Traversal Direction & 5-State Epistemic Taxonomy

### 1. Separation of Concerns: Impact vs. Risk vs. Confidence
- **`IMPACT`**: Topological reachability from modified roots along typed relationships. (Direct, Transitive).
- **`RISK`**: Engineering criticality and business severity (e.g., changes to core payment gateways carry high risk regardless of blast radius size).
- **`CONFIDENCE`**: Provenance strength of the relationship edge ($1.0$ for direct AST call, $0.8$ for heuristic alias match).

### 2. Directional Traversal Invariants
- Functional dependency edges (`CALLS`, `IMPORTS`, `DEPENDS_ON`, `CONSUMES`, `EXTENDS`, `IMPLEMENTS`, `TESTS`, `PERSISTS_TO`) are traversed in **`REVERSE`**.
- Structural exposure and state transitions (`EXPOSES`, `PARTICIPATES_IN`, `TRANSITIONS_TO`) are traversed in **`FORWARD`**.

### 3. Five-State Test Impact Taxonomy
Every test case in the repository is deterministically classified into one of five disjoint states:

1. **`TEST_IS_AFFECTED`**: A proven causal path connects the test suite to a modified AST symbol. (Safe Decision: **RUN**).
2. **`TEST_EXISTS_AND_IS_UNAFFECTED`**: The test footprint is completely known, verified via AST import/call analysis, and is provably disjoint from the change set. (Safe Decision: **SKIP**).
3. **`TEST_EXISTS_BUT_COVERAGE_IS_UNKNOWN`**: Test exists in the codebase, but the engine cannot definitively prove what code it exercises. (Safe Decision: **RUN**).
4. **`NO_TEST_RELATIONSHIP_FOUND`**: Code was changed, but no test points to it. (Surfaces untested technical debt).
5. **`NO_AUTOMATED_TEST_EXISTS`**: Repository has zero test suites.

**Core Safety Invariant**:
$$\text{TestSelectionDecision} = \begin{cases} \text{SKIP} & \text{if and only if claim} = \text{TEST\_EXISTS\_AND\_IS\_UNAFFECTED} \\ \text{RUN} & \text{if claim} \in \{\text{TEST\_IS\_AFFECTED}, \text{TEST\_EXISTS\_BUT\_COVERAGE\_IS\_UNKNOWN}\} \end{cases}$$
