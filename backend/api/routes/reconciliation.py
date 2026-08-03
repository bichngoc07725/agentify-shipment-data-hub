from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps.permissions import CurrentUser, require_permission
from api.models import (
    ReconciliationApproveRequest,
    ReconciliationCreateRequest,
    ReconciliationLineResponse,
    ReconciliationListResponse,
    ReconciliationResponse,
)
from db.database import get_db
from db.models import Reconciliation
from services.audit_service import record_audit
from services.container_service import get_container_by_no
from services.reconciliation_service import (
    approve_reconciliation,
    build_reconciliation,
    get_reconciliation,
    list_reconciliations_for_container,
)

router = APIRouter(prefix="/api/v1/reconciliation", tags=["reconciliation"])
container_router = APIRouter(prefix="/api/v1", tags=["reconciliation"])


def _to_response(reconciliation: Reconciliation) -> ReconciliationResponse:
    return ReconciliationResponse(
        id=reconciliation.id,
        container_id=reconciliation.container_id,
        container_no=(
            reconciliation.container.container_no if reconciliation.container else None
        ),
        quote_id=reconciliation.quote_id,
        quote_no=reconciliation.quote.quote_no if reconciliation.quote else None,
        status=reconciliation.status.value,
        total_quoted=reconciliation.total_quoted,
        total_actual=reconciliation.total_actual,
        total_variance=reconciliation.total_variance,
        needs_approval=reconciliation.needs_approval,
        created_by=reconciliation.created_by,
        approved_by=reconciliation.approved_by,
        lines=[
            ReconciliationLineResponse(
                id=line.id,
                charge_code=line.charge_code,
                quoted_amount=line.quoted_amount,
                actual_amount=line.actual_amount,
                variance=line.variance,
                match_status=line.match_status.value,
                note=line.note,
            )
            for line in reconciliation.lines
        ],
        created_at=reconciliation.created_at,
    )


@router.post("", response_model=ReconciliationResponse)
async def create_reconciliation_endpoint(
    payload: ReconciliationCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission("reconciliation", "create")),
) -> ReconciliationResponse:
    try:
        reconciliation = await build_reconciliation(
            db, payload.container_no, payload.quote_id, UUID(current_user.user_id)
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _to_response(reconciliation)


@router.get("/{reconciliation_id}", response_model=ReconciliationResponse)
async def get_reconciliation_endpoint(
    reconciliation_id: UUID,
    db: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_permission("reconciliation", "view")),
) -> ReconciliationResponse:
    reconciliation = await get_reconciliation(db, reconciliation_id)
    if reconciliation is None:
        raise HTTPException(status_code=404, detail="Reconciliation not found")
    return _to_response(reconciliation)


@router.post("/{reconciliation_id}/approve", response_model=ReconciliationResponse)
async def approve_reconciliation_endpoint(
    reconciliation_id: UUID,
    payload: ReconciliationApproveRequest = ReconciliationApproveRequest(),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission("reconciliation", "approve")),
) -> ReconciliationResponse:
    reconciliation = await get_reconciliation(db, reconciliation_id)
    if reconciliation is None:
        raise HTTPException(status_code=404, detail="Reconciliation not found")
    updated = await approve_reconciliation(db, reconciliation, UUID(current_user.user_id))
    await record_audit(
        db,
        user_id=UUID(current_user.user_id),
        role_used=current_user.role,
        action="approve",
        resource_type="reconciliation",
        resource_id=reconciliation.id,
        detail={"total_variance": str(reconciliation.total_variance)},
    )
    return _to_response(updated)


@container_router.get(
    "/containers/{container_no}/reconciliation", response_model=ReconciliationListResponse
)
async def list_container_reconciliation_endpoint(
    container_no: str,
    db: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_permission("reconciliation", "view")),
) -> ReconciliationListResponse:
    container = await get_container_by_no(db, container_no)
    if container is None:
        raise HTTPException(status_code=404, detail="Container not found")
    reconciliations = await list_reconciliations_for_container(db, container.id)
    return ReconciliationListResponse(
        items=[_to_response(r) for r in reconciliations], total=len(reconciliations)
    )
