import unittest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from api import app
from api.routes import api_main  # noqa: F401  (registers every router on `app`)
from db.database import get_db
from db.models import UserRole
from tests.auth_helpers import bearer_header

EMAIL_ID = uuid4()


def make_draft(**overrides):
    draft = {
        "source_email_id": str(EMAIL_ID),
        "source_subject": "Hỏi giá cước Da Nang đi Singapore",
        "source_from": "sales@taynguyencoffee.vn",
        "fields": {"pol": "Da Nang", "pod": "Singapore", "container_type": "20GP"},
        "fields_found": ["container_type", "pod", "pol"],
        "extraction_error": None,
    }
    draft.update(overrides)
    return draft


class QuoteDraftRouteTest(unittest.TestCase):
    def setUp(self) -> None:
        app.dependency_overrides[get_db] = lambda: None
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def _get(self, headers: dict[str, str], draft=None):
        with patch(
            "api.routes.quotes.build_quote_draft_from_email",
            new=AsyncMock(return_value=draft if draft is not None else make_draft()),
        ):
            return self.client.get(
                f"/api/v1/emails/{EMAIL_ID}/quote-draft", headers=headers
            )

    def test_sales_can_read_a_draft(self) -> None:
        response = self._get(bearer_header(UserRole.SALES_CS))

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["fields"]["pol"], "Da Nang")
        self.assertEqual(body["fields_found"], ["container_type", "pod", "pol"])

    def test_docs_cannot_read_a_draft(self) -> None:
        # `quote.create` chỉ thuộc sales_cs — vai trò chỉ-xem không được kích
        # hoạt một lượt gọi trích xuất tốn phí.
        self.assertEqual(self._get(bearer_header(UserRole.DOCS)).status_code, 403)

    def test_manager_cannot_read_a_draft(self) -> None:
        self.assertEqual(self._get(bearer_header(UserRole.MANAGER)).status_code, 403)

    def test_no_token_is_rejected(self) -> None:
        self.assertEqual(self._get({}).status_code, 401)

    def test_unknown_email_is_404(self) -> None:
        with patch(
            "api.routes.quotes.build_quote_draft_from_email",
            new=AsyncMock(return_value=None),
        ):
            response = self.client.get(
                f"/api/v1/emails/{EMAIL_ID}/quote-draft",
                headers=bearer_header(UserRole.SALES_CS),
            )
        self.assertEqual(response.status_code, 404)

    def test_an_email_with_nothing_extractable_still_returns_200(self) -> None:
        # Đọc được email nhưng không rút ra trường nào là kết quả hợp lệ, khác
        # hẳn "không có email" — Sales vẫn mở form và gõ tay.
        response = self._get(
            bearer_header(UserRole.SALES_CS),
            draft=make_draft(fields={}, fields_found=[]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["fields_found"], [])

    def test_extraction_failure_is_surfaced_not_hidden(self) -> None:
        response = self._get(
            bearer_header(UserRole.SALES_CS),
            draft=make_draft(fields={}, fields_found=[], extraction_error="429 quota"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["extraction_error"], "429 quota")


if __name__ == "__main__":
    unittest.main()
