"""Generic audit trail for sensitive operations — generalizes the
`exception_action_service` pattern (GĐ2) to any resource: critical-exception
approvals, manual container_fact edits, reconciliation approvals, ERP
exports. See `plan/phase_8_audit_zalo_brief.md` Part 8A.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models import AuditLog, UserRole

logger = logging.getLogger(__name__)


async def record_audit(
    db: AsyncSession,
    user_id: UUID,
    role_used: UserRole,
    action: str,
    resource_type: str,
    resource_id: UUID | None = None,
    detail: dict[str, Any] | None = None,
) -> AuditLog | None:
    """Best-effort: a failure here must never block the business action it
    is auditing, but must not fail silently either — log it for a dev to see."""

    try:
        entry = AuditLog(
            user_id=user_id,
            role_used=role_used,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            detail=detail,
        )
        db.add(entry)
        await db.flush()
        return entry
    except Exception:
        logger.exception(
            "record_audit failed: action=%s resource_type=%s resource_id=%s",
            action, resource_type, resource_id,
        )
        return None


async def list_audit_logs(
    db: AsyncSession,
    resource_type: str | None = None,
    user_id: UUID | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = 200,
) -> list[AuditLog]:
    query = select(AuditLog).options(selectinload(AuditLog.user))
    if resource_type:
        query = query.where(AuditLog.resource_type == resource_type)
    if user_id:
        query = query.where(AuditLog.user_id == user_id)
    if since:
        query = query.where(AuditLog.created_at >= since)
    if until:
        query = query.where(AuditLog.created_at <= until)
    query = query.order_by(AuditLog.created_at.desc()).limit(limit)
    result = await db.execute(query)
    return list(result.scalars().all())
