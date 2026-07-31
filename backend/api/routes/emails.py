from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps.permissions import CurrentUser, require_permission
from api.models import EmailDetailResponse, EmailListItem, EmailListResponse
from api.routes.attachments import attachment_file_url
from db.database import get_db
from services.container_service import get_email_detail, list_emails

router = APIRouter(prefix="/api/v1/emails", tags=["emails"])


@router.get("", response_model=EmailListResponse)
async def list_emails_endpoint(
    gmail_connection_id: UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(
        require_permission("shipping_document", "view")
    ),
) -> EmailListResponse:
    items, total = await list_emails(
        db,
        gmail_connection_id=gmail_connection_id,
        page=page,
        page_size=page_size,
    )
    return EmailListResponse(
        items=[
            EmailListItem(
                id=item["email"].id,
                gmail_connection_id=item["email"].gmail_connection_id,
                sync_job_id=item["email"].sync_job_id,
                channel=item["email"].channel,
                gmail_message_id=item["email"].gmail_message_id,
                subject=item["email"].subject,
                from_email=item["email"].from_email,
                sent_at=item["email"].sent_at,
                snippet=item["email"].snippet,
                has_pdf_attachments=item["email"].has_pdf_attachments,
                processing_status=item["email"].processing_status,
                linked_containers=item["linked_containers"],
                attachment_count=item["attachment_count"],
                fact_count=item["fact_count"],
            )
            for item in items
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{email_id}", response_model=EmailDetailResponse)
async def get_email_detail_endpoint(
    email_id: UUID,
    db: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(
        require_permission("shipping_document", "view")
    ),
) -> EmailDetailResponse:
    detail = await get_email_detail(db, email_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Email not found")

    return EmailDetailResponse(
        email={
            "id": detail["email"].id,
            "channel": detail["email"].channel,
            "gmail_message_id": detail["email"].gmail_message_id,
            "gmail_thread_id": detail["email"].gmail_thread_id,
            "subject": detail["email"].subject,
            "from_email": detail["email"].from_email,
            "to_emails": detail["email"].to_emails,
            "cc_emails": detail["email"].cc_emails,
            "sent_at": detail["email"].sent_at,
            "snippet": detail["email"].snippet,
            "body_text": detail["email"].body_text,
            "body_html": detail["email"].body_html,
            "has_pdf_attachments": detail["email"].has_pdf_attachments,
            "processing_status": detail["email"].processing_status,
        },
        attachments=[
            {
                "id": attachment.id,
                "filename": attachment.filename,
                "mime_type": attachment.mime_type,
                "size_bytes": attachment.size_bytes,
                "text_extract_status": attachment.text_extract_status,
                "document_type": attachment.document_type,
                "extracted_record": attachment.extracted_record,
                "file_url": attachment_file_url(attachment),
            }
            for attachment in detail["attachments"]
        ],
        extracted_facts=[
            {
                "id": fact.id,
                "container_id": fact.container_id,
                "attachment_id": fact.attachment_id,
                "field_name": fact.field_name,
                "field_value": fact.field_value,
                "normalized_value": fact.normalized_value,
                "source_type": fact.source_type,
                "source_label": fact.source_label,
                "document_type": fact.document_type,
                "confidence": fact.confidence,
                "source_sent_at": fact.source_sent_at,
            }
            for fact in detail["facts"]
        ],
        linked_containers=detail["linked_containers"],
    )
