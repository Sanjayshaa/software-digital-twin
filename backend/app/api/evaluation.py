"""
Controlled Software Benchmark Lab — API Router.
Exposes independent ground truth evaluations, scenario runs, history/snapshot tests,
and comparative confusion matrix summaries against controlled synthetic fixtures.
Strictly tags all outputs as SYNTHETIC BENCHMARK with clear provenance statements.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional

from app.core.database import get_db
from app.evaluation.benchmark_lab import benchmark_lab_service
from app.evaluation.ground_truth import BENCHMARK_SCENARIOS


router = APIRouter(
    prefix="/evaluation",
    tags=["Benchmark Evaluation Lab"],
    responses={404: {"description": "Resource not found"}}
)


@router.get("/scenarios")
def list_benchmark_scenarios() -> Dict[str, Any]:
    """
    Lists all available synthetic benchmark scenarios with their ground truth specifications.
    """
    scenarios = benchmark_lab_service.get_scenarios()
    return {
        "status": "success",
        "is_synthetic_benchmark": True,
        "provenance_statement": "SYNTHETIC BENCHMARK LAB — Evaluation conducted against controlled, isolated fixture repository with independent ground truth.",
        "total_scenarios": len(scenarios),
        "scenarios": scenarios
    }


@router.post("/run-scenario/{scenario_id}")
def run_benchmark_scenario(scenario_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Executes TwinCore production engines on a single controlled benchmark scenario
    and computes precision, recall, F1, negative controls, and path validity against ground truth.
    """
    if scenario_id not in BENCHMARK_SCENARIOS:
        raise HTTPException(
            status_code=404,
            detail=f"Benchmark scenario '{scenario_id}' not found. Available scenarios: {list(BENCHMARK_SCENARIOS.keys())}"
        )
    try:
        report = benchmark_lab_service.run_scenario(db, scenario_id)
        return {
            "status": "success",
            "report": report
        }
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to execute benchmark scenario '{scenario_id}': {str(exc)}"
        )


@router.post("/run-suite")
def run_benchmark_suite(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Executes the full benchmark evaluation suite across all 5 synthetic scenarios
    and compiles macro-averaged precision, recall, F1, and negative control integrity.
    """
    results = []
    total_tp = 0
    total_fp = 0
    total_fn = 0
    all_nc_passed = True

    for scen_id in BENCHMARK_SCENARIOS:
        try:
            report = benchmark_lab_service.run_scenario(db, scen_id)
            results.append(report)
            m = report["metrics"]
            total_tp += m["true_positives"]
            total_fp += m["false_positives"]
            total_fn += m["false_negatives"]
            if not report["negative_controls"]["passed"]:
                all_nc_passed = False
        except Exception as exc:
            results.append({
                "scenario_id": scen_id,
                "status": "ERROR",
                "error": str(exc)
            })

    macro_precision = round(total_tp / (total_tp + total_fp), 4) if (total_tp + total_fp) > 0 else 0.0
    macro_recall = round(total_tp / (total_tp + total_fn), 4) if (total_tp + total_fn) > 0 else 0.0
    macro_f1 = round(2 * (macro_precision * macro_recall) / (macro_precision + macro_recall), 4) if (macro_precision + macro_recall) > 0 else 0.0

    return {
        "status": "success",
        "is_synthetic_benchmark": True,
        "provenance_statement": "SYNTHETIC BENCHMARK LAB — Evaluation conducted against controlled, isolated fixture repository with independent ground truth.",
        "suite_summary": {
            "total_scenarios_evaluated": len(results),
            "macro_precision": macro_precision,
            "macro_recall": macro_recall,
            "macro_f1": macro_f1,
            "total_true_positives": total_tp,
            "total_false_positives": total_fp,
            "total_false_negatives": total_fn,
            "negative_controls_integrity_passed": all_nc_passed,
        },
        "scenarios": results
    }


@router.get("/history-tests")
def run_history_and_snapshot_tests(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Runs the 10 History and Snapshot verification tests required by the benchmark specification:
    First commit, multiple commits, tags, renames, deletions, restoration, historical source
    reconstruction, base-vs-target comparison, resumability, and repeated indexing idempotency.
    """
    try:
        report = benchmark_lab_service.run_history_and_snapshot_tests(db)
        return {
            "status": "success",
            "is_synthetic_benchmark": True,
            "provenance_statement": "SYNTHETIC BENCHMARK LAB — Git history and snapshot lifecycle tests executed on controlled repository fixture.",
            "report": report
        }
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to execute history and snapshot tests: {str(exc)}"
        )


@router.get("/summary")
def get_benchmark_summary(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Retrieves the executive summary of the benchmark lab, including active fixture state,
    ground truth manifests, and supported evaluation dimensions.
    """
    manifest = benchmark_lab_service.ensure_fixture()
    scenarios = benchmark_lab_service.get_scenarios()
    return {
        "status": "success",
        "is_synthetic_benchmark": True,
        "provenance_statement": "SYNTHETIC BENCHMARK LAB — Evaluation conducted against controlled, isolated fixture repository with independent ground truth.",
        "lab_fixture": {
            "repository_name": manifest.get("repository_name"),
            "total_commits": manifest.get("total_commits"),
            "tags": manifest.get("tags"),
            "fixture_path": manifest.get("fixture_path"),
        },
        "scenarios_count": len(scenarios),
        "supported_engines": [
            "StructuralTwinEngine (Git History & AST Discovery)",
            "ChangeImpactAnalyzer (Multi-Hop Graph Traversal)",
            "TestImpactEngine (Test Selection & Unknown Coverage)",
            "ScenarioSimulationEngine (What-If Virtual Twin)",
            "RiskIntelligenceEngine (Deterministic Multi-Factor Scoring)",
            "TwinGraphProjection (Architecture Graph Projection)"
        ],
        "metrics_guarantee": "Strict anti-circularity: Ground truth labels are immutable and created independently of TwinCore engines."
    }
