import unittest
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from api import app
from api.routes import api_main  # noqa: F401  (registers every router on `app`)
from db.database import get_db
from db.models import CustomsChannel, CustomsDeclarationType, UserRole
from tests.auth_helpers import bearer_header




def make_declaration(**overrides):
    defaults = dict(
        id=uuid4(),
        container_id=uuid4(),
        container=SimpleNamespace(container_no="MSCU1234567"),
        declaration_no="TK-2026-0001",
        declaration_type=CustomsDeclarationType.IMPORT,
        channel=CustomsChannel.RED,
        hs_code="8471.30.90",
        registered_at=None,
        cleared_at=None,
        tax_amount=None,
        note=None,
        created_by=uuid4(),
        channel_history=[],
        created_at=datetime.now(UTC),
        updated_at=None,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class BaseRouteTest(unittest.TestCase):
    def setUp(self) -> None:
        app.dependency_overrides[get_db] = lambda: None
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()


class CreateDeclarationPermissionTest(BaseRouteTest):
    def _create(self, headers: dict[str, str]):
        with patch(
            "api.routes.customs.create_declaration",
            new=AsyncMock(return_value=make_declaration()),
        ):
            return self.client.post(
                "/api/v1/customs/declarations",
                json={"container_no": "MSCU1234567", "channel": "red"},
                headers=headers,
            )

    def test_ops_can_create(self) -> None:
        response = self._create(bearer_header(UserRole.OPS))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["channel"], "red")

    def test_docs_cannot_create(self) -> None:
        response = self._create(bearer_header(UserRole.DOCS))
        self.assertEqual(response.status_code, 403)

    def test_admin_cannot_create(self) -> None:
        """Admin edits/reviews declarations, but Ops is the one who actually
        registers them, per the brief's least-privilege split."""
        response = self._create(bearer_header(UserRole.ADMIN))
        self.assertEqual(response.status_code, 403)

    def test_accountant_cannot_create(self) -> None:
        response = self._create(bearer_header(UserRole.ACCOUNTANT))
        self.assertEqual(response.status_code, 403)


class UpdateDeclarationPermissionTest(BaseRouteTest):
    def _update(self, headers: dict[str, str]):
        declaration = make_declaration(channel=CustomsChannel.GREEN)
        updated = make_declaration(id=declaration.id, channel=CustomsChannel.RED)
        with (
            patch(
                "api.routes.customs.get_declaration",
                new=AsyncMock(return_value=declaration),
            ),
            patch(
                "api.routes.customs.update_declaration",
                new=AsyncMock(return_value=updated),
            ),
        ):
            return self.client.put(
                f"/api/v1/customs/declarations/{declaration.id}",
                json={"declaration_type": "import", "channel": "red"},
                headers=headers,
            )

    def test_ops_can_edit(self) -> None:
        response = self._update(bearer_header(UserRole.OPS))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["channel"], "red")

    def test_admin_can_edit(self) -> None:
        response = self._update(bearer_header(UserRole.ADMIN))
        self.assertEqual(response.status_code, 200)

    def test_docs_cannot_edit(self) -> None:
        response = self._update(bearer_header(UserRole.DOCS))
        self.assertEqual(response.status_code, 403)

    def test_accountant_cannot_edit(self) -> None:
        response = self._update(bearer_header(UserRole.ACCOUNTANT))
        self.assertEqual(response.status_code, 403)

    def test_unknown_declaration_is_404(self) -> None:
        with patch(
            "api.routes.customs.get_declaration", new=AsyncMock(return_value=None)
        ):
            response = self.client.put(
                f"/api/v1/customs/declarations/{uuid4()}",
                json={"declaration_type": "import"},
                headers=bearer_header(UserRole.OPS),
            )
        self.assertEqual(response.status_code, 404)


class ViewDeclarationPermissionTest(BaseRouteTest):
    def test_admin_manager_docs_ops_accountant_can_view(self) -> None:
        for role in [
            UserRole.ADMIN,
            UserRole.MANAGER,
            UserRole.DOCS,
            UserRole.OPS,
            UserRole.ACCOUNTANT,
        ]:
            with self.subTest(role=role):
                declaration = make_declaration()
                with patch(
                    "api.routes.customs.get_declaration",
                    new=AsyncMock(return_value=declaration),
                ):
                    response = self.client.get(
                        f"/api/v1/customs/declarations/{declaration.id}",
                        headers=bearer_header(role),
                    )
                self.assertEqual(response.status_code, 200)

    def test_sales_cs_cannot_view(self) -> None:
        response = self.client.get(
            f"/api/v1/customs/declarations/{uuid4()}",
            headers=bearer_header(UserRole.SALES_CS),
        )
        self.assertEqual(response.status_code, 403)

    def test_driver_cannot_view(self) -> None:
        response = self.client.get(
            f"/api/v1/customs/declarations/{uuid4()}",
            headers=bearer_header(UserRole.DRIVER),
        )
        self.assertEqual(response.status_code, 403)

    def test_unknown_declaration_is_404(self) -> None:
        with patch(
            "api.routes.customs.get_declaration", new=AsyncMock(return_value=None)
        ):
            response = self.client.get(
                f"/api/v1/customs/declarations/{uuid4()}",
                headers=bearer_header(UserRole.ACCOUNTANT),
            )
        self.assertEqual(response.status_code, 404)


class ContainerCustomsListTest(BaseRouteTest):
    def test_container_declarations_are_listed(self) -> None:
        declaration = make_declaration()
        with (
            patch(
                "api.routes.customs.get_container_by_no",
                new=AsyncMock(return_value=SimpleNamespace(id=uuid4())),
            ),
            patch(
                "api.routes.customs.list_declarations_for_container",
                new=AsyncMock(return_value=[declaration]),
            ),
        ):
            response = self.client.get(
                "/api/v1/containers/MSCU1234567/customs",
                headers=bearer_header(UserRole.DOCS),
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 1)

    def test_driver_cannot_view_container_customs(self) -> None:
        response = self.client.get(
            "/api/v1/containers/MSCU1234567/customs",
            headers=bearer_header(UserRole.DRIVER),
        )
        self.assertEqual(response.status_code, 403)

    def test_unknown_container_is_404(self) -> None:
        with patch(
            "api.routes.customs.get_container_by_no", new=AsyncMock(return_value=None)
        ):
            response = self.client.get(
                "/api/v1/containers/NOSUCH0000000/customs",
                headers=bearer_header(UserRole.OPS),
            )
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
