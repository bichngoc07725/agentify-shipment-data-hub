"""Route-level RBAC tests: for each protected endpoint, a role either in or
out of `config/permissions.py`'s allowed set gets exactly 200 or 403.

Every test builds a real JWT via `create_access_token` (not a mocked
dependency) so the assertions exercise the actual `require_permission` /
`get_current_user` code path, not just the permission table's contents.
"""

import unittest
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from api import app
from api.routes import api_main  # noqa: F401  (registers every router on `app`)
from db.database import get_db
from db.models import UserRole
from tests.auth_helpers import bearer_header
from services.exception_service import ContainerRiskProfile, ShipmentException




class BaseRouteTest(unittest.TestCase):
    def setUp(self) -> None:
        app.dependency_overrides[get_db] = lambda: None
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()


class ManualIngestPermissionTest(BaseRouteTest):
    """Resource `manual_ingest`, action `create`: Ops and Docs only."""

    def _post(self, headers: dict[str, str]):
        with patch(
            "api.routes.manual_ingest.ingest_manual_content",
            new=AsyncMock(
                return_value={
                    "message_id": uuid4(),
                    "channel": "zalo",
                    "linked_containers": ["MSCU1234567"],
                    "fact_count": 0,
                    "extraction_method": "deterministic",
                    "extraction_status": "ok",
                }
            ),
        ):
            return self.client.post(
                "/api/v1/manual-ingest",
                json={"channel": "zalo", "content": "MSCU1234567 da toi cang"},
                headers=headers,
            )

    def test_ops_can_create(self) -> None:
        response = self._post(bearer_header(UserRole.OPS))
        self.assertEqual(response.status_code, 200)

    def test_docs_can_create(self) -> None:
        response = self._post(bearer_header(UserRole.DOCS))
        self.assertEqual(response.status_code, 200)

    def test_sales_cs_cannot_create(self) -> None:
        response = self._post(bearer_header(UserRole.SALES_CS))
        self.assertEqual(response.status_code, 403)

    def test_driver_cannot_create(self) -> None:
        response = self._post(bearer_header(UserRole.DRIVER))
        self.assertEqual(response.status_code, 403)

    def test_missing_token_is_401_not_403(self) -> None:
        response = self.client.post(
            "/api/v1/manual-ingest",
            json={"channel": "zalo", "content": "MSCU1234567 da toi cang"},
        )
        self.assertEqual(response.status_code, 401)


