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




def make_user(**overrides):
    defaults = dict(
        id=uuid4(),
        username="ops2",
        display_name="Vận hành 2",
        role=UserRole.OPS,
        is_active=True,
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


class ListUsersPermissionTest(BaseRouteTest):
    def test_admin_can_list(self) -> None:
        with patch(
            "api.routes.users.list_users", new=AsyncMock(return_value=[make_user()])
        ):
            response = self.client.get("/api/v1/users", headers=bearer_header(UserRole.ADMIN))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 1)
        self.assertEqual(response.json()["items"][0]["username"], "ops2")

    def test_manager_can_list(self) -> None:
        """`system_config.view` includes Manager, per the existing matrix."""
        with patch(
            "api.routes.users.list_users", new=AsyncMock(return_value=[])
        ):
            response = self.client.get("/api/v1/users", headers=bearer_header(UserRole.MANAGER))
        self.assertEqual(response.status_code, 200)

    def test_sales_cs_cannot_list(self) -> None:
        response = self.client.get("/api/v1/users", headers=bearer_header(UserRole.SALES_CS))
        self.assertEqual(response.status_code, 403)

    def test_ops_cannot_list(self) -> None:
        response = self.client.get("/api/v1/users", headers=bearer_header(UserRole.OPS))
        self.assertEqual(response.status_code, 403)


class CreateUserPermissionTest(BaseRouteTest):
    def _create(self, headers: dict[str, str], role: str = "ops"):
        with patch(
            "api.routes.users.create_user",
            new=AsyncMock(return_value=make_user(role=UserRole(role))),
        ):
            return self.client.post(
                "/api/v1/users",
                json={
                    "username": "new_user",
                    "display_name": "New User",
                    "role": role,
                    "password": "secret123",
                },
                headers=headers,
            )

    def test_admin_can_create(self) -> None:
        response = self._create(bearer_header(UserRole.ADMIN))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["role"], "ops")

    def test_manager_cannot_create(self) -> None:
        """`system_config.create` is Admin-only — Manager is view-only."""
        response = self._create(bearer_header(UserRole.MANAGER))
        self.assertEqual(response.status_code, 403)

    def test_invalid_role_is_422_not_500(self) -> None:
        response = self.client.post(
            "/api/v1/users",
            json={
                "username": "bad_role_user",
                "display_name": "Bad Role",
                "role": "superuser",
                "password": "secret123",
            },
            headers=bearer_header(UserRole.ADMIN),
        )
        self.assertEqual(response.status_code, 422)

    def test_duplicate_username_is_400(self) -> None:
        with patch(
            "api.routes.users.create_user",
            new=AsyncMock(side_effect=ValueError("Username 'ops2' already exists")),
        ):
            response = self.client.post(
                "/api/v1/users",
                json={
                    "username": "ops2",
                    "display_name": "Dup",
                    "role": "ops",
                    "password": "secret123",
                },
                headers=bearer_header(UserRole.ADMIN),
            )
        self.assertEqual(response.status_code, 400)


class UpdateUserPermissionTest(BaseRouteTest):
    def _update(self, headers: dict[str, str], payload: dict):
        user = make_user()
        updated = make_user(id=user.id, **{k: v for k, v in payload.items() if k != "role" or True})
        if "role" in payload:
            updated.role = UserRole(payload["role"])
        if "is_active" in payload:
            updated.is_active = payload["is_active"]
        with (
            patch(
                "api.routes.users.get_user_by_id", new=AsyncMock(return_value=user)
            ),
            patch(
                "api.routes.users.update_user", new=AsyncMock(return_value=updated)
            ),
        ):
            return self.client.patch(
                f"/api/v1/users/{user.id}", json=payload, headers=headers
            )

    def test_admin_can_change_role(self) -> None:
        response = self._update(bearer_header(UserRole.ADMIN), {"role": "docs"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["role"], "docs")

    def test_admin_can_deactivate(self) -> None:
        response = self._update(bearer_header(UserRole.ADMIN), {"is_active": False})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["is_active"])

    def test_manager_cannot_edit(self) -> None:
        response = self._update(bearer_header(UserRole.MANAGER), {"is_active": False})
        self.assertEqual(response.status_code, 403)

    def test_unknown_user_is_404(self) -> None:
        with patch(
            "api.routes.users.get_user_by_id", new=AsyncMock(return_value=None)
        ):
            response = self.client.patch(
                f"/api/v1/users/{uuid4()}",
                json={"is_active": False},
                headers=bearer_header(UserRole.ADMIN),
            )
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
