"""Phơi bày trạng thái trích xuất (P0-2).

Vấn đề gốc: OCR ảnh chưa từng chạy vì thiếu API key, nhưng hệ thống không hề
báo — ảnh vẫn upload thành công, mọi trường trả rỗng, người dùng tưởng "AI đọc
không ra". Endpoint này tồn tại để tình trạng đó không thể im lặng nữa.
"""

import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from api import app
from api.routes import api_main  # noqa: F401  (registers every router on `app`)
from db.database import get_db
from db.models import UserRole
from services import extraction_status_service as svc
from services.auth_service import create_access_token


class FakeUser:
    def __init__(self, role: UserRole) -> None:
        self.id = uuid4()
        self.username = "tester"
        self.role = role


def bearer(role: UserRole) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(FakeUser(role))}"}


class StatusLogicTest(unittest.TestCase):
    def test_provider_none_reports_both_capabilities_off(self) -> None:
        with (
            patch.object(svc, "EXTRACTION_PROVIDER", "none"),
            patch.object(svc, "VISION_PROVIDER", "none"),
            patch.object(svc, "azure_is_configured", lambda: False),
            patch.object(svc, "GEMINI_API_KEY", ""),
        ):
            status = svc.get_extraction_status()
        self.assertFalse(status["image_ocr"]["ready"])
        self.assertFalse(status["text_extraction"]["ready"])
        self.assertIn("none", status["image_ocr"]["reason"])

    def test_azure_configured_turns_both_on(self) -> None:
        with (
            patch.object(svc, "EXTRACTION_PROVIDER", "azure_openai"),
            patch.object(svc, "VISION_PROVIDER", "azure_openai"),
            patch.object(svc, "azure_is_configured", lambda: True),
        ):
            status = svc.get_extraction_status()
        self.assertTrue(status["image_ocr"]["ready"])
        self.assertTrue(status["text_extraction"]["ready"])
        self.assertEqual(status["missing_keys"], [])

    def test_gemini_alone_now_reads_BOTH_text_and_images(self) -> None:
        """Trước đây OCR ảnh chỉ chạy được với Azure, nên cấu hình chỉ có Gemini
        vẫn để đọc ảnh TẮT. Từ khi có `call_gemini_vision`, một khoá Gemini là
        đủ cho cả hai đường."""
        with (
            patch.object(svc, "EXTRACTION_PROVIDER", "gemini"),
            patch.object(svc, "VISION_PROVIDER", "gemini"),
            patch.object(svc, "azure_is_configured", lambda: False),
            patch.object(svc, "GEMINI_API_KEY", "fake-key"),
        ):
            status = svc.get_extraction_status()
        self.assertTrue(status["text_extraction"]["ready"])
        self.assertTrue(status["image_ocr"]["ready"])
        self.assertEqual(status["image_ocr"]["provider"], "gemini_vision")
        self.assertEqual(status["missing_keys"], [])

    def test_no_secret_value_is_ever_returned(self) -> None:
        """Chỉ trả TÊN biến còn thiếu, không bao giờ trả giá trị key."""
        with (
            patch.object(svc, "EXTRACTION_PROVIDER", "azure_openai"),
            patch.object(svc, "VISION_PROVIDER", "none"),
            patch.object(svc, "azure_is_configured", lambda: False),
            patch.object(svc, "AZURE_OPENAI_ENDPOINT", "https://secret.example.com"),
            patch.object(svc, "AZURE_OPENAI_DEPLOYMENT", "secret-deployment"),
            patch.object(svc, "GEMINI_API_KEY", "super-secret-value"),
        ):
            status = svc.get_extraction_status()
        blob = repr(status)
        self.assertNotIn("super-secret-value", blob)
        self.assertNotIn("secret.example.com", blob)


class StatusEndpointTest(unittest.TestCase):
    URL = "/api/v1/system/extraction-status"

    def setUp(self) -> None:
        app.dependency_overrides[get_db] = lambda: None
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_every_signed_in_role_can_read_it(self) -> None:
        """Ops và Tài xế là người upload ảnh nên phải biết OCR có bật không;
        đây là thông tin vận hành, không phải cấu hình bí mật."""
        for role in [UserRole.ADMIN, UserRole.OPS, UserRole.DRIVER, UserRole.SALES_CS]:
            with self.subTest(role=role):
                r = self.client.get(self.URL, headers=bearer(role))
                self.assertEqual(r.status_code, 200)
                self.assertIn("image_ocr", r.json())

    def test_anonymous_is_rejected(self) -> None:
        self.assertEqual(self.client.get(self.URL).status_code, 401)


if __name__ == "__main__":
    unittest.main()
