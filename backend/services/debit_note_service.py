"""Debit notes — real costs invoiced for a shipment (carrier debit note /
invoice), entered by hand by `accountant`. This is the "actual" side that
`reconciliation_service.py` compares against a `Quote`'s charges.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.models import DebitNoteChargeRequest, DebitNoteCreateRequest
from db.models import DebitNote, DebitNoteCharge
from services.container_service import get_container_by_no

_LOAD_OPTIONS = (selectinload(DebitNote.charges), selectinload(DebitNote.container))


def total_amount(debit_note: DebitNote) -> Decimal:
    return sum((charge.amount for charge in debit_note.charges), Decimal("0"))


def _build_charge(payload: DebitNoteChargeRequest) -> DebitNoteCharge:
    return DebitNoteCharge(
        charge_code=payload.charge_code,
        description=payload.description,
        amount=payload.amount,
        currency=payload.currency,
        quantity=payload.quantity,
    )


async def create_debit_note(
    db: AsyncSession, payload: DebitNoteCreateRequest, created_by: UUID
) -> DebitNote:
    container = await get_container_by_no(db, payload.container_no)
    if container is None:
        raise ValueError(f"Container '{payload.container_no}' not found")

    debit_note = DebitNote(
        container_id=container.id,
        source_attachment_id=payload.source_attachment_id,
        partner_name=payload.partner_name,
        doc_no=payload.doc_no,
        currency=payload.currency,
        issued_date=payload.issued_date,
        created_by=created_by,
        charges=[_build_charge(charge) for charge in payload.charges],
    )
    db.add(debit_note)
    await db.flush()
    return await get_debit_note(db, debit_note.id)  # type: ignore[return-value]


async def get_debit_note(db: AsyncSession, debit_note_id: UUID) -> DebitNote | None:
    result = await db.execute(
        select(DebitNote).where(DebitNote.id == debit_note_id).options(*_LOAD_OPTIONS)
    )
    return result.scalar_one_or_none()


async def list_debit_notes_for_container(
    db: AsyncSession, container_id: UUID
) -> list[DebitNote]:
    result = await db.execute(
        select(DebitNote)
        .where(DebitNote.container_id == container_id)
        .options(*_LOAD_OPTIONS)
        .order_by(DebitNote.created_at.desc())
    )
    return list(result.scalars().all())
