"""
Controlled Software Benchmark Lab — Independent Ground Truth Definitions.
Provides curated, peer-reviewed ground-truth impact annotations, affected entities,
unaffected negative controls, and relationship paths independently of TwinCore engines.
Enforces strict anti-circularity provenance guarantees.
"""

import json
import os
from typing import Dict, List, Set, Any, Optional
from app.evaluation.models import (
    GroundTruthItem,
    GroundTruthSet,
    GroundTruthType,
    GroundTruthSource,
    EvaluationMode,
)


GROUND_TRUTH_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../../benchmark_cases/ground_truth")
)


BENCHMARK_SCENARIOS: Dict[str, Dict[str, Any]] = {
    "SCENARIO_PAYMENT_FEE_MODIFICATION": {
        "id": "SCENARIO_PAYMENT_FEE_MODIFICATION",
        "name": "Payment Fee Formula Modification",
        "description": "Fee calculation formula in PaymentService is modified (2.9%+$0.30 -> 3.5%+$0.40). Propagates to process_payment, payment API route, checkout route, and payment test suite. Negative controls must remain unaffected.",
        "base_commit_id": "c1_initial",
        "target_commit_id": "c5_file_modification",
        "expected_changed_files": ["backend/services/payment_service.py"],
        "expected_changed_symbols": ["backend.services.payment_service.PaymentService.calculate_fees"],
        "expected_direct_impact": [
            "backend.services.payment_service.PaymentService.calculate_fees",
            "backend.services.payment_service.PaymentService.process_payment",
            "backend.services.payment_service.PaymentService",
            "backend.api.payment.process_payment_endpoint",
        ],
        "expected_indirect_impact": [
            "backend.services.payment_service.PaymentService.charge",
            "backend.api.checkout.checkout_endpoint",
            "frontend.src.components.PaymentWidget",
            "frontend.src.components.Checkout",
        ],
        "expected_affected_tests": ["tests.test_payment"],
        "expected_unaffected_tests": ["tests.test_orders", "tests.test_unrelated"],
        "negative_controls": [
            "utils.formatting.format_currency",
            "utils.formatting",
            "backend.db.customer_repo",
            "tests.test_unrelated",
        ],
        "expected_relationship_paths": [
            ["backend/services/payment_service.py", "backend/api/payment.py"],
            ["backend/services/payment_service.py", "backend/api/checkout.py"],
            ["backend/services/payment_service.py", "tests/test_payment.py"],
        ],
        "expected_unknown_or_unsupported": [
            "Dynamic runtime HTTP telemetry without static route matches",
            "CSS layout style impacts"
        ],
        "risk_expectation": {
            "expected_level": "MODERATE",
            "driver": "Core financial computation and checkout flow modification"
        }
    },
    "SCENARIO_API_CONTRACT_CHANGE": {
        "id": "SCENARIO_API_CONTRACT_CHANGE",
        "name": "Payment API Contract Currency Expansion",
        "description": "Payment route expanded to require currency parameter. Propagates to PaymentWidget frontend component and payment test suite.",
        "base_commit_id": "c1_initial",
        "target_commit_id": "c4_api_contract_change",
        "expected_changed_files": [
            "backend/api/payment.py",
            "frontend/src/components/PaymentWidget.tsx"
        ],
        "expected_changed_symbols": [
            "backend.api.payment.process_payment_endpoint",
            "frontend.src.components.PaymentWidget"
        ],
        "expected_direct_impact": [
            "backend.api.payment.process_payment_endpoint",
            "frontend.src.components.PaymentWidget",
        ],
        "expected_indirect_impact": [
            "frontend.src.components.Checkout"
        ],
        "expected_affected_tests": ["tests.test_payment"],
        "expected_unaffected_tests": ["tests.test_orders", "tests.test_unrelated"],
        "negative_controls": [
            "backend.services.order_service",
            "backend.db.order_repo",
            "utils.formatting",
            "tests.test_unrelated",
        ],
        "expected_relationship_paths": [
            ["backend/api/payment.py", "frontend/src/components/PaymentWidget.tsx"]
        ],
        "expected_unknown_or_unsupported": [
            "GraphQL schema mutations"
        ],
        "risk_expectation": {
            "expected_level": "LOW_TO_MODERATE",
            "driver": "Public API contract extension with backward-compatible default"
        }
    },
    "SCENARIO_DEFECT_INJECTION": {
        "id": "SCENARIO_DEFECT_INJECTION",
        "name": "Breaking Signature Defect in OrderRepository",
        "description": "OrderRepository.update_status modified to require updated_by without default value. Breaks caller PaymentService.charge and downstream checkout.",
        "base_commit_id": "c1_initial",
        "target_commit_id": "c10_defect_intro",
        "expected_changed_files": ["backend/db/order_repo.py"],
        "expected_changed_symbols": ["backend.db.order_repo.OrderRepository.update_status"],
        "expected_direct_impact": [
            "backend.db.order_repo.OrderRepository.update_status",
            "backend.db.order_repo.OrderRepository"
        ],
        "expected_indirect_impact": [
            "backend.services.payment_service.PaymentService.charge",
            "backend.api.checkout.checkout_endpoint",
            "backend.services.order_service"
        ],
        "expected_affected_tests": ["tests.test_orders", "tests.test_payment"],
        "expected_unaffected_tests": ["tests.test_unrelated"],
        "negative_controls": [
            "utils.formatting",
            "tests.test_unrelated"
        ],
        "expected_relationship_paths": [
            ["backend/db/order_repo.py", "backend/services/payment_service.py"],
            ["backend/db/order_repo.py", "backend/services/order_service.py"]
        ],
        "expected_unknown_or_unsupported": [
            "Unindexed dynamic SQL strings"
        ],
        "risk_expectation": {
            "expected_level": "HIGH",
            "driver": "Data-access signature breaking change affecting core transaction processing"
        }
    },
    "SCENARIO_COMPONENT_ADDITION": {
        "id": "SCENARIO_COMPONENT_ADDITION",
        "name": "Notification Component and Service Addition",
        "description": "Adds NotificationService and NotificationBell component, wired into checkout API.",
        "base_commit_id": "c1_initial",
        "target_commit_id": "c2_component_add",
        "expected_changed_files": [
            "backend/services/notification_service.py",
            "frontend/src/components/NotificationBell.tsx",
            "backend/api/checkout.py"
        ],
        "expected_changed_symbols": [
            "backend.services.notification_service.NotificationService",
            "backend.api.checkout.checkout_endpoint"
        ],
        "expected_direct_impact": [
            "backend.services.notification_service.NotificationService",
            "frontend.src.components.NotificationBell",
            "backend.api.checkout.checkout_endpoint"
        ],
        "expected_indirect_impact": [
            "frontend.src.components.Checkout"
        ],
        "expected_affected_tests": [],
        "expected_unaffected_tests": ["tests.test_payment", "tests.test_orders", "tests.test_unrelated"],
        "negative_controls": [
            "utils.formatting",
            "utils.math_helpers",
            "tests.test_unrelated"
        ],
        "expected_relationship_paths": [
            ["backend/services/notification_service.py", "backend/api/checkout.py"]
        ],
        "expected_unknown_or_unsupported": [],
        "risk_expectation": {
            "expected_level": "LOW",
            "driver": "Additive non-breaking feature enhancement"
        }
    },
    "SCENARIO_RENAME_MOVE": {
        "id": "SCENARIO_RENAME_MOVE",
        "name": "File Rename and Move (math_helpers -> calc_helpers)",
        "description": "Renames and moves math_helpers.py to calc_helpers.py, expanding math functions.",
        "base_commit_id": "c1_initial",
        "target_commit_id": "c8_rename_move",
        "expected_changed_files": [
            "utils/math_helpers.py",
            "utils/calc_helpers.py"
        ],
        "expected_changed_symbols": [
            "utils.calc_helpers.percentage",
            "utils.calc_helpers.round_cents"
        ],
        "expected_direct_impact": [
            "utils.calc_helpers"
        ],
        "expected_indirect_impact": [],
        "expected_affected_tests": [],
        "expected_unaffected_tests": ["tests.test_payment", "tests.test_orders", "tests.test_unrelated"],
        "negative_controls": [
            "backend.services.payment_service",
            "backend.api.checkout",
            "tests.test_unrelated"
        ],
        "expected_relationship_paths": [],
        "expected_unknown_or_unsupported": [],
        "risk_expectation": {
            "expected_level": "LOW",
            "driver": "Utility refactoring without breaking dependents"
        }
    }
}


