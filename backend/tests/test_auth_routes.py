import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from api import app
from api.routes import api_main  # noqa: F401  (registers every router on `app`)
from db.database import get_db
from db.models import User, UserRole
from services.auth_service import decode_access_token


def make_user(**overrides) -> User:
    defaults = dict(
        id=uuid4(),
        username="admin",
        password_hash="not-checked-because-authenticate_user-is-mocked",
        display_name="Quản trị hệ thống",
        role=UserRole.ADMIN,
        is_active=True,
    )
    defaults.update(overrides)
    user = User()
    for key, value in defaults.items():
        setattr(user, key, value)
    return user


class LoginRouteTest(unittest.TestCase):
    def setUp(self) -> None:
        app.dependency_overrides[get_db] = lambda: None
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_correct_password_returns_token_with_a_single_role(self) -> None:
        user = make_user(role=UserRole.MANAGER)

        with patch("api.routes.auth.authenticate_user", return_value=user):
            response = self.client.post(
                "/api/v1/auth/login",
                json={"username": "admin", "password": "admin@123"},
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["role"], "manager")
        self.assertEqual(body["username"], "admin")
        self.assertIn("access_token", body)

        payload = decode_access_token(body["access_token"])
        self.assertEqual(payload["role"], "manager")
        self.assertEqual(payload["sub"], str(user.id))

    def test_wrong_password_returns_401(self) -> None:
        with patch("api.routes.auth.authenticate_user", return_value=None):
            response = self.client.post(
                "/api/v1/auth/login",
                json={"username": "admin", "password": "wrong-password"},
            )

        self.assertEqual(response.status_code, 401)
        self.assertNotIn("access_token", response.json())


if __name__ == "__main__":
    unittest.main()
