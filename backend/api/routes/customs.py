from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps.permissions import CurrentUser, require_permission
from api.models import (
    CustomsWorksheetResponse,
    WorksheetFieldResponse,
    WorksheetSectionResponse,
    CustomsChannelHistoryResponse,
    CustomsDeclarationCreateRequest,
    CustomsDeclarationListResponse,
    CustomsDeclarationResponse,
    CustomsDeclarationUpdateRequest,
)
from db.database import get_db
from db.models import CustomsDeclaration
from services.container_service import get_container_by_no
from services.customs_worksheet_service import collect_worksheet, render_docx
from services.customs_service import (
    get_declaration_prefill,
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


@container_router.get("/containers/{container_no}/customs-worksheet/docx")
async def download_customs_worksheet_endpoint(
    container_no: str,
    db: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(
        require_permission("customs_declaration", "view")
    ),
) -> Response:
    """Phiếu nhập liệu tờ khai (.docx) để gõ sang ECUS/VNACCS.

    Trả file thay vì JSON vì đây là thứ nhân viên in ra hoặc mở cạnh màn hình
    ECUS mà gõ — dạng dùng được ngay, không phải dữ liệu để máy khác đọc.
    """
    container = await get_container_by_no(db, container_no)
    if container is None:
        raise HTTPException(status_code=404, detail="Container not found")

    sections = await collect_worksheet(db, container)
    content = render_docx(container.container_no, sections)
    filename = f"to-khai-{container.container_no}.docx"
    return Response(
        content=content,
        media_type=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@container_router.get(
    "/containers/{container_no}/customs-worksheet",
    response_model=CustomsWorksheetResponse,
)
async def get_customs_worksheet_endpoint(
    container_no: str,
    db: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(
        require_permission("customs_declaration", "view")
    ),
) -> CustomsWorksheetResponse:
    """Phiếu nhập liệu tờ khai dưới dạng dữ liệu, để hiển thị trên web.

    Cùng nguồn với bản .docx nên hai bên không thể lệch nhau — xem trên màn
    hình rồi tải file về mà thấy khác nhau là kiểu lỗi phá hết lòng tin.
    """
    container = await get_container_by_no(db, container_no)
    if container is None:
        raise HTTPException(status_code=404, detail="Container not found")

    sections = await collect_worksheet(db, container)
    fields = [field for section in sections for field in section.fields]
    return CustomsWorksheetResponse(
        container_no=container.container_no,
        sections=[
            WorksheetSectionResponse(
                title=section.title,
                fields=[
                    WorksheetFieldResponse(
                        label=f.label,
                        value=f.value,
                        source_hint=f.source_hint,
                        is_missing=f.is_missing,
                        display=f.display,
                    )
                    for f in section.fields
                ],
            )
            for section in sections
        ],
        field_count=len(fields),
        missing_count=sum(1 for f in fields if f.is_missing),
    )


@container_router.get("/containers/{container_no}/customs-prefill")
async def customs_prefill_endpoint(
    container_no: str,
    db: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(
        require_permission("customs_declaration", "create")
    ),
) -> dict[str, str]:
    """Giá trị đã đọc từ thông báo hải quan, để điền sẵn form tờ khai.

    Trả dict rỗng khi chưa đọc được gì — "không tìm thấy trong Agentify" thay
    vì đoán một luồng, vì luồng sai làm cả nhóm chạy nhầm việc.
    """
    prefill = await get_declaration_prefill(db, container_no)
    if prefill is None:
        raise HTTPException(status_code=404, detail="Container not found")
    return prefill
