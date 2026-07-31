from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps.permissions import CurrentUser, require_permission
from api.models import AuditLogListResponse, AuditLogResponse
from db.database import get_db
from db.models import AuditLog
from services.audit_service import list_audit_logs

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


def _to_response(entry: AuditLog) -> AuditLogResponse:
    return AuditLogResponse(
        id=entry.id,
        user_id=entry.user_id,
        username=entry.user.username if entry.user else None,
        role_used=entry.role_used.value,
        action=entry.action,
        resource_type=entry.resource_type,
        resource_id=entry.resource_id,
        detail=entry.detail,
        created_at=entry.created_at,
    )


@router.get("", response_model=AuditLogListResponse)
async def list_audit_logs_endpoint(
    resource_type: str | None = Query(default=None),
    user_id: UUID | None = Query(default=None),
    since: datetime | None = Query(default=None),
    until: datetime | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_permission("audit", "view")),
) -> AuditLogListResponse:
    entries = await list_audit_logs(
        db, resource_type=resource_type, user_id=user_id, since=since, until=until, limit=limit
    )
    return AuditLogListResponse(
        items=[_to_response(e) for e in entries], total=len(entries)
    )
