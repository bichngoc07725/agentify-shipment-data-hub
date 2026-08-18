from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps.permissions import require_permission
from api.models import (
    ManualIngestPreviewResponse,
    ManualIngestRequest,
    ManualIngestResponse,
)
from db.database import get_db
from gmail_service.field_extract import run_extraction_in_thread
from services.manual_ingest_service import (
    container_numbers_in,
    extract_from_content,
    ingest_manual_content,
    split_known_containers,
)

router = APIRouter(prefix="/api/v1/manual-ingest", tags=["manual-ingest"])


@router.post("/preview", response_model=ManualIngestPreviewResponse)
async def preview_manual_ingest(
    payload: ManualIngestRequest,
    db: AsyncSession = Depends(get_db),
    # Cùng quyền với thao tác ghi ngay bên dưới. Preview không ghi gì, nhưng
    # nó chạy trích xuất (tốn tiền LLM) và trả lời được câu hỏi "số container
    # này đã có trong hệ thống chưa" — hai thứ không nên mở cho người lạ.
    _current_user=Depends(require_permission("manual_ingest", "create")),
) -> ManualIngestPreviewResponse:
    """Show what extraction read, without writing anything.

    Keeps a human in the loop: pasted chat is noisier than a carrier PDF, so the
    user confirms the reading before it becomes part of the shipment record.
    """
    fields = await run_extraction_in_thread(extract_from_content, payload)
    container_nos = container_numbers_in(fields)
    matched, new = await split_known_containers(db, container_nos)

    return ManualIngestPreviewResponse(
        channel=payload.channel,
        container_nos=container_nos,
        document_type=fields.get("doc_type"),
        extraction_method=fields.get("extraction_method", "deterministic"),
        extraction_status=fields.get("extraction_status", "ok"),
        extraction_error=fields.get("extraction_error"),
        fields={
            "identifiers": fields.get("identifiers") or {},
            "route": fields.get("route") or {},
            "free_time_days": fields.get("free_time_days"),
        },
        matched_containers=matched,
        new_containers=new,
    )


@router.post("", response_model=ManualIngestResponse)
async def create_manual_ingest(
    payload: ManualIngestRequest,
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(require_permission("manual_ingest", "create")),
) -> ManualIngestResponse:
    result = await ingest_manual_content(db, payload)
    return ManualIngestResponse(**result)
