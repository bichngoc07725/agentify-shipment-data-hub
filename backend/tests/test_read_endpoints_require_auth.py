"""Regression guard: every read endpoint must demand a token.

These routes shipped unauthenticated even though `config/permissions.py`
already declared `view` rules for them — the matrix entries were dead code.
A missing dependency is invisible in a normal happy-path test (which sends a
token anyway), so assert the *absence* of a token is rejected.
"""

import unittest
from uuid import uuid4

from fastapi.testclient import TestClient

from api import app
from api.routes import api_main  # noqa: F401  (registers every router on `app`)
from db.database import get_db
from db.models import UserRole
from tests.auth_helpers import bearer_header

# (method, path) for endpoints that read or trigger work and must be gated.
GATED_ENDPOINTS = [
    ("GET", "/api/v1/app-home"),
    ("GET", "/api/v1/containers"),
    ("GET", "/api/v1/containers/MSCU1234567"),
    ("GET", "/api/v1/containers/MSCU1234567/facts"),
    ("GET", "/api/v1/containers/MSCU1234567/exceptions"),
    ("GET", "/api/v1/exceptions"),
    ("GET", "/api/v1/emails"),
    (
        "GET",
        f"/api/v1/emails/{uuid4()}",
    ),
    (
        "GET",
        f"/api/v1/attachments/{uuid4()}/file",
    ),
    ("GET", "/api/v1/sync-jobs"),
    ("POST", "/api/v1/sync-jobs"),
    (
        "POST",
        f"/api/v1/sync-jobs/{uuid4()}/run",
    ),
]


class ReadEndpointsRequireAuthTest(unittest.TestCase):
    def setUp(self) -> None:
        app.dependency_overrides[get_db] = lambda: None
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_no_token_is_rejected(self) -> None:
        for method, path in GATED_ENDPOINTS:
            with self.subTest(endpoint=f"{method} {path}"):
                response = self.client.request(method, path)
                self.assertEqual(
                    response.status_code,
                    401,
                    f"{method} {path} answered without a token",
                )

    def test_driver_cannot_read_fleet_wide_data(self) -> None:
        """Driver is deliberately excluded from `ALL_STAFF` — they only ever
        see rows scoped to themselves (see `config/permissions.py`)."""

        for method, path in GATED_ENDPOINTS:
            with self.subTest(endpoint=f"{method} {path}"):
                response = self.client.request(
                    method, path, headers=bearer_header(UserRole.DRIVER)
                )
                self.assertEqual(
                    response.status_code,
                    403,
                    f"{method} {path} let a driver through",
                )

    def test_sync_jobs_are_admin_only(self) -> None:
        """Running a Gmail sync is `system_config` — Ops must not trigger it."""

        response = self.client.post(
            f"/api/v1/sync-jobs/{uuid4()}/run", headers=bearer_header(UserRole.OPS)
        )
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
