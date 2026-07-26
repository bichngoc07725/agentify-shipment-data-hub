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

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import (
    IngestFactRequest,
    ManualIngestRequest,
    ProcessedEmailIngestRequest,
)
from db.models import Container
from gmail_service.adapter import SUMMARY_FIELDS
from gmail_service.field_extract import extract_fields
from services.aggregation_service import normalize_container_no
from services.ingestion_service import ingest_processed_email

CHANNEL_LABELS = {
    "zalo": "Zalo",
    "note": "Ghi chú nội bộ",
    "other": "Nguồn khác",
}

# How many characters of the pasted text to use as the message subject.
SUBJECT_MAX_CHARS = 160


def _subject_from(content: str, source_label: str | None, channel: str) -> str:
    first_line = next(
        (line.strip() for line in content.splitlines() if line.strip()), ""
    )
    prefix = source_label or CHANNEL_LABELS.get(channel, channel)
    subject = f"{prefix}: {first_line}" if first_line else prefix
    return subject[:SUBJECT_MAX_CHARS]


def extract_from_content(payload: ManualIngestRequest) -> dict:
    """Run the normal extraction pipeline over pasted text."""
    subject = _subject_from(payload.content, payload.source_label, payload.channel)
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
                source_type=f"{payload.channel}_message",
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
    return first_line[:255]


async def ingest_manual_content(db: AsyncSession, payload: ManualIngestRequest) -> dict:
    fields = extract_from_content(payload)
    facts = build_facts(payload, fields)
    occurred_at = payload.occurred_at or datetime.now(UTC)

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
        has_pdf_attachments=False,
        attachments=[],
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
