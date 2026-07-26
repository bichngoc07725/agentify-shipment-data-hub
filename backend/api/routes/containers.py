from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.routes.attachments import attachment_file_url
from api.models import (
    ContainerDetailResponse,
    ContainerFactsListResponse,
    ContainerFactResponse,
    ContainerListItem,
    ContainerListResponse,
    RelatedAttachmentSummary,
    RelatedEmailSummary,
)
from db.database import get_db
from services.container_service import (
    get_container_by_no,
    get_container_facts,
    get_container_related_attachments,
    get_container_related_emails,
    list_containers,
)

router = APIRouter(prefix="/api/v1/containers", tags=["containers"])


def _to_container_item(container) -> ContainerListItem:
    return ContainerListItem(
        id=container.id,
        container_no=container.container_no,
        booking_no=container.booking_no,
        bl_no=container.bl_no,
        po_no=container.po_no,
        do_no=container.do_no,
        vessel=container.vessel,
        voyage=container.voyage,
        pol=container.pol,
        pod=container.pod,
        etd=container.etd,
        eta=container.eta,
        ata=container.ata,
        free_time_days=container.free_time_days,
        status_text=container.status_text,
        source_count=container.source_count,
        attachment_count=container.attachment_count,
        updated_at=container.updated_at,
    )


@router.get("", response_model=ContainerListResponse)
async def list_containers_endpoint(
    q: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> ContainerListResponse:
    items, total = await list_containers(db, q=q, page=page, page_size=page_size)
    return ContainerListResponse(
        items=[_to_container_item(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{container_no}", response_model=ContainerDetailResponse)
async def get_container_detail_endpoint(
    container_no: str,
    db: AsyncSession = Depends(get_db),
) -> ContainerDetailResponse:
    container = await get_container_by_no(db, container_no)
    if container is None:
        raise HTTPException(status_code=404, detail="Container not found")

    emails = await get_container_related_emails(db, container.id)
    attachments = await get_container_related_attachments(db, container.id)
    return ContainerDetailResponse(
        container=_to_container_item(container),
        related_emails=[
            RelatedEmailSummary(
                id=email.id,
                subject=email.subject,
                from_email=email.from_email,
                sent_at=email.sent_at,
                channel=email.channel,
            )
            for email in emails
        ],
        related_attachments=[
            RelatedAttachmentSummary(
                id=attachment.id,
                filename=attachment.filename,
                email_id=attachment.email_id,
                document_type=attachment.document_type,
                file_url=attachment_file_url(attachment),
            )
            for attachment in attachments
        ],
    )


@router.get("/{container_no}/facts", response_model=ContainerFactsListResponse)
async def get_container_facts_endpoint(
    container_no: str,
    db: AsyncSession = Depends(get_db),
) -> ContainerFactsListResponse:
    container = await get_container_by_no(db, container_no)
    if container is None:
        raise HTTPException(status_code=404, detail="Container not found")

    facts = await get_container_facts(db, container.id)
    return ContainerFactsListResponse(
        items=[
            ContainerFactResponse(
                id=fact.id,
                field_name=fact.field_name,
                field_value=fact.field_value,
                normalized_value=fact.normalized_value,
                source_type=fact.source_type,
                source_label=fact.source_label,
                document_type=fact.document_type,
                confidence=fact.confidence,
                source_sent_at=fact.source_sent_at,
                email_id=fact.email_id,
                attachment_id=fact.attachment_id,
            )
            for fact in facts
        ]
    )
