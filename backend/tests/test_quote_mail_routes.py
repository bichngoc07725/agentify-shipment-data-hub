import unittest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from api import app
from api.routes import api_main  # noqa: F401  (registers every router on `app`)
from db.database import get_db
from db.models import UserRole
from tests.auth_helpers import bearer_header

QUOTE_ID = uuid4()
EMAIL_ID = uuid4()

MAIL = {"subject": "Rate request Da Nang - Singapore", "body": "Dear Sirs, ..."}


class BaseMailRouteTest(unittest.TestCase):
    def setUp(self) -> None:
        app.dependency_overrides[get_db] = lambda: None
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()


class RateRequestMailTest(BaseMailRouteTest):
    def _get(self, headers, quote=object()):
        with patch(
            "api.routes.quotes.get_quote", new=AsyncMock(return_value=quote)
        ), patch("api.routes.quotes.build_rate_request_mail", return_value=MAIL):
            return self.client.get(
                f"/api/v1/quotes/{QUOTE_ID}/rate-request-mail", headers=headers
            )

    def test_sales_can_compose(self) -> None:
        response = self._get(bearer_header(UserRole.SALES_CS))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["subject"], MAIL["subject"])

    def test_ops_cannot_compose(self) -> None:
        self.assertEqual(self._get(bearer_header(UserRole.OPS)).status_code, 403)

    def test_no_token_is_rejected(self) -> None:
        self.assertEqual(self._get({}).status_code, 401)

    def test_unknown_quote_is_404(self) -> None:
        self.assertEqual(
            self._get(bearer_header(UserRole.SALES_CS), quote=None).status_code, 404
        )


class CustomerMailTest(BaseMailRouteTest):
    def _get(self, headers):
        with patch(
            "api.routes.quotes.get_quote", new=AsyncMock(return_value=object())
        ), patch("api.routes.quotes.build_customer_quote_mail", return_value=MAIL):
            return self.client.get(
                f"/api/v1/quotes/{QUOTE_ID}/customer-mail", headers=headers
            )

    def test_sales_can_compose(self) -> None:
        self.assertEqual(self._get(bearer_header(UserRole.SALES_CS)).status_code, 200)

    def test_accountant_cannot_compose(self) -> None:
        self.assertEqual(self._get(bearer_header(UserRole.ACCOUNTANT)).status_code, 403)


class ChargeDraftRouteTest(BaseMailRouteTest):
    def _get(self, headers, draft=None):
        payload = draft if draft is not None else {
            "source_email_id": str(EMAIL_ID),
            "source_subject": "RE: Rate request",
            "source_from": "booking@carrier.com",
            "charges": [
                {
                    "charge_group": "ocean_freight",
                    "charge_code": "OF",
                    "description": "Ocean Freight",
                    "unit_price": "780",
                    "currency": "USD",
                    "quantity": "1",
                }
            ],
            "extraction_error": None,
        }
        with patch(
            "api.routes.quotes.build_charge_draft_from_email",
            new=AsyncMock(return_value=payload),
        ):
            return self.client.get(
                f"/api/v1/emails/{EMAIL_ID}/charge-draft", headers=headers
            )

    def test_sales_can_read_charges(self) -> None:
        response = self._get(bearer_header(UserRole.SALES_CS))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["charges"][0]["charge_code"], "OF")

    def test_docs_cannot_read_charges(self) -> None:
        self.assertEqual(self._get(bearer_header(UserRole.DOCS)).status_code, 403)

    def test_unknown_email_is_404(self) -> None:
        with patch(
            "api.routes.quotes.build_charge_draft_from_email",
            new=AsyncMock(return_value=None),
        ):
            response = self.client.get(
                f"/api/v1/emails/{EMAIL_ID}/charge-draft",
                headers=bearer_header(UserRole.SALES_CS),
            )
        self.assertEqual(response.status_code, 404)

    def test_an_email_with_no_charges_still_returns_200(self) -> None:
        response = self._get(
            bearer_header(UserRole.SALES_CS),
            draft={
                "source_email_id": str(EMAIL_ID),
                "source_subject": "RE: Rate request",
                "source_from": "booking@carrier.com",
                "charges": [],
                "extraction_error": None,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["charges"], [])


if __name__ == "__main__":
    unittest.main()
