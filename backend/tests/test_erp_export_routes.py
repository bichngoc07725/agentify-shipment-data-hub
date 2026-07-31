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
from db.models import ReconciliationStatus, UserRole
from tests.auth_helpers import bearer_header




def make_line(**overrides):
    defaults = dict(
        charge_code="OF",
        quoted_amount=Decimal("1200.00"),
        actual_amount=Decimal("1250.00"),
        variance=Decimal("50.00"),
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def make_reconciliation(**overrides):
    defaults = dict(
        id=uuid4(),
        status=ReconciliationStatus.APPROVED,
        lines=[make_line(), make_line(charge_code="THC", quoted_amount=Decimal("80.00"), actual_amount=Decimal("80.00"), variance=Decimal("0"))],
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


class ExportReconciliationPermissionTest(BaseRouteTest):
    def _export(self, headers: dict[str, str]):
        rec = make_reconciliation()
        with (
            patch(
                "api.routes.erp_export.get_reconciliation",
                new=AsyncMock(return_value=rec),
            ),
            patch(
                "api.routes.erp_export.record_audit", new=AsyncMock(return_value=None)
            ) as audit_mock,
        ):
            response = self.client.get(
                f"/api/v1/erp-export/reconciliation/{rec.id}", headers=headers
            )
        return response, audit_mock, rec

    def test_accountant_can_export(self) -> None:
        response, audit_mock, rec = self._export(bearer_header(UserRole.ACCOUNTANT))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "text/csv; charset=utf-8")
        self.assertIn(f'reconciliation-{rec.id}.csv', response.headers["content-disposition"])

    def test_export_contains_every_reconciliation_line_with_matching_amounts(self) -> None:
        response, _, _ = self._export(bearer_header(UserRole.ACCOUNTANT))
        text = response.content.decode("utf-8-sig")
        rows = text.splitlines()
        self.assertEqual(len(rows), 3)
        self.assertIn("1200.00,1250.00,50.00", rows[1])
        self.assertIn("80.00,80.00,0", rows[2])

    def test_export_writes_one_audit_entry(self) -> None:
        _, audit_mock, rec = self._export(bearer_header(UserRole.ACCOUNTANT))
        audit_mock.assert_called_once()
        _, kwargs = audit_mock.call_args
        self.assertEqual(kwargs["action"], "export")
        self.assertEqual(kwargs["resource_type"], "reconciliation")
        self.assertEqual(kwargs["resource_id"], rec.id)

    def test_docs_cannot_export(self) -> None:
        response, _, _ = self._export(bearer_header(UserRole.DOCS))
        self.assertEqual(response.status_code, 403)

    def test_ops_cannot_export(self) -> None:
        response, _, _ = self._export(bearer_header(UserRole.OPS))
        self.assertEqual(response.status_code, 403)

    def test_sales_cs_cannot_export(self) -> None:
        response, _, _ = self._export(bearer_header(UserRole.SALES_CS))
        self.assertEqual(response.status_code, 403)

    def test_unknown_reconciliation_is_404(self) -> None:
        with patch(
            "api.routes.erp_export.get_reconciliation", new=AsyncMock(return_value=None)
        ):
            response = self.client.get(
                f"/api/v1/erp-export/reconciliation/{uuid4()}",
                headers=bearer_header(UserRole.ACCOUNTANT),
            )
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
