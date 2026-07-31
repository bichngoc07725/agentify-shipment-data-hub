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
from db.models import ChargeGroup, QuoteStatus, UserRole
from tests.auth_helpers import bearer_header




def make_charge(**overrides):
    defaults = dict(
        id=uuid4(),
        charge_group=ChargeGroup.OCEAN_FREIGHT,
        charge_code="OF",
        description="Ocean freight 40HC",
        unit_price=Decimal("1200.00"),
        currency="USD",
        quantity=Decimal("2"),
        amount=Decimal("2400.00"),
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def make_quote(**overrides):
    defaults = dict(
        id=uuid4(),
        quote_no="Q-2026-0001",
        customer_name="ABC Trading",
        status=QuoteStatus.DRAFT,
        pol="Ho Chi Minh City",
        pod="Los Angeles",
        commodity="Furniture",
        is_dangerous=False,
        is_reefer=False,
        container_type="40HC",
        container_qty=2,
        gross_weight_kg=Decimal("18000"),
        cargo_ready_date=None,
        incoterm="FOB",
        payment_term="30% deposit",
        transit_time="25 days",
        valid_until=None,
        note=None,
        currency="USD",
        created_by=uuid4(),
        container_id=None,
        container=None,
        charges=[make_charge()],
        created_at=datetime.now(UTC),
        updated_at=None,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


CREATE_PAYLOAD = {
    "customer_name": "ABC Trading",
    "pol": "Ho Chi Minh City",
    "pod": "Los Angeles",
    "container_type": "40HC",
    "container_qty": 2,
    "charges": [
        {"charge_group": "ocean_freight", "charge_code": "OF", "unit_price": "1200.00", "quantity": "2"},
        {"charge_group": "surcharge", "charge_code": "THC", "unit_price": "80.00", "quantity": "2"},
        {"charge_group": "local", "charge_code": "DOC", "unit_price": "30.00", "quantity": "1"},
    ],
}


class BaseRouteTest(unittest.TestCase):
    def setUp(self) -> None:
        app.dependency_overrides[get_db] = lambda: None
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()


class CreateQuotePermissionTest(BaseRouteTest):
    """Only Sales/CS may create — everyone else, including Admin, is
    view-only on quotes per the design doc."""

    def test_sales_cs_can_create(self) -> None:
        with patch(
            "api.routes.quotes.create_quote", new=AsyncMock(return_value=make_quote())
        ):
            response = self.client.post(
                "/api/v1/quotes",
                json=CREATE_PAYLOAD,
                headers=bearer_header(UserRole.SALES_CS),
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["quote_no"], "Q-2026-0001")
        self.assertEqual(len(body["charges"]), 1)
        self.assertEqual(body["total_amount"], "2400.00")

    def test_docs_cannot_create(self) -> None:
        response = self.client.post(
            "/api/v1/quotes", json=CREATE_PAYLOAD, headers=bearer_header(UserRole.DOCS)
        )
        self.assertEqual(response.status_code, 403)

    def test_ops_cannot_create(self) -> None:
        response = self.client.post(
            "/api/v1/quotes", json=CREATE_PAYLOAD, headers=bearer_header(UserRole.OPS)
        )
        self.assertEqual(response.status_code, 403)

    def test_admin_cannot_create(self) -> None:
        response = self.client.post(
            "/api/v1/quotes", json=CREATE_PAYLOAD, headers=bearer_header(UserRole.ADMIN)
        )
        self.assertEqual(response.status_code, 403)


class ViewQuotePermissionTest(BaseRouteTest):
    def test_every_non_driver_role_can_list(self) -> None:
        staff_roles = [
            UserRole.ADMIN, UserRole.MANAGER, UserRole.SALES_CS,
            UserRole.DOCS, UserRole.OPS, UserRole.ACCOUNTANT,
        ]
        for role in staff_roles:
            with self.subTest(role=role):
                with patch(
                    "api.routes.quotes.list_quotes",
                    new=AsyncMock(return_value=([make_quote()], 1)),
                ):
                    response = self.client.get("/api/v1/quotes", headers=bearer_header(role))
                self.assertEqual(response.status_code, 200)

    def test_driver_cannot_list(self) -> None:
        response = self.client.get("/api/v1/quotes", headers=bearer_header(UserRole.DRIVER))
        self.assertEqual(response.status_code, 403)

    def test_get_single_quote(self) -> None:
        quote = make_quote()
        with patch("api.routes.quotes.get_quote", new=AsyncMock(return_value=quote)):
            response = self.client.get(
                f"/api/v1/quotes/{quote.id}", headers=bearer_header(UserRole.OPS)
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["customer_name"], "ABC Trading")

    def test_unknown_quote_is_404(self) -> None:
        with patch("api.routes.quotes.get_quote", new=AsyncMock(return_value=None)):
            response = self.client.get(
                f"/api/v1/quotes/{uuid4()}", headers=bearer_header(UserRole.OPS)
            )
        self.assertEqual(response.status_code, 404)


class UpdateDeleteQuotePermissionTest(BaseRouteTest):
    def test_sales_cs_can_update(self) -> None:
        quote = make_quote()
        with (
            patch("api.routes.quotes.get_quote", new=AsyncMock(return_value=quote)),
            patch("api.routes.quotes.update_quote", new=AsyncMock(return_value=quote)),
        ):
            response = self.client.put(
                f"/api/v1/quotes/{quote.id}",
                json=CREATE_PAYLOAD,
                headers=bearer_header(UserRole.SALES_CS),
            )
        self.assertEqual(response.status_code, 200)

    def test_docs_cannot_update(self) -> None:
        response = self.client.put(
            f"/api/v1/quotes/{uuid4()}",
            json=CREATE_PAYLOAD,
            headers=bearer_header(UserRole.DOCS),
        )
        self.assertEqual(response.status_code, 403)

    def test_sales_cs_can_delete(self) -> None:
        quote = make_quote()
        with (
            patch("api.routes.quotes.get_quote", new=AsyncMock(return_value=quote)),
            patch("api.routes.quotes.delete_quote", new=AsyncMock(return_value=None)),
        ):
            response = self.client.delete(
                f"/api/v1/quotes/{quote.id}", headers=bearer_header(UserRole.SALES_CS)
            )
        self.assertEqual(response.status_code, 204)

    def test_ops_cannot_delete(self) -> None:
        response = self.client.delete(
            f"/api/v1/quotes/{uuid4()}", headers=bearer_header(UserRole.OPS)
        )
        self.assertEqual(response.status_code, 403)


class ContainerQuotesTest(BaseRouteTest):
    def test_container_quotes_are_listed(self) -> None:
        quote = make_quote()
        with (
            patch(
                "api.routes.quotes.get_container_by_no",
                new=AsyncMock(return_value=SimpleNamespace(id=uuid4())),
            ),
            patch(
                "api.routes.quotes.list_quotes_for_container",
                new=AsyncMock(return_value=[quote]),
            ),
        ):
            response = self.client.get(
                "/api/v1/containers/MSCU1234567/quotes", headers=bearer_header(UserRole.DOCS)
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 1)

    def test_unknown_container_is_404(self) -> None:
        with patch(
            "api.routes.quotes.get_container_by_no", new=AsyncMock(return_value=None)
        ):
            response = self.client.get(
                "/api/v1/containers/NOSUCH0000000/quotes",
                headers=bearer_header(UserRole.DOCS),
            )
        self.assertEqual(response.status_code, 404)

    def test_driver_cannot_view_container_quotes(self) -> None:
        response = self.client.get(
            "/api/v1/containers/MSCU1234567/quotes", headers=bearer_header(UserRole.DRIVER)
        )
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
