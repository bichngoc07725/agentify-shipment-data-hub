import unittest

from fastapi.testclient import TestClient

from api import app
from api.routes import api_main  # noqa: F401  (registers every router on `app`)
from config.permissions import PERMISSIONS
from db.database import get_db
from db.models import UserRole
from tests.auth_helpers import bearer_header




class BaseRouteTest(unittest.TestCase):
    def setUp(self) -> None:
        app.dependency_overrides[get_db] = lambda: None
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()


class PermissionMatrixTest(BaseRouteTest):
    def test_admin_gets_the_matrix_serialized_from_permissions_py(self) -> None:
        response = self.client.get(
            "/api/v1/admin/permissions", headers=bearer_header(UserRole.ADMIN)
        )
        self.assertEqual(response.status_code, 200)
        matrix = response.json()["matrix"]

        # No separate source of truth: the response must literally reflect
        # `config/permissions.py::PERMISSIONS`, not a hand-copied version.
        self.assertEqual(
            set(matrix["customs_declaration"]["view"]),
            {"admin", "manager", "docs", "ops", "accountant"},
        )
        self.assertEqual(matrix["audit"]["view"], ["admin"])
        self.assertEqual(set(matrix.keys()), set(PERMISSIONS.keys()))

    def test_manager_can_view(self) -> None:
        response = self.client.get(
            "/api/v1/admin/permissions", headers=bearer_header(UserRole.MANAGER)
        )
        self.assertEqual(response.status_code, 200)

    def test_sales_cs_cannot_view(self) -> None:
        response = self.client.get(
            "/api/v1/admin/permissions", headers=bearer_header(UserRole.SALES_CS)
        )
        self.assertEqual(response.status_code, 403)

    def test_ops_cannot_view(self) -> None:
        response = self.client.get(
            "/api/v1/admin/permissions", headers=bearer_header(UserRole.OPS)
        )
        self.assertEqual(response.status_code, 403)

    def test_driver_cannot_view(self) -> None:
        response = self.client.get(
            "/api/v1/admin/permissions", headers=bearer_header(UserRole.DRIVER)
        )
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
