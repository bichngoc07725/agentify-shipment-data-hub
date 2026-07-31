"""Shared bearer-token helper for route tests.

Every route test that hits a `require_permission`-gated endpoint needs the
same two things: a stand-in user object with a role, and an Authorization
header built from a real JWT. This used to be copy-pasted into each test
module; keep it here so a change to the token shape is a one-file edit.
"""

from __future__ import annotations

from uuid import uuid4

from db.models import UserRole
from services.auth_service import create_access_token


class FakeUser:
    """Minimal duck-type of `db.models.User` — only what `create_access_token`
    reads (`id`, `username`, `role`)."""

    def __init__(self, role: UserRole, username: str = "tester") -> None:
        self.id = uuid4()
        self.username = username
        self.role = role


def bearer_header(role: UserRole, username: str = "tester") -> dict[str, str]:
    token = create_access_token(FakeUser(role, username))
    return {"Authorization": f"Bearer {token}"}
