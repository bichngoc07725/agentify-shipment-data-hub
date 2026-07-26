from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import (
    ContainerRiskProfileResponse,
    ShipmentExceptionListResponse,
    ShipmentExceptionResponse,
)
from db.database import get_db
from services.container_service import get_container_by_no
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
