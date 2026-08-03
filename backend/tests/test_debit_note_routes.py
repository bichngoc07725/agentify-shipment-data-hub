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
from db.models import UserRole
from tests.auth_helpers import bearer_header




def make_charge(**overrides):
    defaults = dict(
        id=uuid4(),
        charge_code="THC",
        description="Terminal handling",
        amount=Decimal("120.00"),
        currency="USD",
        quantity=Decimal("1"),
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def make_debit_note(**overrides):
    defaults = dict(
        id=uuid4(),
        container_id=uuid4(),
        container=SimpleNamespace(container_no="MSCU1234567"),
        source_attachment_id=None,
        partner_name="ONE Line",
        doc_no="DN-2026-001",
        currency="USD",
        issued_date=None,
        created_by=uuid4(),
        charges=[make_charge()],
        created_at=datetime.now(UTC),
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


CREATE_PAYLOAD = {
    "container_no": "MSCU1234567",
    "partner_name": "ONE Line",
    "doc_no": "DN-2026-001",
    "charges": [
        {"charge_code": "THC", "amount": "120.00", "quantity": "1"},
    ],
}


class BaseRouteTest(unittest.TestCase):
    def setUp(self) -> None:
        app.dependency_overrides[get_db] = lambda: None
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()


class CreateDebitNotePermissionTest(BaseRouteTest):
    def test_accountant_can_create(self) -> None:
        with patch(
            "api.routes.debit_notes.create_debit_note",
            new=AsyncMock(return_value=make_debit_note()),
        ):
            response = self.client.post(
                "/api/v1/debit-notes",
                json=CREATE_PAYLOAD,
                headers=bearer_header(UserRole.ACCOUNTANT),
            )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["total_amount"], "120.00")

    def test_docs_cannot_create(self) -> None:
        response = self.client.post(
            "/api/v1/debit-notes", json=CREATE_PAYLOAD, headers=bearer_header(UserRole.DOCS)
        )
        self.assertEqual(response.status_code, 403)

    def test_sales_cs_cannot_create(self) -> None:
        response = self.client.post(
            "/api/v1/debit-notes", json=CREATE_PAYLOAD, headers=bearer_header(UserRole.SALES_CS)
        )
        self.assertEqual(response.status_code, 403)


class ViewDebitNotePermissionTest(BaseRouteTest):
    def test_docs_and_ops_and_manager_can_view(self) -> None:
        for role in [UserRole.ADMIN, UserRole.MANAGER, UserRole.DOCS, UserRole.OPS, UserRole.ACCOUNTANT]:
            with self.subTest(role=role):
                note = make_debit_note()
                with patch(
                    "api.routes.debit_notes.get_debit_note", new=AsyncMock(return_value=note)
                ):
                    response = self.client.get(
                        f"/api/v1/debit-notes/{note.id}", headers=bearer_header(role)
                    )
                self.assertEqual(response.status_code, 200)

    def test_sales_cs_cannot_view(self) -> None:
        """Cost data is internal-only — reveals margin against the quote."""
        response = self.client.get(
            f"/api/v1/debit-notes/{uuid4()}", headers=bearer_header(UserRole.SALES_CS)
        )
        self.assertEqual(response.status_code, 403)

    def test_driver_cannot_view(self) -> None:
        response = self.client.get(
            f"/api/v1/debit-notes/{uuid4()}", headers=bearer_header(UserRole.DRIVER)
        )
        self.assertEqual(response.status_code, 403)

    def test_unknown_debit_note_is_404(self) -> None:
        with patch(
            "api.routes.debit_notes.get_debit_note", new=AsyncMock(return_value=None)
        ):
            response = self.client.get(
                f"/api/v1/debit-notes/{uuid4()}", headers=bearer_header(UserRole.ACCOUNTANT)
            )
        self.assertEqual(response.status_code, 404)


class ContainerDebitNotesTest(BaseRouteTest):
    def test_container_debit_notes_are_listed(self) -> None:
        note = make_debit_note()
        with (
            patch(
                "api.routes.debit_notes.get_container_by_no",
                new=AsyncMock(return_value=SimpleNamespace(id=uuid4())),
            ),
            patch(
                "api.routes.debit_notes.list_debit_notes_for_container",
                new=AsyncMock(return_value=[note]),
            ),
        ):
            response = self.client.get(
                "/api/v1/containers/MSCU1234567/debit-notes",
                headers=bearer_header(UserRole.ACCOUNTANT),
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 1)

    def test_unknown_container_is_404(self) -> None:
        with patch(
            "api.routes.debit_notes.get_container_by_no", new=AsyncMock(return_value=None)
        ):
            response = self.client.get(
                "/api/v1/containers/NOSUCH0000000/debit-notes",
                headers=bearer_header(UserRole.ACCOUNTANT),
            )
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