def make_fact(**overrides):
    defaults = dict(
        id=uuid4(),
        container_id=uuid4(),
        field_name="vessel",
        field_value="MAERSK HANOI",
        normalized_value="MAERSK HANOI",
        source_type="email",
        source_label="carrier@example.com",
        document_type=None,
        confidence=Decimal("0.9"),
        source_sent_at=None,
        email_id=uuid4(),
        attachment_id=None,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class ContainerFactEditPermissionTest(BaseRouteTest):
    """Resource `container_facts`, action `edit`: two layers.

    Layer 1 (role level): Docs, Ops, Accountant only.
    Layer 2 (field group): a role may only touch fields in its own group.
    """

    def _patch(self, headers: dict[str, str], field_name: str):
        container = SimpleNamespace(id=uuid4(), container_no="MSCU1234567")
        fact = make_fact(container_id=container.id, field_name=field_name)
        with (
            patch(
                "api.routes.containers.get_container_by_no",
                new=AsyncMock(return_value=container),
            ),
            patch(
                "api.routes.containers.get_container_fact_by_id",
                new=AsyncMock(return_value=fact),
            ),
            patch(
                "api.routes.containers.update_container_fact",
                new=AsyncMock(return_value=fact),
            ),
        ):
            return self.client.patch(
                f"/api/v1/containers/MSCU1234567/facts/{fact.id}",
                json={"field_value": "NEW VALUE"},
                headers=headers,
            )

    def test_ops_can_edit_an_operation_field(self) -> None:
        response = self._patch(bearer_header(UserRole.OPS), field_name="vessel")
        self.assertEqual(response.status_code, 200)

    def test_docs_can_edit_a_document_field(self) -> None:
        response = self._patch(bearer_header(UserRole.DOCS), field_name="bl_no")
        self.assertEqual(response.status_code, 200)

    def test_docs_cannot_edit_an_operation_field(self) -> None:
        """Layer 2: Docs has Edit rights in general, but not on Ops's group."""
        response = self._patch(bearer_header(UserRole.DOCS), field_name="vessel")
        self.assertEqual(response.status_code, 403)

    def test_ops_cannot_edit_a_document_field(self) -> None:
        response = self._patch(bearer_header(UserRole.OPS), field_name="bl_no")
        self.assertEqual(response.status_code, 403)

    def test_sales_cs_cannot_edit_at_all(self) -> None:
        """Layer 1: Sales/CS has no Edit right on container_facts, period."""
        response = self._patch(bearer_header(UserRole.SALES_CS), field_name="vessel")
        self.assertEqual(response.status_code, 403)

    def test_accountant_cannot_edit_an_unclassified_field(self) -> None:
        """`vessel` is Ops's field, and Accountant isn't Ops — must fail
        closed, not be silently allowed."""
        response = self._patch(bearer_header(UserRole.ACCOUNTANT), field_name="vessel")
        self.assertEqual(response.status_code, 403)

    def test_accountant_can_edit_a_finance_field(self) -> None:
        response = self._patch(
            bearer_header(UserRole.ACCOUNTANT), field_name="debit_note_no"
        )
        self.assertEqual(response.status_code, 200)

    def test_docs_cannot_edit_a_finance_field(self) -> None:
        response = self._patch(bearer_header(UserRole.DOCS), field_name="debit_note_no")
        self.assertEqual(response.status_code, 403)

    def test_ketoan_cannot_edit_a_document_field(self) -> None:
        response = self._patch(bearer_header(UserRole.ACCOUNTANT), field_name="bl_no")
        self.assertEqual(response.status_code, 403)


def make_exception(**overrides) -> ShipmentException:
    defaults = dict(
        container_no="MSCU1234567",
        code="free_time_expiring",
        severity="warning",
        title="Sắp hết free time",
        detail="Hết free time trong 2 ngày nữa.",
        evidence=["Free time: 5 ngày"],
        due_date=date(2026, 7, 23),
        days_remaining=2,
    )
    defaults.update(overrides)
    return ShipmentException(**defaults)


class ExceptionActionPermissionTest(BaseRouteTest):
    """Resolve/approve are gated by severity tier, not just role."""

    def _call(self, action: str, headers: dict[str, str], severity: str):
        container = SimpleNamespace(id=uuid4(), container_no="MSCU1234567")
        profile = ContainerRiskProfile(
            container_no="MSCU1234567",
            direction="import",
            exceptions=[make_exception(severity=severity)],
            documents_present=[],
            documents_mentioned=[],
            documents_missing=[],
            completeness=0.5,
            free_time_expires_on=None,
            free_time_is_assumed=False,
        )
        with (
            patch(
                "api.routes.exceptions.get_container_by_no",
                new=AsyncMock(return_value=container),
            ),
            patch(
                "api.routes.exceptions.get_container_risk_profile",
                new=AsyncMock(return_value=profile),
            ),
            patch(
                "api.routes.exceptions.record_exception_action",
                new=AsyncMock(
                    return_value=SimpleNamespace(
                        code="free_time_expiring",
                        action=action,
                        severity_tier="critical" if severity == "critical" else "normal",
                        acted_by_username="tester",
                        acted_by_role="ops",
                        note=None,
                    )
                ),
            ),
        ):
            return self.client.post(
                f"/api/v1/containers/MSCU1234567/exceptions/free_time_expiring/{action}",
                json={},
                headers=headers,
            )

    def test_ops_can_resolve_a_normal_exception(self) -> None:
        response = self._call("resolve", bearer_header(UserRole.OPS), severity="warning")
        self.assertEqual(response.status_code, 200)

    def test_docs_can_resolve_a_normal_exception(self) -> None:
        response = self._call("resolve", bearer_header(UserRole.DOCS), severity="warning")
        self.assertEqual(response.status_code, 200)

    def test_sales_cs_cannot_resolve_a_normal_exception(self) -> None:
        response = self._call("resolve", bearer_header(UserRole.SALES_CS), severity="warning")
        self.assertEqual(response.status_code, 403)

    def test_admin_can_approve_a_normal_exception(self) -> None:
        response = self._call("approve", bearer_header(UserRole.ADMIN), severity="warning")
        self.assertEqual(response.status_code, 200)

    def test_ops_cannot_approve_a_normal_exception(self) -> None:
        response = self._call("approve", bearer_header(UserRole.OPS), severity="warning")
        self.assertEqual(response.status_code, 403)

    def test_admin_can_approve_a_critical_exception(self) -> None:
        response = self._call("approve", bearer_header(UserRole.ADMIN), severity="critical")
        self.assertEqual(response.status_code, 200)

    def test_manager_can_approve_a_critical_exception(self) -> None:
        response = self._call("approve", bearer_header(UserRole.MANAGER), severity="critical")
        self.assertEqual(response.status_code, 200)

    def test_ops_cannot_approve_a_critical_exception(self) -> None:
        response = self._call("approve", bearer_header(UserRole.OPS), severity="critical")
        self.assertEqual(response.status_code, 403)

    def test_docs_cannot_resolve_a_critical_exception(self) -> None:
        """Critical exceptions have no 'resolve' tier for anyone but
        Admin/Manager approve — Docs's normal-tier resolve right does not
        carry over."""
        response = self._call("resolve", bearer_header(UserRole.DOCS), severity="critical")
        self.assertEqual(response.status_code, 403)

    def test_sales_cs_cannot_approve_a_critical_exception(self) -> None:
        response = self._call("approve", bearer_header(UserRole.SALES_CS), severity="critical")
        self.assertEqual(response.status_code, 403)

    def test_admin_can_approve_a_critical_exception_where_sales_cannot(self) -> None:
        response = self._call("approve", bearer_header(UserRole.ADMIN), severity="critical")
        self.assertEqual(response.status_code, 200)


class SystemConfigPermissionTest(BaseRouteTest):
    """Resource `system_config` (Gmail connections, in this codebase):
    Admin/Manager only, per design doc row 1. No other role — including
    Accountant — may view or edit it."""

    def test_accountant_cannot_view_gmail_connections(self) -> None:
        response = self.client.get(
            "/api/v1/gmail-connections", headers=bearer_header(UserRole.ACCOUNTANT)
        )
        self.assertEqual(response.status_code, 403)

    def test_accountant_cannot_start_gmail_oauth(self) -> None:
        response = self.client.get(
            "/api/v1/gmail-connections/oauth/start",
            headers=bearer_header(UserRole.ACCOUNTANT),
        )
        self.assertEqual(response.status_code, 403)

    def test_admin_can_view_gmail_connections(self) -> None:
        with patch(
            "api.routes.gmail_connections.list_gmail_connections",
            new=AsyncMock(return_value=[]),
        ):
            response = self.client.get(
                "/api/v1/gmail-connections", headers=bearer_header(UserRole.ADMIN)
            )
        self.assertEqual(response.status_code, 200)

    def test_manager_can_view_gmail_connections(self) -> None:
        """Manager has view-only system_config access, per design doc §7."""
        with patch(
            "api.routes.gmail_connections.list_gmail_connections",
            new=AsyncMock(return_value=[]),
        ):
            response = self.client.get(
                "/api/v1/gmail-connections", headers=bearer_header(UserRole.MANAGER)
            )
        self.assertEqual(response.status_code, 200)

    def test_manager_cannot_edit_gmail_connections(self) -> None:
        """Manager is view-only on system_config — Edit is Admin-exclusive."""
        response = self.client.post(
            "/api/v1/gmail-connections",
            json={"account_email": "demo@agentify.vn"},
            headers=bearer_header(UserRole.MANAGER),
        )
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
