"""Field photos: container/seal/EIR/POD, read with vision.

The photo is saved permanently as soon as it's uploaded (Zalo auto-deletes
originals, so Agentify's copy is the durable one) — regardless of whether
vision reads it, or reads it wrong. Assigning it to a container is a second,
separate step (`confirm_field_image`) so an unclear photo never gets attached
to the wrong shipment automatically.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Attachment, ContainerFact
from gmail_service.image_extract import extract_from_image
from services.aggregation_service import (
    get_or_create_container,
    normalize_container_no,
    refresh_container_summary,
)
from services.container_service import get_container_by_no

BACKEND_ROOT = Path(__file__).resolve().parents[1]
FIELD_IMAGE_STORAGE_DIR = BACKEND_ROOT / "storage" / "field_images"


def _sanitize_filename(filename: str) -> str:
    basename = Path(filename).name or "photo.jpg"
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", basename)
    return sanitized[:240] or "photo.jpg"


def _save_image_bytes(image_bytes: bytes, filename: str) -> str:
    safe_filename = _sanitize_filename(filename)
    folder = FIELD_IMAGE_STORAGE_DIR / uuid.uuid4().hex
    folder.mkdir(parents=True, exist_ok=True)
    absolute_path = folder / safe_filename
    absolute_path.write_bytes(image_bytes)
    return absolute_path.relative_to(BACKEND_ROOT).as_posix()


async def preview_field_image(
    db: AsyncSession, image_bytes: bytes, filename: str, mime_type: str
) -> dict:
    """Persist the photo and run vision on it.

    Does not create a `ContainerFact` yet — that happens at confirm, once the
    user has accepted or corrected which container it belongs to.
    """

    storage_path = _save_image_bytes(image_bytes, filename)
    vision = extract_from_image(image_bytes, mime_type)

    attachment = Attachment(
        email_id=None,
        filename=Path(storage_path).name,
        mime_type=mime_type,
        size_bytes=len(image_bytes),
        storage_path=storage_path,
        is_text_pdf=False,
        text_extract_status=vision["extraction_status"],
        document_type=vision.get("doc_kind"),
        extracted_record=vision,
        source_channel="field_upload",
    )
    db.add(attachment)
    await db.flush()
    await db.refresh(attachment)

    matched_container = None
    container_no = vision.get("container_no")
    if container_no and vision.get("container_no_valid"):
        existing = await get_container_by_no(db, container_no)
        if existing is not None:
            matched_container = existing.container_no

    return {"attachment": attachment, "vision": vision, "matched_container": matched_container}


async def confirm_field_image(
    db: AsyncSession,
    image_id: UUID,
    container_no: str,
    seal_no: str | None,
    doc_kind: str | None,
) -> tuple[Attachment, int]:
    attachment = await db.get(Attachment, image_id)
    if attachment is None:
        raise ValueError(f"Image '{image_id}' not found")
    if attachment.source_channel != "field_upload":
        raise ValueError(f"Attachment '{image_id}' is not a field image")

    normalized_no = normalize_container_no(container_no)
    now = datetime.now(UTC)
    container = await get_or_create_container(db, normalized_no, now)

    if doc_kind:
        attachment.document_type = doc_kind

    fact_count = 0

    def add_fact(field_name: str, value: str | None) -> None:
        nonlocal fact_count
        if not value:
            return
        db.add(
            ContainerFact(
                container_id=container.id,
                email_id=None,
                attachment_id=attachment.id,
                field_name=field_name,
                field_value=str(value),
                normalized_value=str(value),
                source_type="image",
                source_label=attachment.filename,
                document_type=attachment.document_type,
                confidence=None,
                source_sent_at=now,
            )
        )
        fact_count += 1

    add_fact("container_no", normalized_no)
    add_fact("seal_no", seal_no)

    await db.flush()
    await refresh_container_summary(db, container.id)
    return attachment, fact_count


async def list_field_images_for_container(
    db: AsyncSession, container_id: UUID
) -> list[Attachment]:
    result = await db.execute(
        select(Attachment)
        .join(ContainerFact, ContainerFact.attachment_id == Attachment.id)
        .where(
            and_(
                ContainerFact.container_id == container_id,
                Attachment.source_channel == "field_upload",
            )
        )
        .group_by(Attachment.id)
        .order_by(Attachment.created_at.desc())
    )
    return list(result.scalars().all())
