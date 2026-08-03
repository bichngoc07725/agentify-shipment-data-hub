from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps.permissions import CurrentUser, get_current_user, require_permission
from api.models import (
    ContainerRiskProfileResponse,
    ExceptionActionRequest,
    ExceptionActionResponse,
    ShipmentExceptionListResponse,
    ShipmentExceptionResponse,
)
from config.permissions import EXCEPTION_ACTIONS_BY_SEVERITY, exception_severity_tier
from db.database import get_db
from services.audit_service import record_audit
from services.container_service import get_container_by_no
from services.exception_action_service import record_exception_action
from services.exception_service import (
    ShipmentException,
    get_container_risk_profile,
    list_shipment_exceptions,
)

router = APIRouter(prefix="/api/v1", tags=["exceptions"])


def _to_response(exception: ShipmentException) -> ShipmentExceptionResponse:
    return ShipmentExceptionResponse(
        container_no=exception.container_no,
        code=exception.code,
        severity=exception.severity,
        title=exception.title,
        detail=exception.detail,
        evidence=exception.evidence,
        due_date=exception.due_date,
        days_remaining=exception.days_remaining,
    )


@router.get("/exceptions", response_model=ShipmentExceptionListResponse)
async def list_exceptions_endpoint(
    severity: str | None = Query(default=None),
    code: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_permission("exception", "view")),
) -> ShipmentExceptionListResponse:
    exceptions = await list_shipment_exceptions(
        db, severity=severity, code=code, limit=limit
    )

    counts: dict[str, int] = {}
    for exception in exceptions:
        counts[exception.severity] = counts.get(exception.severity, 0) + 1

    return ShipmentExceptionListResponse(
        items=[_to_response(exception) for exception in exceptions],
        total=len(exceptions),
        counts_by_severity=counts,
    )


@router.get(
    "/containers/{container_no}/exceptions",
    response_model=ContainerRiskProfileResponse,
)
async def get_container_exceptions_endpoint(
    container_no: str,
    db: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_permission("exception", "view")),
) -> ContainerRiskProfileResponse:
    container = await get_container_by_no(db, container_no)
    if container is None:
        raise HTTPException(status_code=404, detail="Container not found")

    profile = await get_container_risk_profile(db, container)
    return ContainerRiskProfileResponse(
        container_no=profile.container_no,
        direction=profile.direction,
        exceptions=[_to_response(exception) for exception in profile.exceptions],
        documents_present=profile.documents_present,
        documents_mentioned=profile.documents_mentioned,
        documents_missing=profile.documents_missing,
        completeness=profile.completeness,
        free_time_expires_on=profile.free_time_expires_on,
        free_time_is_assumed=profile.free_time_is_assumed,
    )


async def _find_container_exception(
    db: AsyncSession, container_no: str, code: str
) -> tuple[object, ShipmentException]:
    container = await get_container_by_no(db, container_no)
    if container is None:
        raise HTTPException(status_code=404, detail="Container not found")

    profile = await get_container_risk_profile(db, container)
    exception = next((exc for exc in profile.exceptions if exc.code == code), None)
    if exception is None:
        raise HTTPException(
            status_code=404,
            detail=f"Exception '{code}' is not currently open for {container_no}",
        )
    return container, exception


async def _act_on_exception(
    db: AsyncSession,
    container_no: str,
    code: str,
    action: str,
    payload: ExceptionActionRequest,
    current_user: CurrentUser,
) -> ExceptionActionResponse:
    container, exception = await _find_container_exception(db, container_no, code)
    tier = exception_severity_tier(exception.severity)

    allowed_roles = EXCEPTION_ACTIONS_BY_SEVERITY.get(tier, {}).get(action, set())
    if current_user.role not in allowed_roles:
        raise HTTPException(
            status_code=403,
            detail=(
                f"Role '{current_user.role.value}' cannot '{action}' a "
                f"'{tier}' severity exception"
            ),
        )

    entry = await record_exception_action(
        db,
        container_id=container.id,
        code=code,
        action=action,
        severity_tier=tier,
        acted_by_user_id=UUID(current_user.user_id),
        acted_by_username=current_user.username,
        acted_by_role=current_user.role,
        note=payload.note,
    )

    # A "critical" exception can only ever be *approved* (see
    # EXCEPTION_ACTIONS_BY_SEVERITY) — that approval is the dispute-evidence
    # moment 8A exists for, so it's the only exception action logged here.
    if tier == "critical":
        await record_audit(
            db,
            user_id=UUID(current_user.user_id),
            role_used=current_user.role,
            action=action,
            resource_type="exception",
            resource_id=container.id,
            detail={"code": code, "container_no": container_no.upper(), "note": payload.note},
        )

    return ExceptionActionResponse(
        container_no=container_no.upper(),
        code=entry.code,
        action=entry.action,
        severity_tier=entry.severity_tier,
        acted_by_username=entry.acted_by_username,
        acted_by_role=entry.acted_by_role,
        note=entry.note,
    )


@router.post(
    "/containers/{container_no}/exceptions/{code}/resolve",
    response_model=ExceptionActionResponse,
)
async def resolve_exception_endpoint(
    container_no: str,
    code: str,
    payload: ExceptionActionRequest = ExceptionActionRequest(),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> ExceptionActionResponse:
    return await _act_on_exception(
        db, container_no, code, "resolve", payload, current_user
    )


@router.post(
    "/containers/{container_no}/exceptions/{code}/approve",
    response_model=ExceptionActionResponse,
)
async def approve_exception_endpoint(
    container_no: str,
    code: str,
    payload: ExceptionActionRequest = ExceptionActionRequest(),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> ExceptionActionResponse:
    return await _act_on_exception(
        db, container_no, code, "approve", payload, current_user
    )
