from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps.permissions import CurrentUser, require_permission
from api.models import (
    ShipmentAdvanceRequest,
    ShipmentMoveStageRequest,
    ShipmentBoardColumn,
    ShipmentBoardResponse,
    ShipmentCreateRequest,
    ShipmentListResponse,
    ShipmentResponse,
)
from db.database import get_db
from db.models import Shipment, ShipmentStage
from services.shipment_service import (
    STAGE_ORDER,
    StageAdvanceError,
    StageOwnerError,
    advance_stage,
    move_to_stage,
    create_shipment,
    get_board,
    get_shipment,
    is_sla_breached,
    list_shipments,
)

router = APIRouter(prefix="/api/v1/shipments", tags=["shipments"])


def _to_response(shipment: Shipment) -> ShipmentResponse:
    return ShipmentResponse(
        id=shipment.id,
        shipment_no=shipment.shipment_no,
        customer_name=shipment.customer_name,
        direction=shipment.direction.value if shipment.direction else None,
        stage=shipment.stage.value,
        quote_id=shipment.quote_id,
        quote_no=shipment.quote.quote_no if shipment.quote else None,
        owner_role=shipment.owner_role.value if shipment.owner_role else None,
        sla_due_at=shipment.sla_due_at,
        sla_breached=is_sla_breached(shipment),
        container_count=len(shipment.containers),
        container_nos=[c.container_no for c in shipment.containers],
        created_at=shipment.created_at,
        updated_at=shipment.updated_at,
    )


@router.post("", response_model=ShipmentResponse)
async def create_shipment_endpoint(
    payload: ShipmentCreateRequest,
    db: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_permission("shipment", "create")),
) -> ShipmentResponse:
    shipment = await create_shipment(db, payload)
    return _to_response(shipment)


@router.get("/board", response_model=ShipmentBoardResponse)
async def get_board_endpoint(
    db: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_permission("shipment", "view")),
) -> ShipmentBoardResponse:
    board = await get_board(db)
    return ShipmentBoardResponse(
        columns=[
            ShipmentBoardColumn(
                stage=stage.value,
                jobs=[_to_response(job) for job in board.columns[stage]],
            )
            for stage in STAGE_ORDER
        ]
    )


@router.get("", response_model=ShipmentListResponse)
async def list_shipments_endpoint(
    db: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_permission("shipment", "view")),
) -> ShipmentListResponse:
    shipments = await list_shipments(db)
    return ShipmentListResponse(
        items=[_to_response(s) for s in shipments], total=len(shipments)
    )


@router.get("/{shipment_id}", response_model=ShipmentResponse)
async def get_shipment_endpoint(
    shipment_id: UUID,
    db: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_permission("shipment", "view")),
) -> ShipmentResponse:
    shipment = await get_shipment(db, shipment_id)
    if shipment is None:
        raise HTTPException(status_code=404, detail="Shipment not found")
    return _to_response(shipment)


@router.post("/{shipment_id}/advance", response_model=ShipmentResponse)
async def advance_shipment_endpoint(
    shipment_id: UUID,
    _payload: ShipmentAdvanceRequest = ShipmentAdvanceRequest(),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission("shipment", "edit")),
) -> ShipmentResponse:
    shipment = await get_shipment(db, shipment_id)
    if shipment is None:
        raise HTTPException(status_code=404, detail="Shipment not found")
    try:
        updated = await advance_stage(db, shipment, current_user.role)
    except StageOwnerError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except StageAdvanceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _to_response(updated)


@router.post("/{shipment_id}/stage", response_model=ShipmentResponse)
async def move_shipment_stage_endpoint(
    shipment_id: UUID,
    payload: ShipmentMoveStageRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission("shipment", "edit")),
) -> ShipmentResponse:
    """Move a job to an explicit stage — what a Kanban drag actually means.

    `/advance` can only step forward one column, so dragging a card backwards
    (or across two columns) had no endpoint to call at all.
    """

    shipment = await get_shipment(db, shipment_id)
    if shipment is None:
        raise HTTPException(status_code=404, detail="Shipment not found")
    try:
        updated = await move_to_stage(
            db, shipment, ShipmentStage(payload.stage), current_user.role
        )
    except StageOwnerError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return _to_response(updated)
