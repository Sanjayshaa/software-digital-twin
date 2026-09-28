# Phase 6 — Test Impact Intelligence

## 1. Executive Summary & Objective

**Test Impact Intelligence** answers the central developer question:
> *"If I change this code, which tests should I run, and why?"*

Modern codebases often run hundreds or thousands of tests indiscriminately on every commit, wasting developer time, CI minutes, and compute costs. Alternatively, developers manually guess which test suites to run, introducing risk of uncaught regressions.

Phase 6 provides a deterministic, graph-grounded test impact engine that traverses real Digital Twin relationships (`TESTS`, `CALLS`, `IMPORTS`, `DEPENDS_ON`, `EXTENDS`, `IMPLEMENTS`, `CONSUMES`, `EXPOSES`) to identify:
1. **Directly Affected Tests**: Tests that directly assert on or target modified symbols, or tests whose code was directly altered.
2. **Indirectly Affected Tests**: Tests that target downstream or intermediate components reachable from the changed code via transitive call/dependency chains.
3. **Unaffected Tests**: Mapped tests in the repository that are outside the transitive blast radius of the change.
4. **Unknown Coverage**: Changed entities for which no direct or indirect test relationships exist in the living software model.

**Crucial Engineering Guardrail**: Test impact calculation is **100% deterministic** based on code relationships. No LLM or generative model is permitted in the traversal path or impact calculation.

---

## 2. Architecture & Data Flow

```
                      CODE CHANGE
            (git diff / snapshot comparison)
                           ↓
                   CHANGED ENTITIES
            (classes, methods, functions, files)
                           ↓
            DIGITAL TWIN RELATIONSHIP GRAPH
          (CALLS, IMPORTS, DEPENDS_ON, EXTENDS)
                           ↓
                  REACHABLE COMPONENTS
           (transitive downstream blast radius)
                           ↓
                    TEST LINKAGE
                   (TESTS edges)
                           ↓
                   AFFECTED TESTS
            (Directly vs Indirectly Affected)
                           ↓
                 TEST IMPACT REPORT
       (Classification, Paths, Reasons, Coverage)
```

---

## 3. Classification Taxonomy & Evidence Model

| Classification | Meaning | Evidence Status | Path Depth | Execution Recommendation |
| :--- | :--- | :--- | :--- | :--- |
| **DIRECTLY_AFFECTED** | Test directly targets the changed symbol or test code itself was modified | `OBSERVED` | 1 | **Mandatory** |
| **INDIRECTLY_AFFECTED** | Test covers a component reachable via transitive calls/imports | `DERIVED` | ≥ 2 | **Recommended** |
| **UNAFFECTED** | Test mapped in codebase, but outside transitive change reachability | `OBSERVED` | 0 | Optional / Skip |
| **UNKNOWN_COVERAGE** | Changed code entity has no mapped test suites or assertions | `UNKNOWN` | N/A | **Warning: Add Test** |

### Evidence Status Philosophy
In accordance with our digital twin principles:
- The system **never** claims a test "definitely fails" before running it.
- Instead, the system classifies tests as *"Potentially affected"* or *"Recommended for execution"*.
- When an explicit `TESTS` edge is present in AST analysis, status is `OBSERVED`.
- When multi-hop call traversal is used, status is `DERIVED`.

---

## 4. Deterministic Traversal Engine

### Relationship Directions
- `TESTS`: Direction `Test -> Target`. When Target changes, Test is impacted (Reverse trigger).
- `CALLS`: Direction `Caller -> Callee`. When Callee changes, Caller is impacted (Reverse trigger).
- `IMPORTS`: Direction `Importer -> Imported`. When Imported changes, Importer is impacted (Reverse trigger).
- `DEPENDS_ON`: Direction `Dependent -> Dependency`. When Dependency changes, Dependent is impacted.
- `EXTENDS`: Direction `Subclass -> Superclass`. When Superclass changes, Subclass is impacted.
- `IMPLEMENTS`: Direction `Implementer -> Interface`. When Interface changes, Implementer is impacted.

### Bounded Traversal & Cycle Safety
- **Cycle Protection**: Node traversal tracks `visited` identifiers to prevent infinite loops in cyclic dependencies (`A -> B -> A`).
- **Max Depth**: Traversal terminates at `config.max_depth` (default: 6 hops).
- **Deduplication**: If a test is reachable via multiple paths, the path with the shortest depth / highest confidence is retained.

---

## 5. API Reference

### 5.1 Run Test Impact Analysis
`POST /repositories/{repository_id}/test-impact`

**Request Body**:
```json
{
  "target_snapshot_id": "snap_target_uuid",
  "base_snapshot_id": "snap_base_uuid",
  "max_depth": 6,
  "include_indirect": true,
  "include_unaffected": true
}
```

**Response Body**:
```json
{
  "analysis_id": "uuid-here",
  "repository_id": "repo-uuid",
  "base_snapshot_id": "snap_base_uuid",
  "target_snapshot_id": "snap_target_uuid",
  "status": "completed",
  "summary": {
    "total_tests_mapped": 24,
    "potentially_affected_count": 2,
    "directly_affected_count": 1,
    "indirectly_affected_count": 1,
    "unaffected_count": 22,
    "unknown_coverage_count": 0
  },
  "affected_tests": [
    {
      "test_name": "test_tax_calculation",
      "location": "tests/test_tax.py:12",
      "classification": "DIRECTLY_AFFECTED",
      "evidence_status": "OBSERVED",
      "reason": "Directly tests or asserts on modified entity 'calculate_tax' via TESTS relationship.",
      "impact_path": ["PaymentService.calculate_tax", "test_tax_calculation"],
      "relationships": ["TESTS"],
      "depth": 1,
      "confidence": 1.0
    }
  ],
  "unaffected_tests": [...],
  "unknown_coverage": [],
  "execution_time_ms": 6.45
}
```

### 5.2 Retrieve Test Impact Analysis
`GET /repositories/{repository_id}/test-impact/{analysis_id}`

### 5.3 Test Catalog
`GET /repositories/{repository_id}/tests-catalog?snapshot_id={id}`

---

## 6. Verification & Test Coverage

Phase 6 is validated by unit and integration tests in `backend/tests/test_test_impact.py`:
- `test_direct_and_indirect_test_impact`: Confirms direct vs indirect classification across multi-hop calls.
- `test_unknown_coverage_detection`: Confirms changed functions without tests are flagged in `unknown_coverage`.
- `test_direct_test_file_modification`: Confirms modified test files are flagged as directly affected.
- `test_cycle_protection_and_bounded_traversal`: Confirms traversal terminates cleanly in cyclic graphs.
- `test_test_impact_api_endpoints`: Verifies HTTP status codes, schema validation, and negative 404 tests.
- `test_multiple_changed_entities`: Validates concurrent changes across disparate modules.
- `test_zero_changes_test_impact`: Verifies 0 false positives when comparing identical snapshots.
