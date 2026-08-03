from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps.permissions import CurrentUser, require_permission
from api.models import (
    CustomsChannelHistoryResponse,
    CustomsDeclarationCreateRequest,
    CustomsDeclarationListResponse,
    CustomsDeclarationResponse,
    CustomsDeclarationUpdateRequest,
)
from db.database import get_db
from db.models import CustomsDeclaration
from services.container_service import get_container_by_no
from services.customs_service import (
    create_declaration,
    get_declaration,
    list_declarations_for_container,
    update_declaration,
)

router = APIRouter(prefix="/api/v1/customs", tags=["customs"])
container_router = APIRouter(prefix="/api/v1", tags=["customs"])


def _to_response(declaration: CustomsDeclaration) -> CustomsDeclarationResponse:
    return CustomsDeclarationResponse(
        id=declaration.id,
        container_id=declaration.container_id,
        container_no=(
            declaration.container.container_no if declaration.container else None
        ),
        declaration_no=declaration.declaration_no,
        declaration_type=declaration.declaration_type.value,
        channel=declaration.channel.value if declaration.channel else None,
        hs_code=declaration.hs_code,
        registered_at=declaration.registered_at,
        cleared_at=declaration.cleared_at,
        tax_amount=declaration.tax_amount,
        note=declaration.note,
        created_by=declaration.created_by,
        channel_history=[
            CustomsChannelHistoryResponse(
                id=h.id,
                from_channel=h.from_channel.value if h.from_channel else None,
                to_channel=h.to_channel.value,
                changed_at=h.changed_at,
                changed_by=h.changed_by,
                reason=h.reason,
            )
            for h in declaration.channel_history
        ],
        created_at=declaration.created_at,
        updated_at=declaration.updated_at,
    )


@router.post("/declarations", response_model=CustomsDeclarationResponse)
async def create_declaration_endpoint(
    payload: CustomsDeclarationCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_permission("customs_declaration", "create")
    ),
) -> CustomsDeclarationResponse:
    try:
        declaration = await create_declaration(db, payload, UUID(current_user.user_id))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _to_response(declaration)


@router.put("/declarations/{declaration_id}", response_model=CustomsDeclarationResponse)
async def update_declaration_endpoint(
    declaration_id: UUID,
    payload: CustomsDeclarationUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_permission("customs_declaration", "edit")
    ),
) -> CustomsDeclarationResponse:
    declaration = await get_declaration(db, declaration_id)
    if declaration is None:
        raise HTTPException(status_code=404, detail="Customs declaration not found")
    updated = await update_declaration(
        db, declaration, payload, UUID(current_user.user_id)
    )
    return _to_response(updated)


@router.get("/declarations/{declaration_id}", response_model=CustomsDeclarationResponse)
async def get_declaration_endpoint(
    declaration_id: UUID,
    db: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(
        require_permission("customs_declaration", "view")
    ),
) -> CustomsDeclarationResponse:
    declaration = await get_declaration(db, declaration_id)
    if declaration is None:
        raise HTTPException(status_code=404, detail="Customs declaration not found")
    return _to_response(declaration)


@container_router.get(
    "/containers/{container_no}/customs", response_model=CustomsDeclarationListResponse
)
async def list_container_customs_endpoint(
    container_no: str,
    db: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(
        require_permission("customs_declaration", "view")
    ),
) -> CustomsDeclarationListResponse:
    container = await get_container_by_no(db, container_no)
    if container is None:
        raise HTTPException(status_code=404, detail="Container not found")
    declarations = await list_declarations_for_container(db, container.id)
    return CustomsDeclarationListResponse(
        items=[_to_response(d) for d in declarations], total=len(declarations)
    )