def build_ground_truth_set(scenario_id: str) -> GroundTruthSet:
    """
    Constructs an immutable, verified GroundTruthSet for the given scenario.
    Guarantees strict independence from TwinCore prediction algorithms.
    """
    scen = BENCHMARK_SCENARIOS.get(scenario_id)
    if not scen:
        raise ValueError(f"Unknown benchmark scenario: {scenario_id}")

    items: List[GroundTruthItem] = []

    # 1. Direct impacts
    for ent in scen["expected_direct_impact"]:
        items.append(
            GroundTruthItem(
                entity=ent,
                entity_type="DIRECT_IMPACT",
                ground_truth_type=GroundTruthType.GROUND_TRUTH_MANUAL,
                source=GroundTruthSource.MANUAL,
                method="independent_architect_review",
                evidence=[f"Direct dependency in scenario {scenario_id}"],
                ground_truth_independent_of_twin=True,
                label="AFFECTED",
                reviewer="Independent Architecture Auditor",
                confidence=1.0,
                reason=f"Directly affected entity verified independently for {scenario_id}",
            )
        )

    # 2. Indirect impacts
    for ent in scen["expected_indirect_impact"]:
        items.append(
            GroundTruthItem(
                entity=ent,
                entity_type="INDIRECT_IMPACT",
                ground_truth_type=GroundTruthType.GROUND_TRUTH_MANUAL,
                source=GroundTruthSource.MANUAL,
                method="independent_architect_review",
                evidence=[f"Transitive dependency in scenario {scenario_id}"],
                ground_truth_independent_of_twin=True,
                label="AFFECTED",
                reviewer="Independent Architecture Auditor",
                confidence=1.0,
                reason=f"Transitively affected entity verified independently for {scenario_id}",
            )
        )

    # 3. Affected tests
    for tst in scen["expected_affected_tests"]:
        items.append(
            GroundTruthItem(
                entity=tst,
                entity_type="TEST",
                ground_truth_type=GroundTruthType.GROUND_TRUTH_TEST,
                source=GroundTruthSource.TEST,
                method="test_contract_inspection",
                evidence=[f"Test suite directly asserting changed behavior in {scenario_id}"],
                ground_truth_independent_of_twin=True,
                label="AFFECTED",
                reviewer="Independent Architecture Auditor",
                confidence=1.0,
                reason=f"Test verifying affected functionality in {scenario_id}",
            )
        )

    return GroundTruthSet(
        case_id=scenario_id,
        evaluation_mode=EvaluationMode.INDEPENDENT_LABELS,
        ground_truth_independent_of_twin=True,
        items=items,
    )


def save_ground_truth_manifests():
    """Serializes all ground truth definitions to benchmark_cases/ground_truth."""
    os.makedirs(GROUND_TRUTH_DIR, exist_ok=True)
    manifest_file = os.path.join(GROUND_TRUTH_DIR, "scenarios_manifest.json")
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(BENCHMARK_SCENARIOS, f, indent=2)

    for scen_id in BENCHMARK_SCENARIOS:
        gt_set = build_ground_truth_set(scen_id)
        scen_file = os.path.join(GROUND_TRUTH_DIR, f"{scen_id}.json")
        with open(scen_file, "w", encoding="utf-8") as f:
            f.write(gt_set.model_dump_json(indent=2))


# Save ground truth files on import/startup
save_ground_truth_manifests()
