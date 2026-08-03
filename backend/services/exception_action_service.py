"""Resolve/approve actions on a shipment exception.

Exceptions are computed live (see `exception_service.py`) — there is no row to
flip a status on. This records *who acted on what, and when* as an audit
trail (design doc §5.5), gated by severity tier: a "critical" exception
(credit-limit / large cost variance) may only ever be approved by
Admin/Manager, per `config.permissions.EXCEPTION_ACTIONS_BY_SEVERITY`.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from db.models import ExceptionAction, UserRole


async def record_exception_action(
    db: AsyncSession,
    container_id: UUID,
    code: str,
    action: str,
    severity_tier: str,
    acted_by_user_id: UUID,
    acted_by_username: str,
    acted_by_role: UserRole,
    note: str | None = None,
) -> ExceptionAction:
    entry = ExceptionAction(
        container_id=container_id,
        code=code,
        action=action,
        severity_tier=severity_tier,
        acted_by_user_id=acted_by_user_id,
        acted_by_username=acted_by_username,
        acted_by_role=acted_by_role.value,
        note=note,
    )
    db.add(entry)
    await db.flush()
    await db.refresh(entry)
    return entry
