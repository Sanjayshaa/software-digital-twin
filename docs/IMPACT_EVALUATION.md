# Running & Interpreting Impact Evaluations

**System**: TwinCore Software Digital Twin  
**Document Version**: 1.0.0  
**Phase**: 8.9  

---

## 1. Quick Start: Running Evaluations

The evaluation harness can be executed programmatically or via pytest test suites:

### Running Test Suites:
```bash
# Run the historical benchmark suite
npm run test:quick -- backend/tests/test_historical_evaluation.py

# Run the formalization and golden fixture matrix suite
npm run test:quick -- backend/tests/test_impact_formalization.py

# Run the deterministic repeatability suite
npm run test:quick -- backend/tests/test_impact_determinism.py
```

### Running via Python API:
```python
from app.core.database import SessionLocal
from app.evaluation.harness import EvaluationHarness

db = SessionLocal()
report = EvaluationHarness.run_benchmark(
    db=db,
    repository_id="<repo_id>",
    base_snapshot_id="<snap_a_id>",
    target_snapshot_id="<snap_b_id>",
    ground_truth_entities={"src.components.CodeEditor", "POST /api/run"},
    case_id="BENCH_LAB_RECORD_SYSTEM_V1",
)

print(report.to_dict())
```

---

## 2. Interpreting the Benchmark Comparison Output

The harness emits a structured machine-readable JSON object:

```json
{
  "case_id": "BENCH_LAB_RECORD_SYSTEM_V1",
  "repository_name": "LAB-RECORD-SYSTEM",
  "base_commit": "815c0749b9d120c72ab84223c3684613f91e76c7",
  "target_commit": "22432b8da6b4b07d93fbb06936bfd7fb00e36231",
  "changes": {
    "total": 120,
    "added": 27,
    "removed": 1,
    "modified": 92
  },
  "comparison": {
    "CHANGED_FILES_SET": {
      "precision": 0.0,
      "recall": 0.0,
      "f1": 0.0,
      "total_predicted": 120,
      "runtime_ms": 1.2
    },
    "IMPORT_CLOSURE": {
      "precision": 0.5,
      "recall": 0.33,
      "f1": 0.40,
      "total_predicted": 125,
      "runtime_ms": 4.5
    },
    "CALL_CLOSURE": {
      "precision": 0.67,
      "recall": 0.67,
      "f1": 0.67,
      "total_predicted": 128,
      "runtime_ms": 6.8
    },
    "FULL_TWIN": {
      "status": "VALID",
      "precision": 1.0,
      "recall": 0.67,
      "f1": 0.80,
      "total_predicted": 29,
      "runtime_ms": 28.4,
      "average_path_depth": 1.3,
      "notes": "Evaluated against independent manual ground truth. Previous 1.00/1.00/1.00 result was circular and is formally INVALID."
    }
  },
  "path_verification": {
    "total_paths": 57,
    "valid_paths": 57,
    "validity_percentage": 100.0,
    "unique_affected_count": 29,
    "multi_hop_count": 7,
    "depth_1_paths": 45,
    "depth_2_paths": 10,
    "depth_3_paths": 2
  }
}
```

> [!WARNING]
> **Audit Notice (Phase 8.9.1)**:
> The initial Phase 8.9 report listed Full Twin metrics as $P=1.00, R=1.00, F1=1.00$. The Phase 8.9.1 Evaluation Integrity Audit discovered that this was due to circular target leakage (evaluating the Twin against its own predicted output). That result is formally classified as **`INVALID`**.
>
> **Academic Status**: "Evaluation result not yet suitable for accuracy claims."
> Measurable results are restricted to independently verified manual annotations (`benchmark_cases/lab_record_system/manual_labels.json`).

### Key Metric Indicators:
- **`status`**: Metric validity status (`VALID`, `PARTIAL_PATCH_ONLY`, `NO_GROUND_TRUTH`, `INVALID_GROUND_TRUTH`, `GROUND_TRUTH_INSUFFICIENT`).
- **`validity_percentage`**: Percentage of predicted paths whose intermediate hops exist verbatim in the target snapshot's PostgreSQL relationship table. Must be $100\%$ for deterministic credibility.
- **`multi_hop_count`**: Number of entities requiring $> 1$ hop to discover. This represents the precise value that simpler baselines miss.
- **`f1`**: Balances blast-radius over-approximation against missed dependents.


---

## 3. Known Limitations

1. **Dynamic Reflection & Monkey-Patching**: Python `getattr(obj, name)` and JavaScript `window[method]` cannot be fully resolved statically; they are tagged with `INFERRED` or `UNKNOWN` provenance.
2. **Polyglot Foreign Function Interfaces (FFI)**: Calls across C/Rust extensions or WASM modules are not yet indexed into the structural twin.
3. **Database Schema Trigger Cascades**: SQL triggers and stored procedures are modeled as `DATABASE` components, but internal trigger execution flows are not traced beyond table-level `PERSISTS_TO` links.
