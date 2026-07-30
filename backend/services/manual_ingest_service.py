"""Ingest content the user pastes or forwards in by hand.

This is the safe path for Zalo. Agentify does not read Zalo automatically —
that would require consent and access the product should not ask for, and the
market research is explicit that promising it is a mistake. Instead the user
pastes the message that matters, reviews what Agentify read from it, and only
then commits it to the shipment record.

Pasted messages are stored alongside email in the same table so that container
profiles, provenance and the exception engine treat them identically. The
`channel` column is what tells them apart.
"""

from __future__ import annotations

import base64
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import (
    IngestAttachmentRequest,
    IngestFactRequest,
    ManualIngestRequest,
    ProcessedEmailIngestRequest,
)
from db.models import Container
from gmail_service.adapter import SUMMARY_FIELDS
from gmail_service.field_extract import extract_fields
from gmail_service.pipeline import process_image_attachment
from services.aggregation_service import normalize_container_no
from services.ingestion_service import ingest_processed_email

CHANNEL_LABELS = {
    "zalo": "Zalo",
    "note": "Ghi chú nội bộ",
    "other": "Nguồn khác",
}

# How many characters of the pasted text to use as the message subject.
SUBJECT_MAX_CHARS = 160

BACKEND_ROOT = Path(__file__).resolve().parents[1]
MANUAL_ATTACHMENT_STORAGE_DIR = BACKEND_ROOT / "storage" / "manual_attachments"


def _subject_from(content: str, source_label: str | None, channel: str) -> str:
    first_line = next(
        (line.strip() for line in content.splitlines() if line.strip()), ""
    )
    prefix = source_label or CHANNEL_LABELS.get(channel, channel)
    subject = f"{prefix}: {first_line}" if first_line else prefix
    return subject[:SUBJECT_MAX_CHARS]


def _persist_manual_image(image_bytes: bytes, filename: str) -> str:
    MANUAL_ATTACHMENT_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = "".join(c for c in filename if c.isalnum() or c in "._-") or "pasted.jpg"
    unique_name = f"{uuid.uuid4()}_{safe_name}"
    absolute_path = MANUAL_ATTACHMENT_STORAGE_DIR / unique_name
    absolute_path.write_bytes(image_bytes)
    return absolute_path.relative_to(BACKEND_ROOT).as_posix()


def extract_from_content(payload: ManualIngestRequest) -> dict:
    """Run the normal extraction pipeline over the pasted text and/or image."""
    subject = _subject_from(payload.content, payload.source_label, payload.channel)
    if payload.image_base64:
        image_bytes = base64.b64decode(payload.image_base64)
        record = process_image_attachment(
            {
                "message_id": f"{payload.channel}-preview",
                "sender": payload.sender or "",
                "subject": subject,
                "received_at": payload.occurred_at or datetime.now(UTC),
            },
            payload.image_filename or "pasted-image.jpg",
            image_bytes,
            payload.image_mime_type or "image/jpeg",
        )
        return record.model_dump(mode="json")
    return extract_fields(subject, payload.sender or "", payload.content)


def container_numbers_in(fields: dict) -> list[str]:
    identifiers = fields.get("identifiers") or {}
    return [
        normalize_container_no(container_no)
        for container_no in identifiers.get("container_no") or []
        if container_no
    ]


async def split_known_containers(
    db: AsyncSession, container_nos: list[str]
) -> tuple[list[str], list[str]]:
    """Return `(already in Agentify, would be created)`.

    Shown in the preview so the user can tell a genuine new shipment from a typo
    before it becomes a container record.
    """
    if not container_nos:
        return [], []

    result = await db.execute(
        select(Container.container_no).where(Container.container_no.in_(container_nos))
    )
    known = set(result.scalars().all())
    return (
        [no for no in container_nos if no in known],
        [no for no in container_nos if no not in known],
    )


def build_facts(payload: ManualIngestRequest, fields: dict) -> list[IngestFactRequest]:
    """Turn extracted fields into facts, one per container mentioned."""
    container_nos = container_numbers_in(fields)
    identifiers = fields.get("identifiers") or {}
    route = fields.get("route") or {}
    document_type = fields.get("doc_type")
    source_label = payload.source_label or CHANNEL_LABELS.get(
        payload.channel, payload.channel
    )
    source_type = "image_vision" if payload.image_base64 else f"{payload.channel}_message"

    facts: list[IngestFactRequest] = []

    def add(field_name: str, value, container_no: str | None) -> None:
        if value in (None, "", []):
            return
        facts.append(
            IngestFactRequest(
                field_name=field_name,
                field_value=str(value),
                normalized_value=str(value),
                container_no=container_no,
                source_type=source_type,
                source_label=source_label,
                document_type=document_type,
                source_sent_at=payload.occurred_at,
            )
        )

    for container_no in container_nos:
        add("container_no", container_no, container_no)

    # Without a container the fact has nothing to hang off, so only the
    # container-scoped fields are recorded.
    for container_no in container_nos:
        for field_name in SUMMARY_FIELDS:
            add(field_name, identifiers.get(field_name) or route.get(field_name), container_no)

        for seal_no in identifiers.get("seal_no") or []:
            add("seal_no", seal_no, container_no)

        free_time_days = fields.get("free_time_days")
        if free_time_days is not None:
            add("free_time_days", free_time_days, container_no)

        add("status_text", _status_text(payload), container_no)

    return facts


def _status_text(payload: ManualIngestRequest) -> str:
    first_line = next(
        (line.strip() for line in payload.content.splitlines() if line.strip()), ""
    )
    if not first_line and payload.image_base64:
        return "Ảnh đính kèm"
    return first_line[:255]


async def ingest_manual_content(db: AsyncSession, payload: ManualIngestRequest) -> dict:
    fields = extract_from_content(payload)
    facts = build_facts(payload, fields)
    occurred_at = payload.occurred_at or datetime.now(UTC)

    attachments: list[IngestAttachmentRequest] = []
    if payload.image_base64:
        image_bytes = base64.b64decode(payload.image_base64)
        filename = payload.image_filename or "pasted-image.jpg"
        attachments.append(
            IngestAttachmentRequest(
                filename=filename,
                mime_type=payload.image_mime_type or "image/jpeg",
                size_bytes=len(image_bytes),
                storage_path=_persist_manual_image(image_bytes, filename),
                is_text_pdf=False,
                text_extract_status=(
                    "extracted" if fields.get("extraction_status") == "ok" else "failed"
                ),
                document_type=fields.get("doc_type"),
                extracted_record=fields,
            )
        )

    request = ProcessedEmailIngestRequest(
        gmail_connection_id=None,
        sync_job_id=None,
        channel=payload.channel,
        gmail_message_id=f"{payload.channel}:{uuid.uuid4()}",
        subject=_subject_from(payload.content, payload.source_label, payload.channel),
        from_email=(payload.sender or CHANNEL_LABELS.get(payload.channel, payload.channel))[:255],
        to_emails=[],
        cc_emails=[],
        sent_at=occurred_at,
        snippet=payload.content[:500],
        body_text=payload.content,
        raw_labels=[payload.channel],
        has_pdf_attachments=bool(attachments),
        attachments=attachments,
        extracted_facts=facts,
    )

    result = await ingest_processed_email(db, request)
    return {
        "message_id": result["email_id"],
        "channel": payload.channel,
        "linked_containers": result["linked_containers"],
        "fact_count": result["fact_count"],
        "extraction_method": fields.get("extraction_method", "deterministic"),
        "extraction_status": fields.get("extraction_status", "ok"),
    }
