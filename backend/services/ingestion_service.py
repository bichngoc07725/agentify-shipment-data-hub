from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import ProcessedEmailIngestRequest
from db.models import Attachment, ContainerFact, Email
from services.aggregation_service import (
    get_or_create_container,
    normalize_container_no,
    refresh_container_summary,
)


async def ingest_processed_email(db: AsyncSession, payload: ProcessedEmailIngestRequest):
    result = await db.execute(
        select(Email).where(Email.gmail_message_id == payload.gmail_message_id)
    )
    email = result.scalar_one_or_none()
    created = email is None
    if email is None:
        email = Email(
            gmail_connection_id=payload.gmail_connection_id,
            sync_job_id=payload.sync_job_id,
            channel=payload.channel,
            gmail_message_id=payload.gmail_message_id,
            gmail_thread_id=payload.gmail_thread_id,
            subject=payload.subject,
            from_email=payload.from_email,
            to_emails=payload.to_emails,
            cc_emails=payload.cc_emails,
            sent_at=payload.sent_at,
            snippet=payload.snippet,
            body_text=payload.body_text,
            body_html=payload.body_html,
            raw_labels=payload.raw_labels,
            has_pdf_attachments=payload.has_pdf_attachments,
            processing_status="processed",
        )
        db.add(email)
        await db.flush()
    else:
        email.sync_job_id = payload.sync_job_id
        email.channel = payload.channel
        email.gmail_thread_id = payload.gmail_thread_id
        email.subject = payload.subject
        email.from_email = payload.from_email
        email.to_emails = payload.to_emails
        email.cc_emails = payload.cc_emails
        email.sent_at = payload.sent_at
        email.snippet = payload.snippet
        email.body_text = payload.body_text
        email.body_html = payload.body_html
        email.raw_labels = payload.raw_labels
        email.has_pdf_attachments = payload.has_pdf_attachments
        email.processing_status = "processed"
        await db.flush()

    old_container_ids_result = await db.execute(
        select(ContainerFact.container_id).where(ContainerFact.email_id == email.id)
    )
    old_container_ids = set(old_container_ids_result.scalars().all())
    if old_container_ids:
        await db.execute(delete(ContainerFact).where(ContainerFact.email_id == email.id))

    attachment_by_filename: dict[str, Attachment] = {}
    for attachment_payload in payload.attachments:
        attachment_result = await db.execute(
            select(Attachment).where(
                and_(
                    Attachment.email_id == email.id,
                    Attachment.filename == attachment_payload.filename,
                )
            )
        )
        attachment = attachment_result.scalar_one_or_none()
        if attachment is None:
            attachment = Attachment(
                email_id=email.id,
                gmail_attachment_id=attachment_payload.gmail_attachment_id,
                filename=attachment_payload.filename,
                mime_type=attachment_payload.mime_type,
                size_bytes=attachment_payload.size_bytes,
                storage_path=attachment_payload.storage_path,
                is_text_pdf=attachment_payload.is_text_pdf,
                text_extract_status=attachment_payload.text_extract_status,
                extracted_text=attachment_payload.extracted_text,
                document_type=attachment_payload.document_type,
                extracted_record=attachment_payload.extracted_record,
            )
            db.add(attachment)
            await db.flush()
        else:
            attachment.gmail_attachment_id = attachment_payload.gmail_attachment_id
            attachment.mime_type = attachment_payload.mime_type
            attachment.size_bytes = attachment_payload.size_bytes
            attachment.storage_path = attachment_payload.storage_path
            attachment.is_text_pdf = attachment_payload.is_text_pdf
            attachment.text_extract_status = attachment_payload.text_extract_status
            attachment.extracted_text = attachment_payload.extracted_text
            attachment.document_type = attachment_payload.document_type
            attachment.extracted_record = attachment_payload.extracted_record
            await db.flush()
        attachment_by_filename[attachment.filename] = attachment

    explicit_container_nos = {
        normalize_container_no(fact.container_no)
        for fact in payload.extracted_facts
        if fact.container_no
    }
    inferred_container_nos = {
        normalize_container_no(fact.normalized_value or fact.field_value)
        for fact in payload.extracted_facts
        if fact.field_name == "container_no"
    }
    all_container_nos = explicit_container_nos | inferred_container_nos
    default_container_no = (
        next(iter(all_container_nos)) if len(all_container_nos) == 1 else None
    )

    container_ids = {}
    linked_containers: set[str] = set()
    fact_count = 0

    for fact_payload in payload.extracted_facts:
        container_no = fact_payload.container_no or default_container_no
        if fact_payload.field_name == "container_no" and container_no is None:
            container_no = fact_payload.normalized_value or fact_payload.field_value
        if not container_no:
            continue

        normalized_container_no = normalize_container_no(container_no)
        container = await get_or_create_container(
            db, normalized_container_no, payload.sent_at
        )
        attachment = (
            attachment_by_filename.get(fact_payload.attachment_filename)
            if fact_payload.attachment_filename
            else None
        )

        container_fact = ContainerFact(
            container_id=container.id,
            email_id=email.id,
            attachment_id=attachment.id if attachment else None,
            field_name=fact_payload.field_name,
            field_value=fact_payload.field_value,
            normalized_value=fact_payload.normalized_value,
            source_type=fact_payload.source_type,
            source_label=fact_payload.source_label,
            document_type=fact_payload.document_type,
            confidence=fact_payload.confidence,
            source_sent_at=fact_payload.source_sent_at or payload.sent_at,
        )
        db.add(container_fact)
        fact_count += 1
        linked_containers.add(normalized_container_no)
        container_ids[normalized_container_no] = container.id

    await db.flush()

    affected_container_ids = set(container_ids.values()) | old_container_ids
    for container_no in linked_containers:
        await refresh_container_summary(db, container_ids[container_no])
    for container_id in affected_container_ids - set(container_ids.values()):
        await refresh_container_summary(db, container_id)

    return {
        "email_id": email.id,
        "created": created,
        "attachment_count": len(payload.attachments),
        "fact_count": fact_count,
        "linked_containers": sorted(linked_containers),
    }
