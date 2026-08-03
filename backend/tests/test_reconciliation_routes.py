import unittest
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from api import app
from api.routes import api_main  # noqa: F401  (registers every router on `app`)
from db.database import get_db
from db.models import ReconciliationMatchStatus, ReconciliationStatus, UserRole
from tests.auth_helpers import bearer_header




def make_line(**overrides):
    defaults = dict(
        id=uuid4(),
        charge_code="OF",
        quoted_amount=Decimal("1200.00"),
        actual_amount=Decimal("1200.00"),
        variance=Decimal("0"),
        match_status=ReconciliationMatchStatus.MATCHED,
        note=None,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def make_reconciliation(**overrides):
    defaults = dict(
        id=uuid4(),
        container_id=uuid4(),
        container=SimpleNamespace(container_no="MSCU1234567"),
        quote_id=uuid4(),
        quote=SimpleNamespace(quote_no="Q-2026-0001"),
        status=ReconciliationStatus.DRAFT,
        total_quoted=Decimal("1200.00"),
        total_actual=Decimal("1200.00"),
        total_variance=Decimal("0"),
        needs_approval=False,
        created_by=uuid4(),
        approved_by=None,
        lines=[make_line()],
        created_at=datetime.now(UTC),
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class BaseRouteTest(unittest.TestCase):
    def setUp(self) -> None:
        app.dependency_overrides[get_db] = lambda: None
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()


class CreateReconciliationPermissionTest(BaseRouteTest):
    def _create(self, headers: dict[str, str]):
        with patch(
            "api.routes.reconciliation.build_reconciliation",
            new=AsyncMock(return_value=make_reconciliation()),
        ):
            return self.client.post(
                "/api/v1/reconciliation",
                json={"container_no": "MSCU1234567", "quote_id": str(uuid4())},
                headers=headers,
            )

    def test_accountant_can_create(self) -> None:
        response = self._create(bearer_header(UserRole.ACCOUNTANT))
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["lines"][0]["match_status"], "matched")
        self.assertFalse(body["needs_approval"])

    def test_docs_cannot_create(self) -> None:
        response = self._create(bearer_header(UserRole.DOCS))
        self.assertEqual(response.status_code, 403)

    def test_sales_cs_cannot_create(self) -> None:
        response = self._create(bearer_header(UserRole.SALES_CS))
        self.assertEqual(response.status_code, 403)

    def test_admin_cannot_create(self) -> None:
        """Admin approves escalations, but running the reconciliation itself
        is Accountant's job, per the design doc's least-privilege split."""
        response = self._create(bearer_header(UserRole.ADMIN))
        self.assertEqual(response.status_code, 403)


class ViewReconciliationPermissionTest(BaseRouteTest):
    def test_docs_ops_manager_accountant_can_view(self) -> None:
        for role in [UserRole.ADMIN, UserRole.MANAGER, UserRole.DOCS, UserRole.OPS, UserRole.ACCOUNTANT]:
            with self.subTest(role=role):
                rec = make_reconciliation()
                with patch(
                    "api.routes.reconciliation.get_reconciliation",
                    new=AsyncMock(return_value=rec),
                ):
                    response = self.client.get(
                        f"/api/v1/reconciliation/{rec.id}", headers=bearer_header(role)
                    )
                self.assertEqual(response.status_code, 200)

    def test_sales_cs_cannot_view(self) -> None:
        response = self.client.get(
            f"/api/v1/reconciliation/{uuid4()}", headers=bearer_header(UserRole.SALES_CS)
        )
        self.assertEqual(response.status_code, 403)

    def test_driver_cannot_view(self) -> None:
        response = self.client.get(
            f"/api/v1/reconciliation/{uuid4()}", headers=bearer_header(UserRole.DRIVER)
        )
        self.assertEqual(response.status_code, 403)

    def test_unknown_reconciliation_is_404(self) -> None:
        with patch(
            "api.routes.reconciliation.get_reconciliation", new=AsyncMock(return_value=None)
        ):
            response = self.client.get(
                f"/api/v1/reconciliation/{uuid4()}", headers=bearer_header(UserRole.ACCOUNTANT)
            )
        self.assertEqual(response.status_code, 404)


class ApproveReconciliationPermissionTest(BaseRouteTest):
    def _approve(self, headers: dict[str, str]):
        rec = make_reconciliation(
            status=ReconciliationStatus.ESCALATED,
            needs_approval=True,
            total_variance=Decimal("500.00"),
        )
        approved = make_reconciliation(
            id=rec.id, status=ReconciliationStatus.APPROVED, approved_by=uuid4()
        )
        with (
            patch(
                "api.routes.reconciliation.get_reconciliation",
                new=AsyncMock(return_value=rec),
            ),
            patch(
                "api.routes.reconciliation.approve_reconciliation",
                new=AsyncMock(return_value=approved),
            ),
        ):
            return self.client.post(
                f"/api/v1/reconciliation/{rec.id}/approve", json={}, headers=headers
            )

    def test_accountant_cannot_approve(self) -> None:
        """Large variances need Admin/Manager sign-off, not the accountant
        who ran the reconciliation — same severity-gate pattern as GĐ2's
        exception engine."""
        response = self._approve(bearer_header(UserRole.ACCOUNTANT))
        self.assertEqual(response.status_code, 403)

    def test_manager_can_approve(self) -> None:
        response = self._approve(bearer_header(UserRole.MANAGER))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "approved")

    def test_admin_can_approve(self) -> None:
        response = self._approve(bearer_header(UserRole.ADMIN))
        self.assertEqual(response.status_code, 200)


class ContainerReconciliationTest(BaseRouteTest):
    def test_container_reconciliations_are_listed(self) -> None:
        rec = make_reconciliation()
        with (
            patch(
                "api.routes.reconciliation.get_container_by_no",
                new=AsyncMock(return_value=SimpleNamespace(id=uuid4())),
            ),
            patch(
                "api.routes.reconciliation.list_reconciliations_for_container",
                new=AsyncMock(return_value=[rec]),
            ),
        ):
            response = self.client.get(
                "/api/v1/containers/MSCU1234567/reconciliation",
                headers=bearer_header(UserRole.ACCOUNTANT),
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 1)

    def test_driver_cannot_view_container_reconciliation(self) -> None:
        response = self.client.get(
            "/api/v1/containers/MSCU1234567/reconciliation",
            headers=bearer_header(UserRole.DRIVER),
        )
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
