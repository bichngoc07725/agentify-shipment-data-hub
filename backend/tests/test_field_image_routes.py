import unittest
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from api import app
from api.routes import api_main  # noqa: F401  (registers every router on `app`)
from db.database import get_db
from db.models import UserRole
from tests.auth_helpers import bearer_header




def make_attachment(**overrides):
    defaults = dict(
        id=uuid4(),
        filename="photo.jpg",
        mime_type="image/jpeg",
        storage_path="storage/field_images/abc/photo.jpg",
        document_type="container_photo",
        extracted_record={"doc_kind": "container_photo"},
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


class PreviewFieldImagePermissionTest(BaseRouteTest):
    def _upload(self, headers: dict[str, str]):
        attachment = make_attachment()
        preview_result = {
            "attachment": attachment,
            "vision": {
                "container_no": "CSQU3054383",
                "container_no_valid": True,
                "seal_no": "SL-1",
                "license_plate": None,
                "doc_kind": "container_photo",
                "depot": None,
                "datetime_text": None,
                "raw_text": None,
                "confidence": 0.9,
                "extraction_status": "ok",
                "extraction_error": None,
            },
            "matched_container": "CSQU3054383",
        }
        with (
            patch(
                "api.routes.field_images.preview_field_image",
                new=AsyncMock(return_value=preview_result),
            ),
            patch(
                "api.routes.field_images.attachment_file_url",
                return_value="/api/v1/attachments/x/file",
            ),
        ):
            return self.client.post(
                "/api/v1/field-images/preview",
                files={"file": ("photo.jpg", b"fake-image-bytes", "image/jpeg")},
                headers=headers,
            )

    def test_ops_can_upload(self) -> None:
        response = self._upload(bearer_header(UserRole.OPS))
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["container_no_valid"])
        self.assertEqual(body["container_no"], "CSQU3054383")

    def test_driver_can_upload(self) -> None:
        response = self._upload(bearer_header(UserRole.DRIVER))
        self.assertEqual(response.status_code, 200)

    def test_sales_cs_cannot_upload(self) -> None:
        response = self._upload(bearer_header(UserRole.SALES_CS))
        self.assertEqual(response.status_code, 403)

    def test_docs_cannot_upload(self) -> None:
        response = self._upload(bearer_header(UserRole.DOCS))
        self.assertEqual(response.status_code, 403)

    def test_accountant_cannot_upload(self) -> None:
        response = self._upload(bearer_header(UserRole.ACCOUNTANT))
        self.assertEqual(response.status_code, 403)

    def test_non_image_file_is_rejected(self) -> None:
        response = self.client.post(
            "/api/v1/field-images/preview",
            files={"file": ("doc.pdf", b"%PDF-1.4", "application/pdf")},
            headers=bearer_header(UserRole.OPS),
        )
        self.assertEqual(response.status_code, 400)


class ConfirmFieldImagePermissionTest(BaseRouteTest):
    def _confirm(self, headers: dict[str, str]):
        attachment = make_attachment()
        with patch(
            "api.routes.field_images.confirm_field_image",
            new=AsyncMock(return_value=(attachment, 2)),
        ):
            return self.client.post(
                "/api/v1/field-images",
                json={"image_id": str(uuid4()), "container_no": "CSQU3054383", "seal_no": "SL-1"},
                headers=headers,
            )

    def test_ops_can_confirm(self) -> None:
        response = self._confirm(bearer_header(UserRole.OPS))
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["fact_count"], 2)
        self.assertEqual(body["container_no"], "CSQU3054383")

    def test_driver_can_confirm(self) -> None:
        response = self._confirm(bearer_header(UserRole.DRIVER))
        self.assertEqual(response.status_code, 200)

    def test_docs_cannot_confirm(self) -> None:
        response = self._confirm(bearer_header(UserRole.DOCS))
        self.assertEqual(response.status_code, 403)

    def test_unknown_image_id_is_404(self) -> None:
        with patch(
            "api.routes.field_images.confirm_field_image",
            new=AsyncMock(side_effect=ValueError("Image 'x' not found")),
        ):
            response = self.client.post(
                "/api/v1/field-images",
                json={"image_id": str(uuid4()), "container_no": "CSQU3054383"},
                headers=bearer_header(UserRole.OPS),
            )
        self.assertEqual(response.status_code, 404)


class ContainerFieldImagesViewTest(BaseRouteTest):
    def test_admin_can_view(self) -> None:
        with (
            patch(
                "api.routes.field_images.get_container_by_no",
                new=AsyncMock(return_value=SimpleNamespace(id=uuid4())),
            ),
            patch(
                "api.routes.field_images.list_field_images_for_container",
                new=AsyncMock(return_value=[make_attachment()]),
            ),
            patch(
                "api.routes.field_images.attachment_file_url",
                return_value="/api/v1/attachments/x/file",
            ),
        ):
            response = self.client.get(
                "/api/v1/containers/CSQU3054383/images",
                headers=bearer_header(UserRole.ADMIN),
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["items"]), 1)

    def test_unknown_container_is_404(self) -> None:
        with patch(
            "api.routes.field_images.get_container_by_no", new=AsyncMock(return_value=None)
        ):
            response = self.client.get(
                "/api/v1/containers/NOSUCH0000000/images",
                headers=bearer_header(UserRole.ADMIN),
            )
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
