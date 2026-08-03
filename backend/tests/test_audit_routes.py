import unittest
from datetime import UTC, date, datetime
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




def make_log(**overrides):
    defaults = dict(
        id=uuid4(),
        user_id=uuid4(),
        user=SimpleNamespace(username="admin"),
        role_used=UserRole.ADMIN,
        action="approve",
        resource_type="reconciliation",
        resource_id=uuid4(),
        detail={"total_variance": "500.00"},
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


class ListAuditLogsPermissionTest(BaseRouteTest):
    def test_admin_can_view(self) -> None:
        with patch(
            "api.routes.audit.list_audit_logs", new=AsyncMock(return_value=[make_log()])
        ):
            response = self.client.get("/api/v1/audit", headers=bearer_header(UserRole.ADMIN))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 1)
        self.assertEqual(response.json()["items"][0]["username"], "admin")

    def test_manager_cannot_view(self) -> None:
        response = self.client.get("/api/v1/audit", headers=bearer_header(UserRole.MANAGER))
        self.assertEqual(response.status_code, 403)

    def test_accountant_cannot_view(self) -> None:
        response = self.client.get("/api/v1/audit", headers=bearer_header(UserRole.ACCOUNTANT))
        self.assertEqual(response.status_code, 403)

    def test_driver_cannot_view(self) -> None:
        response = self.client.get("/api/v1/audit", headers=bearer_header(UserRole.DRIVER))
        self.assertEqual(response.status_code, 403)


def make_exception(**overrides) -> ShipmentException:
    defaults = dict(
        container_no="MSCU1234567",
        code="credit_limit_exceeded",
        severity="critical",
        title="Vượt hạn mức công nợ",
        detail="Vượt hạn mức.",
        evidence=[],
        due_date=date(2026, 7, 23),
        days_remaining=2,
    )
    defaults.update(overrides)
    return ShipmentException(**defaults)


class CriticalExceptionApprovalAuditTest(BaseRouteTest):
    def _approve(self, severity: str):
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
                        code="credit_limit_exceeded",
                        action="approve",
                        severity_tier="critical" if severity == "critical" else "normal",
                        acted_by_username="tester",
                        acted_by_role="admin",
                        note=None,
                    )
                ),
            ),
            patch(
                "api.routes.exceptions.record_audit", new=AsyncMock(return_value=None)
            ) as audit_mock,
        ):
            response = self.client.post(
                "/api/v1/containers/MSCU1234567/exceptions/credit_limit_exceeded/approve",
                json={},
                headers=bearer_header(UserRole.ADMIN),
            )
        return response, audit_mock

    def test_approving_a_critical_exception_writes_exactly_one_audit_entry(self) -> None:
        response, audit_mock = self._approve(severity="critical")
        self.assertEqual(response.status_code, 200)
        audit_mock.assert_called_once()
        _, kwargs = audit_mock.call_args
        self.assertEqual(kwargs["action"], "approve")
        self.assertEqual(kwargs["resource_type"], "exception")
        self.assertEqual(kwargs["role_used"], UserRole.ADMIN)

    def test_approving_a_normal_exception_writes_no_audit_entry(self) -> None:
        """Only the critical-tier approval is the dispute-evidence moment
        8A cares about — a routine (warning-tier) approval isn't audited."""
        response, audit_mock = self._approve(severity="warning")
        self.assertEqual(response.status_code, 200)
        audit_mock.assert_not_called()


def make_fact(**overrides):
    defaults = dict(
        id=uuid4(),
        container_id=uuid4(),
        field_name="vessel",
        field_value="OLD VESSEL",
        normalized_value="OLD VESSEL",
        source_type="email",
        source_label="carrier@example.com",
        document_type=None,
        confidence=None,
        source_sent_at=None,
        email_id=uuid4(),
        attachment_id=None,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class ContainerFactEditAuditTest(BaseRouteTest):
    def test_editing_a_fact_writes_an_audit_entry_with_old_and_new_value(self) -> None:
        container = SimpleNamespace(id=uuid4(), container_no="MSCU1234567")
        fact = make_fact()
        updated_fact = make_fact(
            id=fact.id,
            container_id=container.id,
            field_value="NEW VESSEL",
            normalized_value="NEW VESSEL",
            source_type="manual_edit",
            source_label="Sửa tay bởi tester",
            source_sent_at=datetime.now(UTC),
        )
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
                new=AsyncMock(return_value=updated_fact),
            ),
            patch(
                "api.routes.containers.record_audit", new=AsyncMock(return_value=None)
            ) as audit_mock,
        ):
            response = self.client.patch(
                f"/api/v1/containers/MSCU1234567/facts/{fact.id}",
                json={"field_value": "NEW VESSEL"},
                headers=bearer_header(UserRole.OPS),
            )

        self.assertEqual(response.status_code, 200)
        audit_mock.assert_called_once()
        _, kwargs = audit_mock.call_args
        self.assertEqual(kwargs["action"], "edit")
        self.assertEqual(kwargs["resource_type"], "container_fact")
        self.assertEqual(kwargs["detail"]["old_value"], "OLD VESSEL")
        self.assertEqual(kwargs["detail"]["new_value"], "NEW VESSEL")


class ReconciliationApprovalAuditTest(BaseRouteTest):
    def test_approving_a_reconciliation_writes_an_audit_entry(self) -> None:
        from db.models import ReconciliationStatus

        rec = SimpleNamespace(
            id=uuid4(),
            container_id=uuid4(),
            container=SimpleNamespace(container_no="MSCU1234567"),
            quote_id=uuid4(),
            quote=SimpleNamespace(quote_no="Q-2026-0001"),
            status=ReconciliationStatus.ESCALATED,
            total_quoted="1200.00",
            total_actual="1700.00",
            total_variance="500.00",
            needs_approval=True,
            created_by=uuid4(),
            approved_by=None,
            lines=[],
            created_at=datetime.now(UTC),
        )
        approved = SimpleNamespace(**{**rec.__dict__, "status": ReconciliationStatus.APPROVED})

        with (
            patch(
                "api.routes.reconciliation.get_reconciliation",
                new=AsyncMock(return_value=rec),
            ),
            patch(
                "api.routes.reconciliation.approve_reconciliation",
                new=AsyncMock(return_value=approved),
            ),
            patch(
                "api.routes.reconciliation.record_audit", new=AsyncMock(return_value=None)
            ) as audit_mock,
        ):
            response = self.client.post(
                f"/api/v1/reconciliation/{rec.id}/approve",
                json={},
                headers=bearer_header(UserRole.ADMIN),
            )

        self.assertEqual(response.status_code, 200)
        audit_mock.assert_called_once()
        _, kwargs = audit_mock.call_args
        self.assertEqual(kwargs["action"], "approve")
        self.assertEqual(kwargs["resource_type"], "reconciliation")
        self.assertEqual(kwargs["resource_id"], rec.id)


if __name__ == "__main__":
    unittest.main()
