from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import ProcessedEmailIngestRequest, UpdateSyncJobRequest
from db.models import Attachment, Email, GmailConnection, SyncJob
from gmail_service.adapter import (
    AttachmentExtractionResult,
    EmailTextExtractionResult,
    build_processed_email_request,
)
from gmail_service.auth import get_gmail_profile, get_gmail_service
from gmail_service.fetcher import get_email, resolve_sync_message_ids
from gmail_service.models import ExtractedRecord, GmailEmailPayload
from gmail_service.pdf_reader import read_pdf_text
from gmail_service.pipeline import process_pdf_attachment, process_pdf_text, process_text_content
from services.ingestion_service import ingest_processed_email
from services.sync_job_service import update_sync_job


def build_gmail_oauth_payload(
    refresh_token: str, scopes: list[str] | None = None
) -> dict[str, str]:
    profile = get_gmail_profile(refresh_token)
    return {
        "account_email": profile["emailAddress"],
        "google_account_id": profile["emailAddress"],
        "access_scope": " ".join(scopes or ["gmail.readonly"]),
        "encrypted_refresh_token": refresh_token,
        "status": "connected",
    }


def process_gmail_pdf_attachment(
    email: dict[str, str], filename: str, pdf_bytes: bytes
) -> ExtractedRecord:
    return process_pdf_attachment(email, filename, pdf_bytes)


def build_processed_email_from_gmail_payload(
    gmail_connection_id,
    sync_job_id,
    email: GmailEmailPayload,
) -> ProcessedEmailIngestRequest:
    results: list[AttachmentExtractionResult] = []
    for attachment in email.attachments:
        extracted_text = read_pdf_text(attachment.attachment_bytes)
        text_extract_status = "extracted" if extracted_text.strip() else "empty"
        record = process_pdf_text(
            {
                "message_id": email.gmail_message_id,
                "sender": email.from_email,
                "subject": email.subject,
                "received_at": email.sent_at,
            },
            attachment.filename,
            extracted_text,
        )
        results.append(
            AttachmentExtractionResult(
                attachment=attachment,
                extracted_text=extracted_text,
                text_extract_status=text_extract_status,
                record=record,
            )
        )

    email_text_result = None
    email_text = _collect_email_text(email)
    if email_text:
        record = process_text_content(
            {
                "message_id": email.gmail_message_id,
                "sender": email.from_email,
                "subject": email.subject,
                "received_at": email.sent_at,
            },
            "email_body",
            email_text,
        )
        email_text_result = EmailTextExtractionResult(
            extracted_text=email_text,
            record=record,
        )

    return build_processed_email_request(
        gmail_connection_id=gmail_connection_id,
        sync_job_id=sync_job_id,
        email=email,
        attachment_results=results,
        email_text_result=email_text_result,
    )


def _collect_email_text(email: GmailEmailPayload) -> str:
    parts = [email.body_text, email.snippet, email.subject]
    return "\n".join(part.strip() for part in parts if part and part.strip())


async def execute_sync_job(
    db: AsyncSession,
    connection: GmailConnection,
    job: SyncJob,
    create_service=get_gmail_service,
    resolve_message_ids=resolve_sync_message_ids,
    filter_message_ids=None,
    fetch_email=get_email,
    process_email=build_processed_email_from_gmail_payload,
    ingest_email=ingest_processed_email,
) -> SyncJob:
    if not connection.encrypted_refresh_token:
        job.status = "failed"
        job.error_message = "Gmail connection is missing a refresh token"
        job.completed_at = datetime.now(UTC)
        await db.flush()
        await db.refresh(job)
        return job

    started_at = datetime.now(UTC)
    previous_started_at = job.started_at
    await update_sync_job(
        db,
        job.id,
        UpdateSyncJobRequest(
            status="running",
            started_at=started_at,
            error_message=None,
        ),
    )

    try:
        gmail_api = create_service(connection.encrypted_refresh_token)
        message_ids, next_sync_cursor = resolve_message_ids(
            gmail_api,
            query=job.query,
            max_results=job.max_results,
            sync_cursor=connection.sync_cursor,
        )
        filter_message_ids = filter_message_ids or select_syncable_message_ids
        message_ids = await filter_message_ids(db, connection.id, message_ids)
        linked_containers: set[str] = set()
        attachments_found = 0
        pdf_text_extracted = 0
        skipped_message_ids: list[str] = []

        for message_id in message_ids:
            try:
                email = fetch_email(gmail_api, message_id)
            except Exception as exc:
                skipped_message_ids.append(message_id)
                print(f"gmail sync: skipping unreachable message {message_id}: {exc}")
                continue
            processed_email = process_email(connection.id, job.id, email)
            ingest_result = await ingest_email(db, processed_email)
            attachments_found += ingest_result["attachment_count"]
            pdf_text_extracted += (
                sum(
                    1
                    for attachment in processed_email.attachments
                    if attachment.text_extract_status == "extracted"
                )
                or ingest_result["attachment_count"]
            )
            linked_containers.update(ingest_result["linked_containers"])

        completed_at = datetime.now(UTC)
        job.status = "completed"
        job.emails_fetched = len(message_ids) - len(skipped_message_ids)
        job.attachments_found = attachments_found
        job.pdf_text_extracted = pdf_text_extracted
        job.containers_upserted = len(linked_containers)
        job.error_message = (
            f"Skipped {len(skipped_message_ids)} unreachable message(s)"
            if skipped_message_ids
            else None
        )
        job.started_at = job.started_at or started_at
        job.completed_at = completed_at
        connection.sync_cursor = next_sync_cursor or connection.sync_cursor
        connection.last_synced_at = completed_at
        await db.flush()
        await db.refresh(job)
        return job
    except Exception as exc:
        await db.rollback()
        job.status = "failed"
        job.error_message = str(exc)
        job.started_at = previous_started_at or started_at
        job.completed_at = datetime.now(UTC)
        await db.flush()
        await db.refresh(job)
        return job


async def select_syncable_message_ids(
    db: AsyncSession,
    gmail_connection_id,
    message_ids: list[str],
) -> list[str]:
    if not message_ids:
        return []

    existing_result = await db.execute(
        select(Email.id, Email.gmail_message_id, Email.has_pdf_attachments).where(
            Email.gmail_connection_id == gmail_connection_id,
            Email.gmail_message_id.in_(message_ids),
        )
    )
    existing_rows = existing_result.all()
    existing_by_message_id = {
        row.gmail_message_id: {
            "email_id": row.id,
            "has_pdf_attachments": row.has_pdf_attachments,
        }
        for row in existing_rows
    }

    if not existing_by_message_id:
        return message_ids

    attachment_rows = []
    existing_email_ids = [row["email_id"] for row in existing_by_message_id.values()]
    if existing_email_ids:
        attachment_result = await db.execute(
            select(Attachment.email_id, Attachment.storage_path).where(
                Attachment.email_id.in_(existing_email_ids)
            )
        )
        attachment_rows = attachment_result.all()

    attachments_by_email_id: dict = {}
    for row in attachment_rows:
        attachments_by_email_id.setdefault(row.email_id, []).append(row.storage_path)

    syncable_message_ids: list[str] = []
    for message_id in message_ids:
        existing = existing_by_message_id.get(message_id)
        if existing is None:
            syncable_message_ids.append(message_id)
            continue

        if not existing["has_pdf_attachments"]:
            continue

        attachment_paths = attachments_by_email_id.get(existing["email_id"], [])
        if not attachment_paths or any(not path for path in attachment_paths):
            syncable_message_ids.append(message_id)

    return syncable_message_ids
