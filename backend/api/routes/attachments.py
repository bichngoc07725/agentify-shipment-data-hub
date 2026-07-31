from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps.permissions import CurrentUser, require_permission
from db.database import get_db
from db.models import Attachment

router = APIRouter(prefix="/api/v1/attachments", tags=["attachments"])

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def attachment_file_url(attachment) -> str | None:
    if not getattr(attachment, "storage_path", None):
        return None
    return f"/api/v1/attachments/{attachment.id}/file"


def _resolve_storage_path(storage_path: str) -> Path:
    path = Path(storage_path)
    if not path.is_absolute():
        path = (BACKEND_ROOT / path).resolve()
    else:
        path = path.resolve()

    try:
        path.relative_to(BACKEND_ROOT)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid attachment path") from exc

    return path


@router.get("/{attachment_id}/file")
async def get_attachment_file(
    attachment_id: UUID,
    db: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(
        require_permission("shipping_document", "view")
    ),
) -> FileResponse:
    attachment = await db.get(Attachment, attachment_id)
    if attachment is None:
        raise HTTPException(status_code=404, detail="Attachment not found")
    if not attachment.storage_path:
        raise HTTPException(status_code=404, detail="Attachment file is not available")

    path = _resolve_storage_path(attachment.storage_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Attachment file is missing on disk")

    return FileResponse(
        path,
        media_type=attachment.mime_type or "application/octet-stream",
        headers={"Content-Disposition": f'inline; filename="{attachment.filename}"'},
    )
