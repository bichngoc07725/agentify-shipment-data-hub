from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps.permissions import CurrentUser, require_permission
from api.models import (
    FieldImageConfirmRequest,
    FieldImageConfirmResponse,
    FieldImageListItem,
    FieldImageListResponse,
    FieldImagePreviewResponse,
)
from api.routes.attachments import attachment_file_url
from db.database import get_db
from db.models import Attachment
from services.container_service import get_container_by_no
from services.field_image_service import (
    confirm_field_image,
    list_field_images_for_container,
    preview_field_image,
)

router = APIRouter(prefix="/api/v1/field-images", tags=["field-images"])
# Container-scoped lookup lives at `/api/v1/containers/{no}/images`, matching
# the existing convention for sub-resources (see `.../{no}/facts`,
# `.../{no}/exceptions`, `.../{no}/quotes`), not under `/field-images`.
container_router = APIRouter(prefix="/api/v1", tags=["field-images"])


@router.post("/preview", response_model=FieldImagePreviewResponse)
async def preview_field_image_endpoint(
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_permission("field_image", "create")),
) -> FieldImagePreviewResponse:
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Empty file")

    result = await preview_field_image(
        db, image_bytes, file.filename or "photo.jpg", file.content_type
    )
    attachment: Attachment = result["attachment"]
    vision = result["vision"]

    return FieldImagePreviewResponse(
        image_id=attachment.id,
        filename=attachment.filename,
        mime_type=attachment.mime_type,
        file_url=attachment_file_url(attachment),
        doc_kind=vision.get("doc_kind"),
        container_no=vision.get("container_no"),
        container_no_valid=vision.get("container_no_valid", False),
        matched_container=result["matched_container"],
        seal_no=vision.get("seal_no"),
        license_plate=vision.get("license_plate"),
        depot=vision.get("depot"),
        datetime_text=vision.get("datetime_text"),
        raw_text=vision.get("raw_text"),
        confidence=vision.get("confidence"),
        extraction_status=vision["extraction_status"],
        extraction_error=vision.get("extraction_error"),
    )


@router.post("", response_model=FieldImageConfirmResponse)
async def confirm_field_image_endpoint(
    payload: FieldImageConfirmRequest,
    db: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_permission("field_image", "create")),
) -> FieldImageConfirmResponse:
    try:
        attachment, fact_count = await confirm_field_image(
            db,
            image_id=payload.image_id,
            container_no=payload.container_no,
            seal_no=payload.seal_no,
            doc_kind=payload.doc_kind,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return FieldImageConfirmResponse(
        attachment_id=attachment.id,
        container_no=payload.container_no,
        fact_count=fact_count,
    )


@container_router.get(
    "/containers/{container_no}/images",
    response_model=FieldImageListResponse,
)
async def list_container_field_images_endpoint(
    container_no: str,
    db: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_permission("field_image", "view")),
) -> FieldImageListResponse:
    container = await get_container_by_no(db, container_no)
    if container is None:
        raise HTTPException(status_code=404, detail="Container not found")

    images = await list_field_images_for_container(db, container.id)
    return FieldImageListResponse(
        items=[
            FieldImageListItem(
                id=image.id,
                filename=image.filename,
                mime_type=image.mime_type,
                document_type=image.document_type,
                file_url=attachment_file_url(image),
                extracted_record=image.extracted_record,
                created_at=image.created_at,
            )
            for image in images
        ]
    )
