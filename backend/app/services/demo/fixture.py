"""
Deterministic E-Commerce Microservices Reference Fixture & Demo Engine.

Provides:
1. Complete e-commerce microservices sample architecture:
   - API Gateway
   - Authentication Service
   - Product Catalog Service
   - Order Service
   - Payment Service
   - Inventory Service
   - Database Entities (users, products, orders, payments, inventory)
   - API Endpoints (/api/v1/checkout, /api/v1/orders, etc.)
   - Test Suites (test_payment, test_orders, etc.)
2. Deterministic graph traversal for blast radius calculation.
3. Deterministic What-If simulation engine with isolated virtual twins.
4. Truthful test impact analysis (suggested vs executed vs passed/failed).
5. Transparent mathematical risk score breakdown.
6. Extension point declarations for future multi-repo, PR review, and CI targeting.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from enum import Enum


class DemoProvenance(str, Enum):
    STATIC_EXTRACTED = "STATIC_EXTRACTED"
    SIMULATED_STRUCTURAL = "SIMULATED_STRUCTURAL"
    OBSERVED_RUNTIME = "OBSERVED_RUNTIME"
    HISTORICAL_INCIDENT = "HISTORICAL_INCIDENT"
    UNKNOWN_EVIDENCE = "UNKNOWN_EVIDENCE"


# ============================================================================
# 1. DETERMINISTIC REPOSITORY & FIXTURE SPECIFICATION
# ============================================================================

DEMO_REPO_METADATA = {
    "id": "repo-demo-ecommerce-001",
    "name": "ecommerce-microservices-reference",
    "description": "Enterprise E-Commerce Microservices Architecture (API Gateway, Auth, Products, Orders, Payments, Inventory)",
    "primary_language": "Python / TypeScript / SQL",
    "default_branch": "main",
    "commit_sha": "a7f920c8b31d402e86ef512d7c0018a4",
    "commit_message": "feat: harden checkout flow with payment idempotency and stock reservation",
    "committed_at": "2026-10-24T16:30:00Z",
    "provenance": "DETERMINISTIC_REFERENCE_FIXTURE",
    "fixture_version": "v1.4.0",
    "discovery_summary": {
        "total_files": 48,
        "languages": {
            "Python": {"files": 28, "lines": 4820, "percentage": 58.4},
            "TypeScript / React": {"files": 12, "lines": 2140, "percentage": 25.9},
            "SQL": {"files": 5, "lines": 860, "percentage": 10.4},
            "Dockerfile / YAML": {"files": 3, "lines": 440, "percentage": 5.3},
        },
        "extracted_symbols": 86,
        "api_endpoints": 14,
        "services": 6,
        "database_tables": 5,
        "test_suites": 6,
        "test_cases": 24,
        "extraction_method": "Tree-sitter AST & OpenAPI Spec Static Parser",
        "unsupported_boundaries": [
            "Dynamic runtime reflection in plugin loaders",
            "Untyped Redis Pub/Sub string message dispatch",
            "Third-party external Stripe / PayPal cloud webhook callbacks"
        ],
        "is_precomputed_demo": True,
        "label": "DEMO FIXTURE: Statically parsed from E-Commerce Microservices Reference Spec"
    }
}


# ============================================================================
# 2. DETERMINISTIC KNOWLEDGE GRAPH ARTIFACTS & RELATIONSHIPS
# ============================================================================

DEMO_NODES = [
    # --- Microservices ---
    {
        "id": "art-gw",
        "name": "ApiGateway",
        "qualified_name": "gateway.routes.api_gateway",
        "artifact_type": "GATEWAY",
        "category": "service",
        "layer": "GATEWAY",
        "location": "gateway/router.py:15-120",
        "file_path": "gateway/router.py",
        "line_start": 15,
        "line_end": 120,
        "language": "python",
        "in_degree": 0,
        "out_degree": 4,
        "is_leaf": False,
        "is_test_entity": False,
        "description": "Central reverse proxy, SSL termination, and rate-limiting ingress gateway.",
        "provenance": "STATIC_EXTRACTED",
        "evidence_status": "VERIFIED_AST",
        "tier": 1,
    },
    {
        "id": "art-auth",
        "name": "AuthService",
        "qualified_name": "services.auth.AuthService",
        "artifact_type": "SERVICE",
        "category": "service",
        "layer": "CORE_SERVICE",
        "location": "services/auth_service.py:10-95",
        "file_path": "services/auth_service.py",
        "line_start": 10,
        "line_end": 95,
        "language": "python",
        "in_degree": 1,
        "out_degree": 1,
        "is_leaf": False,
        "is_test_entity": False,
        "description": "JWT authentication, RBAC authorization, and password hashing service.",
        "provenance": "STATIC_EXTRACTED",
        "evidence_status": "VERIFIED_AST",
        "tier": 2,
    },
    {
        "id": "art-prod",
        "name": "ProductService",
        "qualified_name": "services.products.ProductService",
        "artifact_type": "SERVICE",
        "category": "service",
        "layer": "CORE_SERVICE",
        "location": "services/product_service.py:12-140",
        "file_path": "services/product_service.py",
        "line_start": 12,
        "line_end": 140,
        "language": "python",
        "in_degree": 1,
        "out_degree": 1,
        "is_leaf": False,
        "is_test_entity": False,
        "description": "Product catalog queries, search filtering, and pricing lookup.",
        "provenance": "STATIC_EXTRACTED",
        "evidence_status": "VERIFIED_AST",
        "tier": 2,
    },
    {
        "id": "art-order",
        "name": "OrderService",
        "qualified_name": "services.orders.OrderService",
        "artifact_type": "SERVICE",
        "category": "service",
        "layer": "CORE_SERVICE",
        "location": "services/order_service.py:18-185",
        "file_path": "services/order_service.py",
        "line_start": 18,
        "line_end": 185,
        "language": "python",
        "in_degree": 2,
        "out_degree": 3,
        "is_leaf": False,
        "is_test_entity": False,
        "description": "Orchestrates order creation, checkout state machine, and fulfillment.",
        "provenance": "STATIC_EXTRACTED",
        "evidence_status": "VERIFIED_AST",
        "tier": 2,
    },
    {
        "id": "art-payment",
        "name": "PaymentService",
        "qualified_name": "services.payment.PaymentService",
        "artifact_type": "SERVICE",
        "category": "service",
        "layer": "PAYMENT_INTEGRATION",
        "location": "services/payment_service.py:14-165",
        "file_path": "services/payment_service.py",
        "line_start": 14,
        "line_end": 165,
        "language": "python",
        "in_degree": 2,
        "out_degree": 1,
        "is_leaf": False,
        "is_test_entity": False,
        "description": "Processes credit card charges, transaction fees, and refund lifecycle.",
        "provenance": "STATIC_EXTRACTED",
        "evidence_status": "VERIFIED_AST",
        "tier": 3,
    },
    {
        "id": "art-inventory",
        "name": "InventoryService",
        "qualified_name": "services.inventory.InventoryService",
        "artifact_type": "SERVICE",
        "category": "service",
        "layer": "CORE_SERVICE",
        "location": "services/inventory_service.py:8-110",
        "file_path": "services/inventory_service.py",
        "line_start": 8,
        "line_end": 110,
        "language": "python",
        "in_degree": 1,
        "out_degree": 1,
        "is_leaf": False,
        "is_test_entity": False,
        "description": "Manages warehouse stock reservations and inventory level decrementing.",
        "provenance": "STATIC_EXTRACTED",
        "evidence_status": "VERIFIED_AST",
        "tier": 3,
    },

    # --- API Endpoints ---
    {
        "id": "art-ep-auth",
        "name": "POST /api/v1/auth/token",
        "qualified_name": "api.endpoints.auth_token",
        "artifact_type": "API_ENDPOINT",
        "category": "api",
        "layer": "API_LAYER",
        "location": "api/auth.py:20-55",
        "file_path": "api/auth.py",
        "line_start": 20,
        "line_end": 55,
        "language": "python",
        "in_degree": 1,
        "out_degree": 1,
        "is_leaf": False,
        "is_test_entity": False,
        "description": "Authenticates user credentials and issues bearer JWT tokens.",
        "provenance": "STATIC_EXTRACTED",
        "evidence_status": "VERIFIED_AST",
        "tier": 1,
    },
    {
        "id": "art-ep-prod",
        "name": "GET /api/v1/products/{id}",
        "qualified_name": "api.endpoints.get_product",
        "artifact_type": "API_ENDPOINT",
        "category": "api",
        "layer": "API_LAYER",
        "location": "api/products.py:15-40",
        "file_path": "api/products.py",
        "line_start": 15,
        "line_end": 40,
        "language": "python",
        "in_degree": 1,
        "out_degree": 1,
        "is_leaf": False,
        "is_test_entity": False,
        "description": "Retrieves product item details and active catalog pricing.",
        "provenance": "STATIC_EXTRACTED",
        "evidence_status": "VERIFIED_AST",
        "tier": 1,
    },
    {
        "id": "art-ep-orders",
        "name": "POST /api/v1/orders",
        "qualified_name": "api.endpoints.create_order",
        "artifact_type": "API_ENDPOINT",
        "category": "api",
        "layer": "API_LAYER",
        "location": "api/orders.py:25-70",
        "file_path": "api/orders.py",
        "line_start": 25,
        "line_end": 70,
        "language": "python",
        "in_degree": 1,
        "out_degree": 1,
        "is_leaf": False,
        "is_test_entity": False,
        "description": "Places a pending customer order and validates cart items.",
        "provenance": "STATIC_EXTRACTED",
        "evidence_status": "VERIFIED_AST",
        "tier": 1,
    },
    {
        "id": "art-ep-checkout",
        "name": "POST /api/v1/checkout",
        "qualified_name": "api.endpoints.checkout_flow",
        "artifact_type": "API_ENDPOINT",
        "category": "api",
        "layer": "API_LAYER",
        "location": "api/checkout.py:30-85",
        "file_path": "api/checkout.py",
        "line_start": 30,
        "line_end": 85,
        "language": "python",
        "in_degree": 1,
        "out_degree": 1,
        "is_leaf": False,
        "is_test_entity": False,
        "description": "Orchestrates order finalization, stock decrement, and payment capture.",
        "provenance": "STATIC_EXTRACTED",
        "evidence_status": "VERIFIED_AST",
        "tier": 1,
    },
    {
        "id": "art-ep-pay",
        "name": "POST /api/v1/payments/charge",
        "qualified_name": "api.endpoints.charge_payment",
        "artifact_type": "API_ENDPOINT",
        "category": "api",
        "layer": "API_LAYER",
        "location": "api/payment.py:18-60",
        "file_path": "api/payment.py",
        "line_start": 18,
        "line_end": 60,
        "language": "python",
        "in_degree": 0,
        "out_degree": 1,
        "is_leaf": False,
        "is_test_entity": False,
        "description": "Direct payment gateway charge endpoint called by external webhooks or checkout.",
        "provenance": "STATIC_EXTRACTED",
        "evidence_status": "VERIFIED_AST",
        "tier": 2,
    },

    # --- Database Entities ---
    {
        "id": "art-db-users",
        "name": "users_table",
        "qualified_name": "database.tables.users",
        "artifact_type": "DATABASE_ENTITY",
        "category": "database",
        "layer": "DATA_PERSISTENCE",
        "location": "schema/users.sql:1-35",
        "file_path": "schema/users.sql",
        "line_start": 1,
        "line_end": 35,
        "language": "sql",
        "in_degree": 1,
        "out_degree": 0,
        "is_leaf": True,
        "is_test_entity": False,
        "description": "PostgreSQL relational table storing user credentials, roles, and profiles.",
        "provenance": "STATIC_EXTRACTED",
        "evidence_status": "VERIFIED_AST",
        "tier": 4,
    },
    {
        "id": "art-db-products",
        "name": "products_table",
        "qualified_name": "database.tables.products",
        "artifact_type": "DATABASE_ENTITY",
        "category": "database",
        "layer": "DATA_PERSISTENCE",
        "location": "schema/products.sql:1-40",
        "file_path": "schema/products.sql",
        "line_start": 1,
        "line_end": 40,
        "language": "sql",
        "in_degree": 1,
        "out_degree": 0,
        "is_leaf": True,
        "is_test_entity": False,
        "description": "PostgreSQL relational table storing SKU items, prices, and categories.",
        "provenance": "STATIC_EXTRACTED",
        "evidence_status": "VERIFIED_AST",
        "tier": 4,
    },
    {
        "id": "art-db-orders",
        "name": "orders_table",
        "qualified_name": "database.tables.orders",
        "artifact_type": "DATABASE_ENTITY",
        "category": "database",
        "layer": "DATA_PERSISTENCE",
        "location": "schema/orders.sql:1-50",
        "file_path": "schema/orders.sql",
        "line_start": 1,
        "line_end": 50,
        "language": "sql",
        "in_degree": 1,
        "out_degree": 0,
        "is_leaf": True,
        "is_test_entity": False,
        "description": "PostgreSQL relational table storing customer orders and transaction states.",
        "provenance": "STATIC_EXTRACTED",
        "evidence_status": "VERIFIED_AST",
        "tier": 4,
    },
    {
        "id": "art-db-payments",
        "name": "payments_table",
        "qualified_name": "database.tables.payments",
        "artifact_type": "DATABASE_ENTITY",
        "category": "database",
        "layer": "DATA_PERSISTENCE",
        "location": "schema/payments.sql:1-45",
        "file_path": "schema/payments.sql",
        "line_start": 1,
        "line_end": 45,
        "language": "sql",
        "in_degree": 1,
        "out_degree": 0,
        "is_leaf": True,
        "is_test_entity": False,
        "description": "PostgreSQL ledger storing transaction tokens, fees, and charge logs.",
        "provenance": "STATIC_EXTRACTED",
        "evidence_status": "VERIFIED_AST",
        "tier": 4,
    },
    {
        "id": "art-db-inventory",
        "name": "inventory_table",
        "qualified_name": "database.tables.inventory",
        "artifact_type": "DATABASE_ENTITY",
        "category": "database",
        "layer": "DATA_PERSISTENCE",
        "location": "schema/inventory.sql:1-30",
        "file_path": "schema/inventory.sql",
        "line_start": 1,
        "line_end": 30,
        "language": "sql",
        "in_degree": 1,
        "out_degree": 0,
        "is_leaf": True,
        "is_test_entity": False,
        "description": "PostgreSQL inventory ledger storing available warehouse units per SKU.",
        "provenance": "STATIC_EXTRACTED",
        "evidence_status": "VERIFIED_AST",
        "tier": 4,
    },

    # --- Test Entities ---
    {
        "id": "art-test-payment-proc",
        "name": "test_process_payment",
        "qualified_name": "tests.test_payment.test_process_payment",
        "artifact_type": "TEST_CASE",
        "category": "test",
        "layer": "TEST_SUITE",
        "location": "tests/test_payment.py:15-45",
        "file_path": "tests/test_payment.py",
        "line_start": 15,
        "line_end": 45,
        "language": "python",
        "in_degree": 0,
        "out_degree": 1,
        "is_leaf": True,
        "is_test_entity": True,
        "description": "Unit and integration test verifying charge execution and token handoff.",
        "provenance": "STATIC_EXTRACTED",
        "evidence_status": "VERIFIED_AST",
        "tier": 3,
    },
    {
        "id": "art-test-payment-fees",
        "name": "test_calculate_fees",
        "qualified_name": "tests.test_payment.test_calculate_fees",
        "artifact_type": "TEST_CASE",
        "category": "test",
        "layer": "TEST_SUITE",
        "location": "tests/test_payment.py:50-80",
        "file_path": "tests/test_payment.py",
        "line_start": 50,
        "line_end": 80,
        "language": "python",
        "in_degree": 0,
        "out_degree": 1,
        "is_leaf": True,
        "is_test_entity": True,
        "description": "Unit test verifying standard processing fee computation formulas.",
        "provenance": "STATIC_EXTRACTED",
        "evidence_status": "VERIFIED_AST",
        "tier": 3,
    },
    {
        "id": "art-test-orders",
        "name": "test_order_creation_flow",
        "qualified_name": "tests.test_orders.test_order_creation_flow",
        "artifact_type": "TEST_CASE",
        "category": "test",
        "layer": "TEST_SUITE",
        "location": "tests/test_orders.py:20-65",
        "file_path": "tests/test_orders.py",
        "line_start": 20,
        "line_end": 65,
        "language": "python",
        "in_degree": 0,
        "out_degree": 1,
        "is_leaf": True,
        "is_test_entity": True,
        "description": "End-to-end integration test verifying order checkout pipeline.",
        "provenance": "STATIC_EXTRACTED",
        "evidence_status": "VERIFIED_AST",
        "tier": 2,
    },
    {
        "id": "art-test-inventory",
        "name": "test_stock_reservation",
        "qualified_name": "tests.test_inventory.test_stock_reservation",
        "artifact_type": "TEST_CASE",
        "category": "test",
        "layer": "TEST_SUITE",
        "location": "tests/test_inventory.py:10-40",
        "file_path": "tests/test_inventory.py",
        "line_start": 10,
        "line_end": 40,
        "language": "python",
        "in_degree": 0,
        "out_degree": 1,
        "is_leaf": True,
        "is_test_entity": True,
        "description": "Concurrency test verifying atomic stock lock under load.",
        "provenance": "STATIC_EXTRACTED",
        "evidence_status": "VERIFIED_AST",
        "tier": 3,
    },
    {
        "id": "art-test-auth",
        "name": "test_jwt_validation",
        "qualified_name": "tests.test_auth.test_jwt_validation",
        "artifact_type": "TEST_CASE",
        "category": "test",
        "layer": "TEST_SUITE",
        "location": "tests/test_auth.py:12-48",
        "file_path": "tests/test_auth.py",
        "line_start": 12,
        "line_end": 48,
        "language": "python",
        "in_degree": 0,
        "out_degree": 1,
        "is_leaf": True,
        "is_test_entity": True,
        "description": "Security test asserting token expiration and signature tampering rejection.",
        "provenance": "STATIC_EXTRACTED",
        "evidence_status": "VERIFIED_AST",
        "tier": 2,
    },
    {
        "id": "art-test-gw",
        "name": "test_rate_limiting",
        "qualified_name": "tests.test_gateway.test_rate_limiting",
        "artifact_type": "TEST_CASE",
        "category": "test",
        "layer": "TEST_SUITE",
        "location": "tests/test_gateway.py:15-50",
        "file_path": "tests/test_gateway.py",
        "line_start": 15,
        "line_end": 50,
        "language": "python",
        "in_degree": 0,
        "out_degree": 1,
        "is_leaf": True,
        "is_test_entity": True,
        "description": "Traffic test verifying IP token bucket rate-limiting at gateway.",
        "provenance": "STATIC_EXTRACTED",
        "evidence_status": "VERIFIED_AST",
        "tier": 1,
    },
]

DEMO_EDGES = [
    # Gateway Routes
    {"id": "rel-1", "source": "art-gw", "target": "art-ep-auth", "type": "ROUTES_TO", "provenance": "STATIC_EXTRACTED", "status": "VERIFIED_AST"},
    {"id": "rel-2", "source": "art-gw", "target": "art-ep-prod", "type": "ROUTES_TO", "provenance": "STATIC_EXTRACTED", "status": "VERIFIED_AST"},
    {"id": "rel-3", "source": "art-gw", "target": "art-ep-orders", "type": "ROUTES_TO", "provenance": "STATIC_EXTRACTED", "status": "VERIFIED_AST"},
    {"id": "rel-4", "source": "art-gw", "target": "art-ep-checkout", "type": "ROUTES_TO", "provenance": "STATIC_EXTRACTED", "status": "VERIFIED_AST"},

    # API Handlers Call Services
    {"id": "rel-5", "source": "art-ep-auth", "target": "art-auth", "type": "CALLS", "provenance": "STATIC_EXTRACTED", "status": "VERIFIED_AST"},
    {"id": "rel-6", "source": "art-ep-prod", "target": "art-prod", "type": "CALLS", "provenance": "STATIC_EXTRACTED", "status": "VERIFIED_AST"},
    {"id": "rel-7", "source": "art-ep-orders", "target": "art-order", "type": "CALLS", "provenance": "STATIC_EXTRACTED", "status": "VERIFIED_AST"},
    {"id": "rel-8", "source": "art-ep-checkout", "target": "art-order", "type": "CALLS", "provenance": "STATIC_EXTRACTED", "status": "VERIFIED_AST"},
    {"id": "rel-9", "source": "art-ep-pay", "target": "art-payment", "type": "CALLS", "provenance": "STATIC_EXTRACTED", "status": "VERIFIED_AST"},

    # Inter-Service Communication
    {"id": "rel-10", "source": "art-order", "target": "art-payment", "type": "CALLS", "provenance": "STATIC_EXTRACTED", "status": "VERIFIED_AST"},
    {"id": "rel-11", "source": "art-order", "target": "art-inventory", "type": "CALLS", "provenance": "STATIC_EXTRACTED", "status": "VERIFIED_AST"},

    # Database Persistence
    {"id": "rel-12", "source": "art-auth", "target": "art-db-users", "type": "STORES_IN", "provenance": "STATIC_EXTRACTED", "status": "VERIFIED_AST"},
    {"id": "rel-13", "source": "art-prod", "target": "art-db-products", "type": "STORES_IN", "provenance": "STATIC_EXTRACTED", "status": "VERIFIED_AST"},
    {"id": "rel-14", "source": "art-order", "target": "art-db-orders", "type": "STORES_IN", "provenance": "STATIC_EXTRACTED", "status": "VERIFIED_AST"},
    {"id": "rel-15", "source": "art-payment", "target": "art-db-payments", "type": "STORES_IN", "provenance": "STATIC_EXTRACTED", "status": "VERIFIED_AST"},
    {"id": "rel-16", "source": "art-inventory", "target": "art-db-inventory", "type": "STORES_IN", "provenance": "STATIC_EXTRACTED", "status": "VERIFIED_AST"},

    # Test Coverage Edges
    {"id": "rel-17", "source": "art-test-payment-proc", "target": "art-payment", "type": "TESTS", "provenance": "STATIC_EXTRACTED", "status": "VERIFIED_AST"},
    {"id": "rel-18", "source": "art-test-payment-fees", "target": "art-payment", "type": "TESTS", "provenance": "STATIC_EXTRACTED", "status": "VERIFIED_AST"},
    {"id": "rel-19", "source": "art-test-orders", "target": "art-order", "type": "TESTS", "provenance": "STATIC_EXTRACTED", "status": "VERIFIED_AST"},
    {"id": "rel-20", "source": "art-test-inventory", "target": "art-inventory", "type": "TESTS", "provenance": "STATIC_EXTRACTED", "status": "VERIFIED_AST"},
    {"id": "rel-21", "source": "art-test-auth", "target": "art-auth", "type": "TESTS", "provenance": "STATIC_EXTRACTED", "status": "VERIFIED_AST"},
    {"id": "rel-22", "source": "art-test-gw", "target": "art-gw", "type": "TESTS", "provenance": "STATIC_EXTRACTED", "status": "VERIFIED_AST"},
]


# ============================================================================
# 3. DETERMINISTIC GRAPH TRAVERSAL & BLAST RADIUS ENGINE
# ============================================================================

class DemoGraphEngine:
    def __init__(self):
        self.nodes_by_id = {n["id"]: n for n in DEMO_NODES}
        self.nodes_by_name = {n["name"]: n for n in DEMO_NODES}
        self.nodes_by_qual = {n["qualified_name"]: n for n in DEMO_NODES}

        # Build adjacency maps:
        # forward: who does node call? (source -> targets)
        # reverse: who calls node? (target -> sources)
        self.forward_edges: Dict[str, List[Dict[str, Any]]] = {}
        self.reverse_edges: Dict[str, List[Dict[str, Any]]] = {}

        for edge in DEMO_EDGES:
            src = edge["source"]
            tgt = edge["target"]
            self.forward_edges.setdefault(src, []).append(edge)
            self.reverse_edges.setdefault(tgt, []).append(edge)

    def resolve_entity(self, identifier: str) -> Optional[Dict[str, Any]]:
        return (
            self.nodes_by_id.get(identifier) or
            self.nodes_by_qual.get(identifier) or
            self.nodes_by_name.get(identifier)
        )

    def compute_blast_radius(self, root_identifier: str) -> Dict[str, Any]:
        """
        Computes caller reachability blast radius starting from root_identifier.
        Traverses reverse edges (callers) to discover directly and indirectly affected entities.
        """
        root = self.resolve_entity(root_identifier)
        if not root:
            return {
                "status": "UNRESOLVED_TARGET",
                "message": f"Target entity '{root_identifier}' could not be resolved in the sample graph.",
                "root_entity": None,
                "directly_affected": [],
                "indirectly_affected": [],
                "affected_apis": [],
                "affected_tests": [],
                "propagation_paths": [],
                "excluded_entities": [],
                "blast_radius_score": 0.0,
            }

        root_id = root["id"]
        # Breadth-first caller traversal (who depends on root?)
        visited_depths: Dict[str, int] = {root_id: 0}
        propagation_paths: List[List[str]] = []
        queue = [(root_id, [root["qualified_name"]], 0)]

        while queue:
            curr_id, curr_path, curr_depth = queue.pop(0)
            inbound_edges = self.reverse_edges.get(curr_id, [])
            for edge in inbound_edges:
                caller_id = edge["source"]
                caller_node = self.nodes_by_id.get(caller_id)
                if not caller_node:
                    continue

                new_depth = curr_depth + 1
                new_path = [caller_node["qualified_name"]] + curr_path

                if caller_id not in visited_depths:
                    visited_depths[caller_id] = new_depth
                    propagation_paths.append(new_path)
                    queue.append((caller_id, new_path, new_depth))
                elif new_depth < visited_depths[caller_id]:
                    visited_depths[caller_id] = new_depth

        directly_affected = []
        indirectly_affected = []
        affected_apis = []
        affected_tests = []

        for node_id, depth in visited_depths.items():
            if depth == 0:
                continue
            node = self.nodes_by_id[node_id]
            node_qual = node["qualified_name"]
            item = {
                "id": node["id"],
                "name": node["name"],
                "qualified_name": node_qual,
                "artifact_type": node["artifact_type"],
                "depth": depth,
                "location": node["location"],
                "causal_reason": f"Transitively depends on '{root['name']}' at call depth {depth}."
            }

            if depth == 1:
                directly_affected.append(item)
            else:
                indirectly_affected.append(item)

            if node["artifact_type"] == "API_ENDPOINT":
                affected_apis.append(node_qual)
            elif node["artifact_type"] == "TEST_CASE":
                affected_tests.append(node_qual)

        # Compute excluded entities with explicit exclusion reasons
        excluded_entities = []
        all_visited = set(visited_depths.keys())
        for node in DEMO_NODES:
            if node["id"] not in all_visited:
                reason = "Independent architectural layer with 0 reachable dependency edges to target."
                if node["category"] == "test":
                    reason = "Test suite targets an unaffected component outside the blast radius."
                elif node["category"] == "database":
                    reason = "Database table persistence is isolated and uncoupled from this service."
                excluded_entities.append({
                    "id": node["id"],
                    "name": node["name"],
                    "qualified_name": node["qualified_name"],
                    "artifact_type": node["artifact_type"],
                    "exclusion_reason": reason
                })

        # Calculate exact risk score
        total_affected = len(directly_affected) + len(indirectly_affected)
        structural_score = min(total_affected * 10.0, 60.0)
        api_penalty = len(affected_apis) * 15.0
        risk_score = min(round(structural_score + api_penalty, 1), 100.0)

        risk_level = "LOW"
        if risk_score > 75:
            risk_level = "CRITICAL"
        elif risk_score > 50:
            risk_level = "HIGH"
        elif risk_score > 25:
            risk_level = "MEDIUM"

        return {
            "status": "VERIFIED_ZERO_IMPACT" if total_affected == 0 else "DOWNSTREAM_IMPACT_DETECTED",
            "root_entity": root,
            "total_affected": total_affected,
            "directly_affected": directly_affected,
            "indirectly_affected": indirectly_affected,
            "affected_apis": affected_apis,
            "affected_tests": affected_tests,
            "propagation_paths": propagation_paths,
            "excluded_entities": excluded_entities,
            "max_depth": max(visited_depths.values()) if visited_depths else 0,
            "blast_radius_score": risk_score,
            "risk_level": risk_level,
            "risk_formula": f"Risk Score ({risk_score:.1f}/100) = Structural Affected ({structural_score:.1f}) + API Exposure ({api_penalty:.1f})"
        }


# ============================================================================
# 4. DETERMINISTIC WHAT-IF SCENARIOS
# ============================================================================

DEMO_SCENARIOS = {
    "SCENARIO_SERVICE_OUTAGE": {
        "id": "SCENARIO_SERVICE_OUTAGE",
        "title": "Payment Service Cluster Outage",
        "mutation_type": "SERVICE_OUTAGE",
        "target": "services.payment.PaymentService",
        "description": "Simulates complete downtime (HTTP 503 Service Unavailable) of PaymentService cluster.",
        "target_entity": "art-payment",
        "baseline_isolation": "Hypothetical virtual twin created; baseline snapshot remains unchanged.",
        "structural_consequences": [
            "Severs payment fee calculation and charge execution.",
            "OrderService cannot complete checkout step and enters degraded state.",
            "POST /api/v1/checkout and POST /api/v1/payments/charge return 503 errors.",
            "ApiGateway reports elevated latency and downstream gateway timeouts."
        ],
        "risk_breakdown": {
            "structural_impact_score": 35.0,
            "guardrail_penalty": 20.0,
            "test_coverage_penalty": 15.0,
            "incident_history_penalty": 0.0,
            "overall_score": 70.0,
            "risk_level": "HIGH",
            "explanation": "Overall score 70.0/100 = Structural Blast (35.0) + Guardrails (20.0) + Test Gap (15.0) + Incident History (0.0)"
        },
        "recommended_verification": [
            "pytest tests/test_payment.py to verify fallback and graceful degradation",
            "pytest tests/test_orders.py -k 'test_order_creation_flow'",
            "Verify circuit-breaker configuration in gateway/router.py"
        ],
        "limitations": [
            "Does not simulate cloud infrastructure autoscaling latency.",
            "Assumes stationary traffic without client-side retry storms."
        ]
    },
    "SCENARIO_API_CONTRACT_CHANGE": {
        "id": "SCENARIO_API_CONTRACT_CHANGE",
        "title": "Payment API Contract Currency & Idempotency Expansion",
        "mutation_type": "MODIFY_API",
        "target": "api.endpoints.charge_payment",
        "description": "Modifies POST /api/v1/payments/charge to strictly require 'idempotency_key' and ISO 'currency' headers.",
        "target_entity": "art-ep-pay",
        "baseline_isolation": "Evaluated against virtual twin with updated OpenAPI contract schema.",
        "structural_consequences": [
            "OrderService checkout integration must supply idempotency key.",
            "Legacy client integrations calling charge without currency parameter will receive 422 Unprocessable Entity."
        ],
        "risk_breakdown": {
            "structural_impact_score": 25.0,
            "guardrail_penalty": 10.0,
            "test_coverage_penalty": 10.0,
            "incident_history_penalty": 0.0,
            "overall_score": 45.0,
            "risk_level": "MEDIUM",
            "explanation": "Overall score 45.0/100 = Structural Blast (25.0) + Guardrails (10.0) + Test Gap (10.0) + Incident History (0.0)"
        },
        "recommended_verification": [
            "pytest tests/test_payment.py::test_process_payment",
            "Verify schema contract validation against frontend client specs"
        ],
        "limitations": [
            "Static analysis cannot detect untyped mobile app clients using dynamic JSON payloads."
        ]
    },
    "SCENARIO_COMPONENT_REMOVAL": {
        "id": "SCENARIO_COMPONENT_REMOVAL",
        "title": "Legacy Payment Adapter Deprecation & Removal",
        "mutation_type": "REMOVE_COMPONENT",
        "target": "tests.test_payment.test_calculate_fees",
        "description": "Simulates removal of an isolated test artifact or decommissioned legacy module.",
        "target_entity": "art-test-payment-fees",
        "baseline_isolation": "Target is removed in virtual twin; all callers inspected.",
        "structural_consequences": [
            "Verified Zero Downstream Impact: Target has in-degree of 0 (no production services call this test artifact).",
            "No breaking changes propagated to production APIs or services."
        ],
        "risk_breakdown": {
            "structural_impact_score": 0.0,
            "guardrail_penalty": 0.0,
            "test_coverage_penalty": 15.0,
            "incident_history_penalty": 0.0,
            "overall_score": 15.0,
            "risk_level": "LOW",
            "explanation": "Overall score 15.0/100 = Structural Blast (0.0) + Guardrails (0.0) + Test Coverage Gap (15.0) + Incident History (0.0)"
        },
        "recommended_verification": [
            "pytest tests/test_payment.py to confirm remaining test suites pass"
        ],
        "limitations": [
            "In-degree is 0 in local repository twin. External test runners are outside current snapshot boundary."
        ]
    },
    "SCENARIO_SCHEMA_MIGRATION": {
        "id": "SCENARIO_SCHEMA_MIGRATION",
        "title": "Payment Ledger Table Schema Migration",
        "mutation_type": "SCHEMA_MIGRATION",
        "target": "database.tables.payments",
        "description": "Simulates column alteration: drops 'raw_card_token' and adds 'tokenized_vault_id' (NOT NULL).",
        "target_entity": "art-db-payments",
        "baseline_isolation": "Virtual schema diff generated; baseline SQL DDL stationary.",
        "structural_consequences": [
            "PaymentService persistence methods must populate tokenized_vault_id.",
            "Unmigrated inserts will trigger SQL constraint violations."
        ],
        "risk_breakdown": {
            "structural_impact_score": 30.0,
            "guardrail_penalty": 20.0,
            "test_coverage_penalty": 10.0,
            "incident_history_penalty": 0.0,
            "overall_score": 60.0,
            "risk_level": "HIGH",
            "explanation": "Overall score 60.0/100 = Structural Blast (30.0) + Guardrails (20.0) + Test Gap (10.0) + Incident History (0.0)"
        },
        "recommended_verification": [
            "Run migration rollback verification script",
            "pytest tests/test_payment.py::test_process_payment"
        ],
        "limitations": [
            "Database triggers and stored procedures cannot be inferred without full database DDL index."
        ]
    }
}


# ============================================================================
# 5. DETERMINISTIC TEST IMPACT MATRIX
# ============================================================================

DEMO_TEST_RESULTS = {
    "SCENARIO_SERVICE_OUTAGE": {
        "suggested_tests": [
            {"test_name": "tests.test_payment.test_process_payment", "location": "tests/test_payment.py:15", "target": "PaymentService", "selection_reason": "Direct caller of PaymentService"},
            {"test_name": "tests.test_payment.test_calculate_fees", "location": "tests/test_payment.py:50", "target": "PaymentService", "selection_reason": "Direct unit test for PaymentService"},
            {"test_name": "tests.test_orders.test_order_creation_flow", "location": "tests/test_orders.py:20", "target": "OrderService", "selection_reason": "Downstream caller (depth 2)"},
        ],
        "selected_tests": [
            "tests.test_payment.test_process_payment",
            "tests.test_payment.test_calculate_fees",
            "tests.test_orders.test_order_creation_flow",
        ],
        "executed_tests": [
            {"test_name": "tests.test_payment.test_process_payment", "status": "FAILED", "duration_ms": 32, "failure_message": "ServiceUnavailableError: PaymentService cluster unreachable during charge", "provenance": "DETERMINISTIC_SIMULATED_RUN"},
            {"test_name": "tests.test_payment.test_calculate_fees", "status": "PASSED", "duration_ms": 14, "failure_message": None, "provenance": "DETERMINISTIC_SIMULATED_RUN"},
            {"test_name": "tests.test_orders.test_order_creation_flow", "status": "FAILED", "duration_ms": 58, "failure_message": "PaymentDependencyException: Downstream payment returned 503", "provenance": "DETERMINISTIC_SIMULATED_RUN"},
        ],
        "unexecuted_tests": [
            {"test_name": "tests.test_auth.test_jwt_validation", "reason": "Excluded: AuthService outside blast radius (0 reachable paths)"},
            {"test_name": "tests.test_inventory.test_stock_reservation", "reason": "Excluded: InventoryService unaffected by PaymentService outage"},
            {"test_name": "tests.test_gateway.test_rate_limiting", "reason": "Excluded: Rate limiting logic decoupled from backend service availability"}
        ],
        "execution_summary": {
            "total_suggested": 3,
            "total_executed": 3,
            "passed": 1,
            "failed": 2,
            "skipped": 3,
            "pass_rate_percentage": 33.3,
            "is_precomputed_demo_data": True
        }
    }
}


# ============================================================================
# 6. ARCHITECTURAL EXTENSION POINTS SPECIFICATION
# ============================================================================

DEMO_EXTENSION_POINTS = [
    {
        "id": "ext-multi-repo",
        "name": "Cross-Repository & Distributed Twin Mesh",
        "status": "ARCHITECTURAL_EXTENSION_POINT",
        "description": "Federate across multiple microservice repositories (e.g., separate payment, auth, and order git repos) using contract schemas and remote graph edges.",
        "supported_protocols": ["gRPC Reflection", "OpenAPI Mesh", "AsyncAPI Schema Registry"],
        "is_active_in_demo": False
    },
    {
        "id": "ext-pr-commit-diff",
        "name": "Pull Request & Commit Comparison",
        "status": "ARCHITECTURAL_EXTENSION_POINT",
        "description": "Analyze GitHub and GitLab pull requests before merging to compute precision change impact and detect architecture drift against baseline twins.",
        "supported_protocols": ["GitHub Checks API", "GitLab Merge Request Pipeline"],
        "is_active_in_demo": False
    },
    {
        "id": "ext-ci-smart-testing",
        "name": "Change-Aware Predictive Test Selection (Smart CI)",
        "status": "ACTIVE_CAPABILITY",
        "description": "Export selective pytest and jest execution commands to CI runners, running only the 15% of tests touched by the change blast radius.",
        "supported_protocols": ["GitHub Actions Matrix", "Jenkins Pipeline", "GitLab CI"],
        "is_active_in_demo": True
    },
    {
        "id": "ext-runtime-telemetry",
        "name": "Runtime Telemetry & Trace Correlation",
        "status": "ARCHITECTURAL_EXTENSION_POINT",
        "description": "Intersect static AST blast radius with live OpenTelemetry traces and Datadog APM traffic to compute real observed invocation frequency.",
        "supported_protocols": ["OpenTelemetry OTLP", "Datadog APM API", "Prometheus Metrics"],
        "is_active_in_demo": False
    },
    {
        "id": "ext-incident-investigation",
        "name": "Historical Incident & Vulnerability Correlation",
        "status": "ARCHITECTURAL_EXTENSION_POINT",
        "description": "Query past production P1/P2 incidents and postmortems from PagerDuty and Sentry to weight risk scores for fragile legacy components.",
        "supported_protocols": ["PagerDuty Incidents API", "Sentry Issues Webhook"],
        "is_active_in_demo": False
    },
    {
        "id": "ext-multi-agent-review",
        "name": "Multi-Agent Autonomous Engineering Review",
        "status": "ACTIVE_CAPABILITY",
        "description": "TwinCore multi-agent orchestrator coordinates Security Auditor, Architect, and Reliability Engineer agents to evaluate simulation risks.",
        "supported_protocols": ["MultiAgentScenarioOrchestrator", "Pydantic Structured Output"],
        "is_active_in_demo": True
    }
]

# Singleton Demo Engine
demo_graph_engine = DemoGraphEngine()
