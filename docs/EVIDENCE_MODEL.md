# Structural Evidence Model

## 1. Traceability & Explainability Foundation

Every relationship and structural fact discovered during Phase 3 is linked to deterministic evidence records in PostgreSQL.

```
Structural Artifact / Relationship
              │
              ▼
       Evidence Record
       ├── source_type: DIRECT | OBSERVED | INFERRED | HEURISTIC
       ├── source_reference: file:line_start-line_end
       ├── confidence: 0.95 - 1.0 (Deterministic Static Quality)
       ├── description: Human-interpretable explanation
       └── payload: Structured context JSON (annotations, AST type, syntax path)
```

## 2. Detection Philosophy: Zero LLM Hallucination

Phase 3 strictly forbids LLM-generated facts or pseudo-confidences:
- **DIRECT / OBSERVED (Confidence 1.0)**:
  Concrete syntactic definitions directly present in the source AST (e.g. `class OrderService`, `def calculate_total`, `import fastapi`, `@GetMapping("/payments")`).
- **INFERRED (Confidence 0.95)**:
  Syntactically observable dependencies derived through structural conventions (e.g. `test_create_order` matching `create_order`, Spring superclass hierarchy).
- **HEURISTIC (Confidence 0.80 - 0.90)**:
  Pattern-based structural markers (e.g. naming conventions, build file references).

## 3. Source Location Tracking

Every extracted artifact records precise line numbers:
- `location`: e.g. `services/order-service/app.py:6`
- `line_start`: 6
- `line_end`: 12

This provides:
1. Explainability for future AI agents without re-parsing raw source text.
2. Direct navigation links for developer tooling.
3. Precise delta boundaries for change-impact and blast-radius analysis.
