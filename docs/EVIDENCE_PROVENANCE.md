# Evidence Provenance & Canonical Data Contract

**Specification Date**: October 4, 2026  
**Auditor & Verification**: Antigravity Verification Subsystem  
**Scope**: Canonical Evidence Representation, Provenance Taxonomies, and Analytical Explainability Chains  
**Status**: ENFORCED & VERIFIED  

---

## 1. The Core Question: Why Did the System Produce This Result?

In an engineering-grade Software Digital Twin, black-box scores and unexplained numbers are unacceptable. Every metric, affected component, and test recommendation rendered by the system must provide a verifiable evidence chain traceable back to source code, Git commits, or sanitized runtime logs.

```
Source Code / Commit / Batch Logs
              │ (OBSERVED)
              ▼
   Structural Artifacts & Edges
              │ (DERIVED)
              ▼
    Change Impact Traversal
              │ (DERIVED)
              ▼
   Canonical Evidence Record  ──► [evidence_id, provenance, confidence, source_location, explanation]
```

---

## 2. Canonical Evidence Data Contract

Every major analytical result returns or links to a `CanonicalEvidence` payload:

```json
{
  "evidence_id": "ev_path_8192a7f1",
  "repository_id": "1dafa8df-4083-47b4-9021-d8a47a897aa8",
  "snapshot_id": "22432b8da6b4b07d93fbb06936bfd7fb00e36231",
  "evidence_type": "CAUSAL_IMPACT_PATH",
  "source_entity_id": "art_languageDetector_f812",
  "source_location": "src/utils/languageDetector.js:14",
  "relationship_type": "IMPORTS",
  "provenance": "DERIVED",
  "confidence": 1.0,
  "metadata": {
    "root_symbol": "languageDetector",
    "target_symbol": "ProctorExamPage",
    "relationship_chain": ["IMPORTS", "IMPORTS", "IMPORTS"],
    "depth": 3
  },
  "justification": "Root 'languageDetector' changed; propagated to 'ProctorExamPage' via [IMPORTS ➔ IMPORTS ➔ IMPORTS] at depth 3."
}
```

---

## 3. Provenance vs. Confidence: Strict Separation

Provenance defines **where the fact originated**. Confidence defines **how certain the system is in the assertion**. They are never conflated into a single number.

| Provenance Level | Definition | Acceptable Sources |
|---|---|---|
| `OBSERVED` | Direct empirical fact extracted from source code, AST, Git tree, or batch runtime logs. | Tree-sitter AST nodes, Git commit SHA, explicit HTTP route decorators, exact HTTP 500 runtime event. |
| `DERIVED` | Deterministically calculated via graph traversal or structural diff algorithms. | Pairwise AST delta, forward BFS impact propagation paths, architecture drift violations. |
| `INFERRED` | Heuristic association without explicit AST edge. | Proximity matching, test naming stem conventions (`test_foo.py` matches `foo.py`). |
| `SIMULATED` | Hypothetical projection generated inside an isolated virtual scenario. | Virtual snapshot mutation, what-if blast radius analysis. |
| `UNKNOWN` | Absence of evidence or unmapped execution paths. | Changed component with no mapped test assertions. |

---

## 4. Impact Finding Explainability Contract

For Change Impact and Blast Radius results, each affected entity exposes:
- **`root_change`**: Symbol name, file location, and modification type (`MODIFIED`, `ADDED`, `REMOVED`).
- **`affected_entity`**: Target symbol name and architectural type (`COMPONENT`, `API`, `TEST`, `PROCESS`).
- **`relationship_path`**: Ordered list of qualified node names from root to target.
- **`relationship_types`**: Ordered list of relationship edge types traversed (`CALLS`, `IMPORTS`, `TESTS`).
- **`depth`**: Exact graph distance (e.g. 1-hop, 2-hop, 3-hop).
- **`snapshot_id`**: Target snapshot wherein the relationship topology exists.
- **`evidence_ids`**: List of canonical evidence identifiers supporting the finding.
- **`explanation`**: Human-readable sentence summarizing the exact path.

### Concrete Example from Real Repository (`LAB-RECORD-SYSTEM`):
```text
Root: languageDetector
 └── IMPORTS ➔ CodeEditor (depth 1)
      └── IMPORTS ➔ StudentExam (depth 2)
           └── IMPORTS ➔ ProctorExamPage (depth 3)
```
- Multi-hop affected entity: `ProctorExamPage`
- Provenance: `DERIVED`
- Confidence: `1.0`
- Evidence ID: `ev_path_proctor_exam`
