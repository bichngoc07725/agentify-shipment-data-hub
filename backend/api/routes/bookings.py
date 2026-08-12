from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps.permissions import CurrentUser, require_permission
from api.models import (
    BookingCreateRequest,
    ComposedMailResponse,
    BookingListResponse,
    BookingResponse,
    BookingUpdateRequest,
)
from db.database import get_db
from db.models import Booking
from services.booking_mail_service import build_booking_request_mail
from services.booking_service import (
    create_booking,
    get_booking,
    get_booking_prefill,
    get_booking_prefill_from_quote,
    list_bookings_for_container,
    list_bookings_for_quote,
    next_cutoff,
    update_booking,
)

router = APIRouter(prefix="/api/v1/bookings", tags=["bookings"])
container_router = APIRouter(prefix="/api/v1", tags=["bookings"])


def _to_response(booking: Booking) -> BookingResponse:
    label, at, hours = next_cutoff(booking)
    return BookingResponse(
        id=booking.id,
        container_id=booking.container_id,
        container_no=booking.container.container_no if booking.container else None,
        quote_id=booking.quote_id,
        quote_no=booking.quote.quote_no if booking.quote else None,
        booking_no=booking.booking_no,
        status=booking.status.value,
        carrier=booking.carrier,
        vessel=booking.vessel,
        voyage=booking.voyage,
        pol=booking.pol,
        pod=booking.pod,
        etd=booking.etd,
        eta=booking.eta,
        si_cutoff_at=booking.si_cutoff_at,
        vgm_cutoff_at=booking.vgm_cutoff_at,
        gate_in_cutoff_at=booking.gate_in_cutoff_at,
        container_type=booking.container_type,
        container_qty=booking.container_qty,
        empty_pickup_depot=booking.empty_pickup_depot,
        freight_rate=booking.freight_rate,
        currency=booking.currency,
        note=booking.note,
        created_by=booking.created_by,
        next_cutoff_label=label,
        next_cutoff_at=at,
        hours_to_next_cutoff=hours,
        created_at=booking.created_at,
        updated_at=booking.updated_at,
    )


@router.post("", response_model=BookingResponse)
async def create_booking_endpoint(
    payload: BookingCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission("booking", "create")),
) -> BookingResponse:
    try:
        booking = await create_booking(db, payload, UUID(current_user.user_id))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _to_response(booking)


@router.put("/{booking_id}", response_model=BookingResponse)
async def update_booking_endpoint(
    booking_id: UUID,
    payload: BookingUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_permission("booking", "edit")),
) -> BookingResponse:
    updated = await update_booking(db, booking_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail="Booking not found")
    return _to_response(updated)


@router.get("/{booking_id}", response_model=BookingResponse)
async def get_booking_endpoint(
    booking_id: UUID,
    db: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_permission("booking", "view")),
) -> BookingResponse:
    booking = await get_booking(db, booking_id)
    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")
    return _to_response(booking)


@router.get("/{booking_id}/request-mail", response_model=ComposedMailResponse)
async def get_booking_request_mail_endpoint(
    booking_id: UUID,
    db: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_permission("booking", "edit")),
) -> ComposedMailResponse:
    """Soạn sẵn thư đặt chỗ gửi hãng tàu. Agentify không gửi hộ."""
    booking = await get_booking(db, booking_id)
    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")
    return ComposedMailResponse(**build_booking_request_mail(booking))


@container_router.get(
    "/containers/{container_no}/bookings", response_model=BookingListResponse
)
async def list_container_bookings_endpoint(
    container_no: str,
    db: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_permission("booking", "view")),
) -> BookingListResponse:
    bookings = await list_bookings_for_container(db, container_no)
    items = [_to_response(booking) for booking in bookings]
    return BookingListResponse(items=items, total=len(items))


@container_router.get("/quotes/{quote_id}/bookings", response_model=BookingListResponse)
async def list_quote_bookings_endpoint(
    quote_id: UUID,
    db: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_permission("booking", "view")),
) -> BookingListResponse:
    bookings = await list_bookings_for_quote(db, quote_id)
    items = [_to_response(booking) for booking in bookings]
    return BookingListResponse(items=items, total=len(items))


@container_router.get("/quotes/{quote_id}/booking-prefill")
async def quote_booking_prefill_endpoint(
    quote_id: UUID,
    db: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_permission("booking", "create")),
) -> dict[str, str]:
    """Thông tin đặt chỗ suy ra từ báo giá đã chốt.

    Nguồn đúng của Bước 2: lúc này chưa có container nào để đọc facts, còn báo
    giá thì đã có tuyến, thiết bị và ngày hàng sẵn.
    """
    prefill = await get_booking_prefill_from_quote(db, quote_id)
    if prefill is None:
        raise HTTPException(status_code=404, detail="Quote not found")
    return prefill


@container_router.get("/containers/{container_no}/booking-prefill")
async def booking_prefill_endpoint(
    container_no: str,
    db: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_permission("booking", "create")),
) -> dict[str, str]:
    """Giá trị pipeline đã đọc được từ mail hãng tàu, để điền sẵn form đặt chỗ.

    Trả về dict rỗng khi chưa đọc được gì — đúng nguyên tắc "không tìm thấy
    trong Agentify" thay vì đoán một số booking.
    """
    try:
        return await get_booking_prefill(db, container_no)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
