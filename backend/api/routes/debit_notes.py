from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps.permissions import CurrentUser, require_permission
from api.models import (
    DebitNoteChargeResponse,
    DebitNoteCreateRequest,
    DebitNoteListResponse,
    DebitNoteResponse,
)
from db.database import get_db
from db.models import DebitNote
from services.container_service import get_container_by_no
from services.debit_note_service import (
    create_debit_note,
    get_debit_note,
    list_debit_notes_for_container,
    total_amount,
)

router = APIRouter(prefix="/api/v1/debit-notes", tags=["debit-notes"])
container_router = APIRouter(prefix="/api/v1", tags=["debit-notes"])


def _to_response(note: DebitNote) -> DebitNoteResponse:
    return DebitNoteResponse(
        id=note.id,
        container_id=note.container_id,
        container_no=note.container.container_no if note.container else None,
        source_attachment_id=note.source_attachment_id,
        partner_name=note.partner_name,
        doc_no=note.doc_no,
        currency=note.currency,
        issued_date=note.issued_date,
        created_by=note.created_by,
        charges=[
            DebitNoteChargeResponse(
                id=charge.id,
                charge_code=charge.charge_code,
                description=charge.description,
                amount=charge.amount,
                currency=charge.currency,
                quantity=charge.quantity,
            )
            for charge in note.charges
        ],
        total_amount=total_amount(note),
        created_at=note.created_at,
    )


@router.post("", response_model=DebitNoteResponse)
async def create_debit_note_endpoint(
    payload: DebitNoteCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission("debit_note", "create")),
) -> DebitNoteResponse:
    try:
        note = await create_debit_note(db, payload, UUID(current_user.user_id))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _to_response(note)


@router.get("/{debit_note_id}", response_model=DebitNoteResponse)
async def get_debit_note_endpoint(
    debit_note_id: UUID,
    db: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_permission("debit_note", "view")),
) -> DebitNoteResponse:
    note = await get_debit_note(db, debit_note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="Debit note not found")
    return _to_response(note)


@container_router.get(
    "/containers/{container_no}/debit-notes", response_model=DebitNoteListResponse
)
async def list_container_debit_notes_endpoint(
    container_no: str,
    db: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_permission("debit_note", "view")),
) -> DebitNoteListResponse:
    container = await get_container_by_no(db, container_no)
    if container is None:
        raise HTTPException(status_code=404, detail="Container not found")
    notes = await list_debit_notes_for_container(db, container.id)
    return DebitNoteListResponse(
        items=[_to_response(note) for note in notes], total=len(notes)
    )
