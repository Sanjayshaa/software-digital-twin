"""
Controlled Software Benchmark Lab — Synthetic Fixture Repository Generator.
Generates a deterministic, reproducible multi-tier Git repository fixture
(frontend components, backend routes, services, data-access layer, SQL schema,
tests, configurations, and utilities) with 12 sequential real Git commits,
tags, and release metadata.
"""

import os
import shutil
import subprocess
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass


DEFAULT_FIXTURE_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../../benchmark_cases/fixtures/synthetic_shop")
)


@dataclass
class CommitInfo:
    index: int
    commit_id: str  # e.g., "c1_initial"
    sha: str
    message: str
    tag: Optional[str] = None


class SyntheticFixtureGenerator:
    """
    Builds and manages the deterministic synthetic shop repository fixture.
    Runs strictly in an isolated workspace without modifying user branches.
    """

    def __init__(self, target_dir: str = DEFAULT_FIXTURE_PATH):
        self.target_dir = os.path.abspath(target_dir)

    def _git(self, *args: str) -> str:
        """Executes a git command inside the target repository with sanitized environment."""
        env = dict(os.environ)
        env["GIT_AUTHOR_NAME"] = "TwinCore Benchmark Lab"
        env["GIT_AUTHOR_EMAIL"] = "benchmark@twincore.local"
        env["GIT_COMMITTER_NAME"] = "TwinCore Benchmark Lab"
        env["GIT_COMMITTER_EMAIL"] = "benchmark@twincore.local"
        env["GIT_TERMINAL_PROMPT"] = "0"
        env["GIT_CONFIG_GLOBAL"] = "/dev/null"
        env["GIT_CONFIG_SYSTEM"] = "/dev/null"
        res = subprocess.run(
            ["git", *args],
            cwd=self.target_dir,
            env=env,
            capture_output=True,
            text=True,
            check=True
        )
        return res.stdout.strip()

    def _write_file(self, rel_path: str, content: str):
        full_path = os.path.join(self.target_dir, rel_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)

    def _remove_file(self, rel_path: str):
        full_path = os.path.join(self.target_dir, rel_path)
        if os.path.exists(full_path):
            os.remove(full_path)

    def generate(self, force_recreate: bool = True) -> Dict[str, Any]:
        """
        Deterministically creates the 12-commit synthetic repository.
        Returns a manifest mapping logical commit IDs to actual Git SHAs.
        """
        if force_recreate and os.path.exists(self.target_dir):
            shutil.rmtree(self.target_dir)

        os.makedirs(self.target_dir, exist_ok=True)

        # Initialize Git repo
        self._git("init", "-b", "main")
        self._git("config", "user.name", "TwinCore Benchmark Lab")
        self._git("config", "user.email", "benchmark@twincore.local")

        commits_map: Dict[str, CommitInfo] = {}

        # =====================================================================
        # COMMIT 1: Initial Architecture (Tag: v1.0.0)
        # =====================================================================
        self._write_file("schema/orders.sql", """-- Orders Database Schema
CREATE TABLE orders (
    id VARCHAR(36) PRIMARY KEY,
    customer_id VARCHAR(36) NOT NULL,
    total NUMERIC(10, 2) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE order_items (
    id VARCHAR(36) PRIMARY KEY,
    order_id VARCHAR(36) REFERENCES orders(id),
    sku VARCHAR(64) NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price NUMERIC(10, 2) NOT NULL
);
""")

        self._write_file("schema/customers.sql", """-- Customers Database Schema
CREATE TABLE customers (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
""")

        self._write_file("backend/__init__.py", "")
        self._write_file("backend/db/__init__.py", "")
        self._write_file("backend/db/order_repo.py", """from typing import Optional, Dict, Any

class OrderRepository:
    \"\"\"Data-access repository for customer orders.\"\"\"

    def save_order(self, order_data: Dict[str, Any]) -> str:
        order_id = str(order_data.get("id", "ord_new"))
        return order_id

    def find_by_id(self, order_id: str) -> Optional[Dict[str, Any]]:
        return {"id": order_id, "status": "PENDING", "total": 100.0}

    def update_status(self, order_id: str, status: str) -> bool:
        return True
""")

        self._write_file("backend/db/customer_repo.py", """from typing import Optional, Dict, Any

class CustomerRepository:
    \"\"\"Data-access repository for customer accounts.\"\"\"

    def get_customer(self, customer_id: str) -> Optional[Dict[str, Any]]:
        return {"id": customer_id, "email": "customer@example.com"}
""")

        self._write_file("backend/services/__init__.py", "")
        self._write_file("backend/services/payment_service.py", """from typing import Dict, Any
from backend.db.order_repo import OrderRepository

class PaymentService:
    \"\"\"Core payment processing and fee calculation service.\"\"\"

    def __init__(self, repo: OrderRepository = None):
        self.repo = repo or OrderRepository()

    def calculate_fees(self, amount: float) -> float:
        # Standard processing fee: 2.9% + $0.30
        return round(amount * 0.029 + 0.30, 2)

    def process_payment(self, amount: float) -> bool:
        fee = self.calculate_fees(amount)
        return amount > 0 and fee >= 0.30

    def charge(self, order_id: str, amount: float) -> bool:
        if self.process_payment(amount):
            return self.repo.update_status(order_id, "PAID")
        return False
""")

        self._write_file("backend/services/order_service.py", """from typing import Dict, Any, List
from backend.db.order_repo import OrderRepository
from backend.db.customer_repo import CustomerRepository

class OrderService:
    \"\"\"Order lifecycle orchestration service.\"\"\"

    def __init__(self, order_repo: OrderRepository = None, customer_repo: CustomerRepository = None):
        self.order_repo = order_repo or OrderRepository()
        self.customer_repo = customer_repo or CustomerRepository()

    def create_order(self, customer_id: str, total: float) -> str:
        customer = self.customer_repo.get_customer(customer_id)
        if not customer:
            raise ValueError(f"Unknown customer {customer_id}")
        return self.order_repo.save_order({"customer_id": customer_id, "total": total})

    def get_order(self, order_id: str) -> Dict[str, Any]:
        return self.order_repo.find_by_id(order_id)
""")

        self._write_file("backend/api/__init__.py", "")
        self._write_file("backend/api/checkout.py", """from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.services.order_service import OrderService
from backend.services.payment_service import PaymentService

router = APIRouter()
order_svc = OrderService()
payment_svc = PaymentService()

class CheckoutRequest(BaseModel):
    customer_id: str
    total: float

@router.post("/api/checkout")
def checkout_endpoint(req: CheckoutRequest):
    order_id = order_svc.create_order(req.customer_id, req.total)
    success = payment_svc.charge(order_id, req.total)
    if not success:
        raise HTTPException(status_code=400, detail="Payment failed")
    return {"order_id": order_id, "status": "CONFIRMED"}
""")

        self._write_file("backend/api/payment.py", """from fastapi import APIRouter
from pydantic import BaseModel
from backend.services.payment_service import PaymentService

router = APIRouter()
payment_svc = PaymentService()

class PaymentRequest(BaseModel):
    amount: float

@router.post("/api/payment")
def process_payment_endpoint(req: PaymentRequest):
    success = payment_svc.process_payment(req.amount)
    return {"success": success, "fee": payment_svc.calculate_fees(req.amount)}
""")

        self._write_file("backend/api/orders.py", """from fastapi import APIRouter
from backend.services.order_service import OrderService

router = APIRouter()
order_svc = OrderService()

@router.get("/api/orders/{order_id}")
def get_order_endpoint(order_id: str):
    return order_svc.get_order(order_id)
""")

        self._write_file("frontend/src/components/Checkout.tsx", """import React from "react";
import { PaymentWidget } from "./PaymentWidget";
import { OrderSummary } from "./OrderSummary";

export const Checkout: React.FC = () => {
    const handleCheckout = async () => {
        const resp = await fetch("/api/checkout", {
            method: "POST",
            body: JSON.stringify({ customer_id: "c1", total: 99.0 })
        });
        return resp.json();
    };

    return (
        <div className="checkout-container">
            <h1>Store Checkout</h1>
            <OrderSummary />
            <PaymentWidget onPay={handleCheckout} />
        </div>
    );
};
""")

        self._write_file("frontend/src/components/PaymentWidget.tsx", """import React from "react";

export interface PaymentWidgetProps {
    onPay?: () => void;
}

export const PaymentWidget: React.FC<PaymentWidgetProps> = ({ onPay }) => {
    const submitPayment = async (amount: number) => {
        const res = await fetch("/api/payment", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ amount })
        });
        if (onPay) onPay();
        return res.json();
    };

    return (
        <button onClick={() => submitPayment(100.0)}>
            Pay Now
        </button>
    );
};
""")

        self._write_file("frontend/src/components/OrderSummary.tsx", """import React, { useEffect, useState } from "react";

export const OrderSummary: React.FC = () => {
    const [order, setOrder] = useState<any>(null);

    useEffect(() => {
        fetch("/api/orders/ord_123")
            .then(r => r.json())
            .then(data => setOrder(data));
    }, []);

    return (
        <div className="order-summary">
            <h3>Order Details</h3>
            <p>Status: {order?.status || "Loading"}</p>
        </div>
    );
};
""")

        # Negative control utility: entirely unrelated to payment or checkout
        self._write_file("utils/__init__.py", "")
        self._write_file("utils/formatting.py", """def format_currency(amount: float) -> str:
    \"\"\"Formats a float amount into USD currency string.\"\"\"
    return f"${amount:,.2f}"

def format_date(timestamp_epoch: float) -> str:
    \"\"\"Formats epoch timestamp into ISO 8601 string.\"\"\"
    import datetime
    return datetime.datetime.fromtimestamp(timestamp_epoch, datetime.timezone.utc).isoformat()
""")

        self._write_file("utils/math_helpers.py", """def round_cents(val: float) -> float:
    \"\"\"Rounds value to 2 decimal places.\"\"\"
    return round(val, 2)
""")

        self._write_file("utils/legacy_tax.py", """def compute_legacy_tax(subtotal: float) -> float:
    \"\"\"Legacy flat-rate tax calculation.\"\"\"
    return round(subtotal * 0.08, 2)
""")

        self._write_file("tests/__init__.py", "")
        self._write_file("tests/test_payment.py", """from backend.services.payment_service import PaymentService

def test_calculate_fees():
    svc = PaymentService()
    assert svc.calculate_fees(100.0) == 3.20

def test_process_payment():
    svc = PaymentService()
    assert svc.process_payment(50.0) is True
    assert svc.process_payment(-10.0) is False
""")

        self._write_file("tests/test_orders.py", """from backend.services.order_service import OrderService

def test_create_order():
    svc = OrderService()
    order_id = svc.create_order("c1", 150.0)
    assert order_id is not None
""")

        # Negative control test suite: strictly tests utils/formatting
        self._write_file("tests/test_unrelated.py", """from utils.formatting import format_currency

def test_format_currency():
    assert format_currency(1234.5) == "$1,234.50"
    assert format_currency(0.0) == "$0.00"
""")

        self._write_file("config/app.json", """{
    "app_name": "SyntheticShop",
    "version": "1.0.0",
    "environment": "benchmark_lab",
    "features": {
        "notifications": false,
        "multi_currency": false
    }
}""")

        self._write_file("Dockerfile", """FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "backend.api.checkout:router", "--host", "0.0.0.0", "--port", "8000"]
""")

        self._write_file("requirements.txt", """fastapi>=0.100.0
pydantic>=2.0.0
pytest>=7.4.0
sqlalchemy>=2.0.0
""")

        self._write_file("package.json", """{
  "name": "synthetic-shop",
  "version": "1.0.0",
  "description": "Deterministic Benchmark Lab Synthetic Multi-Tier Store",
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0"
  }
}""")

        self._write_file("README.md", "# Synthetic Shop Benchmark Fixture\nControlled digital twin evaluation repository.\n")

        self._git("add", ".")
        self._git("commit", "-m", "feat: initial project architecture with fullstack shop components")
        sha1 = self._git("rev-parse", "HEAD")
        self._git("tag", "v1.0.0")
        commits_map["c1_initial"] = CommitInfo(1, "c1_initial", sha1, "feat: initial project architecture", "v1.0.0")

        # =====================================================================
        # COMMIT 2: Component Addition (NotificationService & Bell UI)
        # =====================================================================
        self._write_file("backend/services/notification_service.py", """from typing import Dict, Any

class NotificationService:
    \"\"\"Notification dispatch service for customer order alerts.\"\"\"

    def send_order_confirmation(self, customer_id: str, order_id: str) -> bool:
        # Simulate dispatching email notification
        return True
""")

        self._write_file("frontend/src/components/NotificationBell.tsx", """import React from "react";

export const NotificationBell: React.FC = () => {
    return (
        <div className="notification-bell">
            <span>🔔</span>
        </div>
    );
};
""")

        self._write_file("backend/api/checkout.py", """from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.services.order_service import OrderService
from backend.services.payment_service import PaymentService
from backend.services.notification_service import NotificationService

router = APIRouter()
order_svc = OrderService()
payment_svc = PaymentService()
notif_svc = NotificationService()

class CheckoutRequest(BaseModel):
    customer_id: str
    total: float

@router.post("/api/checkout")
def checkout_endpoint(req: CheckoutRequest):
    order_id = order_svc.create_order(req.customer_id, req.total)
    success = payment_svc.charge(order_id, req.total)
    if not success:
        raise HTTPException(status_code=400, detail="Payment failed")
    notif_svc.send_order_confirmation(req.customer_id, order_id)
    return {"order_id": order_id, "status": "CONFIRMED"}
""")

        self._git("add", ".")
        self._git("commit", "-m", "feat: add notification service and checkout notification trigger")
        sha2 = self._git("rev-parse", "HEAD")
        commits_map["c2_component_add"] = CommitInfo(2, "c2_component_add", sha2, "feat: add notification service")

        # =====================================================================
        # COMMIT 3: Dependency Changes
        # =====================================================================
        self._write_file("requirements.txt", """fastapi>=0.104.0
pydantic>=2.5.0
pytest>=7.4.0
sqlalchemy>=2.0.20
httpx>=0.25.0
""")

        self._git("add", "requirements.txt")
        self._git("commit", "-m", "chore(deps): bump pydantic and add httpx client")
        sha3 = self._git("rev-parse", "HEAD")
        commits_map["c3_dependency_change"] = CommitInfo(3, "c3_dependency_change", sha3, "chore(deps): bump pydantic and add httpx")

        # =====================================================================
        # COMMIT 4: API Contract Changes (payment route currency support)
        # =====================================================================
        self._write_file("backend/api/payment.py", """from fastapi import APIRouter
from pydantic import BaseModel
from backend.services.payment_service import PaymentService

router = APIRouter()
payment_svc = PaymentService()

class PaymentRequest(BaseModel):
    amount: float
    currency: str = "USD"

@router.post("/api/payment")
def process_payment_endpoint(req: PaymentRequest):
    success = payment_svc.process_payment(req.amount)
    fee = payment_svc.calculate_fees(req.amount)
    return {"success": success, "fee": fee, "currency": req.currency}
""")

        self._write_file("frontend/src/components/PaymentWidget.tsx", """import React from "react";

export interface PaymentWidgetProps {
    onPay?: () => void;
}

export const PaymentWidget: React.FC<PaymentWidgetProps> = ({ onPay }) => {
    const submitPayment = async (amount: number) => {
        const res = await fetch("/api/payment", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ amount, currency: "USD" })
        });
        if (onPay) onPay();
        return res.json();
    };

    return (
        <button onClick={() => submitPayment(100.0)}>
            Pay Now (USD)
        </button>
    );
};
""")

        self._git("add", ".")
        self._git("commit", "-m", "feat(api): expand payment contract with currency support")
        sha4 = self._git("rev-parse", "HEAD")
        commits_map["c4_api_contract_change"] = CommitInfo(4, "c4_api_contract_change", sha4, "feat(api): expand payment contract with currency support")

        # =====================================================================
        # COMMIT 5: File Modifications (Payment fee formula change)
        # =====================================================================
        self._write_file("backend/services/payment_service.py", """from typing import Dict, Any
from backend.db.order_repo import OrderRepository

class PaymentService:
    \"\"\"Core payment processing and fee calculation service.\"\"\"

    def __init__(self, repo: OrderRepository = None):
        self.repo = repo or OrderRepository()

    def calculate_fees(self, amount: float) -> float:
        # Adjusted processing fee formula: 3.5% + $0.40
        return round(amount * 0.035 + 0.40, 2)

    def process_payment(self, amount: float) -> bool:
        fee = self.calculate_fees(amount)
        return amount > 0 and fee >= 0.40

    def charge(self, order_id: str, amount: float) -> bool:
        if self.process_payment(amount):
            return self.repo.update_status(order_id, "PAID")
        return False
""")

        self._git("add", "backend/services/payment_service.py")
        self._git("commit", "-m", "fix(payment): update calculation formula for processing fees")
        sha5 = self._git("rev-parse", "HEAD")
        commits_map["c5_file_modification"] = CommitInfo(5, "c5_file_modification", sha5, "fix(payment): update calculation formula for processing fees")

        # =====================================================================
        # COMMIT 6: File Deletion
        # =====================================================================
        self._remove_file("utils/legacy_tax.py")
        self._git("add", "-u", ".")
        self._git("commit", "-m", "refactor: remove deprecated legacy tax utility")
        sha6 = self._git("rev-parse", "HEAD")
        commits_map["c6_file_deletion"] = CommitInfo(6, "c6_file_deletion", sha6, "refactor: remove deprecated legacy tax utility")

        # =====================================================================
        # COMMIT 7: File Restoration
        # =====================================================================
        self._write_file("utils/legacy_tax.py", """import warnings

def compute_legacy_tax(subtotal: float) -> float:
    \"\"\"Deprecated legacy flat-rate tax calculation. Restored for backward compatibility.\"\"\"
    warnings.warn("compute_legacy_tax is deprecated and will be removed in v2", DeprecationWarning)
    return round(subtotal * 0.08, 2)
""")

        self._git("add", "utils/legacy_tax.py")
        self._git("commit", "-m", "fix: restore legacy tax module with deprecation warning")
        sha7 = self._git("rev-parse", "HEAD")
        commits_map["c7_file_restoration"] = CommitInfo(7, "c7_file_restoration", sha7, "fix: restore legacy tax module with deprecation warning")

        # =====================================================================
        # COMMIT 8: Rename and Move Operation
        # =====================================================================
        self._git("mv", "utils/math_helpers.py", "utils/calc_helpers.py")
        self._write_file("utils/calc_helpers.py", """def round_cents(val: float) -> float:
    \"\"\"Rounds value to 2 decimal places.\"\"\"
    return round(val, 2)

def percentage(part: float, whole: float) -> float:
    \"\"\"Calculates percentage of whole.\"\"\"
    return (part / whole) * 100.0 if whole != 0 else 0.0
""")

        self._git("add", ".")
        self._git("commit", "-m", "refactor: rename math_helpers to calc_helpers and add percentage utility")
        sha8 = self._git("rev-parse", "HEAD")
        commits_map["c8_rename_move"] = CommitInfo(8, "c8_rename_move", sha8, "refactor: rename math_helpers to calc_helpers")

        # =====================================================================
        # COMMIT 9: Test Additions
        # =====================================================================
        self._write_file("tests/test_payment_extended.py", """from backend.services.payment_service import PaymentService

def test_high_volume_payment_fees():
    svc = PaymentService()
    fee = svc.calculate_fees(5000.0)
    assert fee == round(5000.0 * 0.035 + 0.40, 2)

def test_charge_success():
    svc = PaymentService()
    assert svc.charge("ord_999", 250.0) is True
""")

        self._git("add", "tests/test_payment_extended.py")
        self._git("commit", "-m", "test: add extended regression tests for payment fee calculations")
        sha9 = self._git("rev-parse", "HEAD")
        commits_map["c9_test_additions"] = CommitInfo(9, "c9_test_additions", sha9, "test: add extended regression tests for payment fee calculations")

        # =====================================================================
        # COMMIT 10: Controlled Defect Introduction (Tag: v1.1.0-defect)
        # =====================================================================
        # Introduce breaking signature change in OrderRepository.update_status without default
        self._write_file("backend/db/order_repo.py", """from typing import Optional, Dict, Any

class OrderRepository:
    \"\"\"Data-access repository for customer orders.\"\"\"

    def save_order(self, order_data: Dict[str, Any]) -> str:
        order_id = str(order_data.get("id", "ord_new"))
        return order_id

    def find_by_id(self, order_id: str) -> Optional[Dict[str, Any]]:
        return {"id": order_id, "status": "PENDING", "total": 100.0}

    def update_status(self, order_id: str, status: str, updated_by: str) -> bool:
        # DEFECT: required updated_by breaks PaymentService.charge caller!
        return bool(order_id and status and updated_by)
""")

        self._git("add", "backend/db/order_repo.py")
        self._git("commit", "-m", "feat: require updated_by audit field on order status transitions")
        sha10 = self._git("rev-parse", "HEAD")
        self._git("tag", "v1.1.0-defect")
        commits_map["c10_defect_intro"] = CommitInfo(10, "c10_defect_intro", sha10, "feat: require updated_by audit field (defect)", "v1.1.0-defect")

        # =====================================================================
        # COMMIT 11: Corrective Changes (Tag: v1.1.1)
        # =====================================================================
        # Fix signature with backward-compatible default
        self._write_file("backend/db/order_repo.py", """from typing import Optional, Dict, Any

class OrderRepository:
    \"\"\"Data-access repository for customer orders.\"\"\"

    def save_order(self, order_data: Dict[str, Any]) -> str:
        order_id = str(order_data.get("id", "ord_new"))
        return order_id

    def find_by_id(self, order_id: str) -> Optional[Dict[str, Any]]:
        return {"id": order_id, "status": "PENDING", "total": 100.0}

    def update_status(self, order_id: str, status: str, updated_by: Optional[str] = None) -> bool:
        # Corrective change: optional updated_by preserves backward compatibility
        return bool(order_id and status)
""")

        self._git("add", "backend/db/order_repo.py")
        self._git("commit", "-m", "fix: make updated_by optional on update_status for caller compatibility")
        sha11 = self._git("rev-parse", "HEAD")
        self._git("tag", "v1.1.1")
        commits_map["c11_corrective_fix"] = CommitInfo(11, "c11_corrective_fix", sha11, "fix: make updated_by optional on update_status", "v1.1.1")

        # =====================================================================
        # COMMIT 12: Refactoring (Extract common validator)
        # =====================================================================
        self._write_file("backend/services/validators.py", """def validate_amount(amount: float) -> bool:
    \"\"\"Common financial amount validator.\"\"\"
    return isinstance(amount, (int, float)) and amount > 0 and amount < 1000000.0
""")

        self._write_file("backend/services/payment_service.py", """from typing import Dict, Any
from backend.db.order_repo import OrderRepository
from backend.services.validators import validate_amount

class PaymentService:
    \"\"\"Core payment processing and fee calculation service.\"\"\"

    def __init__(self, repo: OrderRepository = None):
        self.repo = repo or OrderRepository()

    def calculate_fees(self, amount: float) -> float:
        return round(amount * 0.035 + 0.40, 2)

    def process_payment(self, amount: float) -> bool:
        if not validate_amount(amount):
            return False
        fee = self.calculate_fees(amount)
        return fee >= 0.40

    def charge(self, order_id: str, amount: float) -> bool:
        if self.process_payment(amount):
            return self.repo.update_status(order_id, "PAID")
        return False
""")

        self._git("add", ".")
        self._git("commit", "-m", "refactor: extract financial amount validator and integrate into PaymentService")
        sha12 = self._git("rev-parse", "HEAD")
        commits_map["c12_refactoring"] = CommitInfo(12, "c12_refactoring", sha12, "refactor: extract financial amount validator")

        manifest = {
            "repository_name": "synthetic_shop",
            "fixture_path": self.target_dir,
            "total_commits": len(commits_map),
            "commits": {k: {"index": v.index, "sha": v.sha, "message": v.message, "tag": v.tag} for k, v in commits_map.items()},
            "tags": ["v1.0.0", "v1.1.0-defect", "v1.1.1"],
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }

        manifest_path = os.path.join(self.target_dir, "benchmark_manifest.json")
        import json
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        return manifest


fixture_generator = SyntheticFixtureGenerator()
