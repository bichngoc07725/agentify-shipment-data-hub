"""FastAPI dependencies that enforce `config/permissions.py` against the
caller's JWT. A user has exactly one role — enforcement here never unions
permissions across roles."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status
from jwt import PyJWTError

from config.permissions import PERMISSIONS
from db.models import UserRole
from services.auth_service import decode_access_token


@dataclass(frozen=True)
class CurrentUser:
    user_id: str
    username: str
    role: UserRole


async def get_current_user(
    authorization: str | None = Header(default=None),
) -> CurrentUser:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )

    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_access_token(token)
    except PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc

    try:
        role = UserRole(payload["role"])
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is missing a valid role",
        ) from exc

    return CurrentUser(
        user_id=payload["sub"], username=payload["username"], role=role
    )


def require_permission(
    resource: str, action: str
) -> Callable[[CurrentUser], Awaitable[CurrentUser]]:
    """Dependency factory: 403 unless the caller's role is allowed `action`
    on `resource` per the static matrix in `config/permissions.py`.

    Returns the `CurrentUser` on success so handlers needing the role for a
    second-layer check (e.g. container_facts field groups) don't have to
    decode the token twice.
    """

    allowed_roles = PERMISSIONS.get(resource, {}).get(action, set())

    async def _check(
        current_user: CurrentUser = Depends(get_current_user),
    ) -> CurrentUser:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Role '{current_user.role.value}' cannot '{action}' "
                    f"on '{resource}'"
                ),
            )
        return current_user

    return _check
