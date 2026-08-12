"""Bước 2 — đặt chỗ trên tàu. Thuộc sở hữu `ops`.

Bảng này trả lời câu hỏi mà `container_facts` không trả lời được: lô này đã
đặt chỗ chưa, với hãng nào, giá bao nhiêu, và **còn bao lâu tới giờ chốt**.
Rủi ro gốc của bước này là trễ giờ cut-off dẫn tới rớt chuyến, nên mốc chốt
được tính sẵn ở server thay vì để mỗi màn hình tự suy ra.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.models import BookingCreateRequest, BookingUpdateRequest
from db.models import Booking, BookingStatus, ContainerFact, Quote
from services.container_service import get_container_by_no

_LOAD_OPTIONS = (
    selectinload(Booking.container),
    selectinload(Booking.quote),
)

# Thứ tự đúng theo thực tế khai thác: SI chốt trước, rồi VGM, cuối cùng là hạ
# container vào cảng.
CUTOFF_FIELDS: tuple[tuple[str, str], ...] = (
    ("si_cutoff_at", "SI cut-off"),
    ("vgm_cutoff_at", "VGM cut-off"),
    ("gate_in_cutoff_at", "Hạ container (gate-in)"),
)

# Các field mà pipeline trích xuất có thể đã đọc được từ mail hãng tàu, dùng
# để điền sẵn form — nhân viên xác nhận thay vì gõ lại.
_PREFILL_FIELDS = ("booking_no", "vessel", "voyage", "pol", "pod", "etd", "eta")


def next_cutoff(
    booking: Booking, now: datetime | None = None
) -> tuple[str | None, datetime | None, float | None]:
    """Mốc chốt kế tiếp CHƯA qua, kèm số giờ còn lại (âm nếu đã trễ).

    Booking đã huỷ thì không còn mốc nào để cảnh báo — trả về rỗng, nếu không
    bảng Kanban sẽ đỏ rực vì những lô đã bỏ.
    """
    if booking.status == BookingStatus.CANCELLED:
        return None, None, None

    current = now or datetime.now(UTC)
    upcoming: list[tuple[datetime, str]] = []
    for field_name, label in CUTOFF_FIELDS:
        value = getattr(booking, field_name)
        if value is None:
            continue
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        upcoming.append((value, label))

    if not upcoming:
        return None, None, None

    # Mốc chưa qua thì lấy mốc gần nhất; nếu mọi mốc đã qua thì lấy mốc trễ
    # nhất, vì "đã trễ 3 tiếng" vẫn là thông tin cần hiện, không phải im lặng.
    future = [item for item in upcoming if item[0] >= current]
    chosen = min(future) if future else max(upcoming)
    at, label = chosen
    hours = (at - current).total_seconds() / 3600
    return label, at, round(hours, 2)


async def _prefill_from_facts(db: AsyncSession, container_id: UUID) -> dict[str, str]:
    """Giá trị pipeline đã bóc được từ mail hãng tàu cho lô này.

    Chỉ để gợi ý khi mở form — không tự ghi vào booking, vì booking là thứ
    người chịu trách nhiệm xác nhận, không phải thứ máy suy ra.
    """
    result = await db.execute(
        select(
            ContainerFact.field_name,
            ContainerFact.normalized_value,
            ContainerFact.field_value,
            ContainerFact.source_sent_at,
        )
        .where(
            ContainerFact.container_id == container_id,
            ContainerFact.field_name.in_(_PREFILL_FIELDS),
        )
        .order_by(
            ContainerFact.source_sent_at.desc().nullslast(),
            ContainerFact.created_at.desc(),
        )
    )
    prefill: dict[str, str] = {}
    for field_name, normalized, raw, _ in result.all():
        # Bản ghi đầu tiên gặp là mới nhất nhờ ORDER BY ở trên.
        prefill.setdefault(field_name, normalized or raw)
    return prefill


async def get_booking_prefill(db: AsyncSession, container_no: str) -> dict[str, str]:
    container = await get_container_by_no(db, container_no)
    if container is None:
        raise ValueError(f"Container '{container_no}' not found")
    return await _prefill_from_facts(db, container.id)


async def get_booking_prefill_from_quote(
    db: AsyncSession, quote_id: UUID
) -> dict[str, str] | None:
    """Thông tin đặt chỗ suy ra từ báo giá đã chốt với khách.

    Đây mới là nguồn đúng ở Bước 2: lúc đi đặt chỗ thì chưa có container nào để
    mà đọc `container_facts`, còn báo giá thì đã có sẵn tuyến, thiết bị, ngày
    hàng sẵn và hãng tàu đã chào giá. Cước trong báo giá là giá BÁN nên KHÔNG
    chép sang `freight_rate` (giá mua) — hai con số đó khác nhau, và chênh lệch
    giữa chúng chính là biên lợi nhuận cần nhìn thấy.
    """
    result = await db.execute(select(Quote).where(Quote.id == quote_id))
    quote = result.scalar_one_or_none()
    if quote is None:
        return None

    prefill = {
        "pol": quote.pol,
        "pod": quote.pod,
        "container_type": quote.container_type,
        "container_qty": str(quote.container_qty) if quote.container_qty else None,
        "etd": quote.cargo_ready_date.isoformat() if quote.cargo_ready_date else None,
        "customer_name": quote.customer_name,
        "commodity": quote.commodity,
    }
    return {key: value for key, value in prefill.items() if value}


def _apply(booking: Booking, payload: BookingCreateRequest | BookingUpdateRequest) -> None:
    booking.quote_id = payload.quote_id
    booking.booking_no = payload.booking_no
    booking.status = BookingStatus(payload.status)
    booking.carrier = payload.carrier
    booking.vessel = payload.vessel
    booking.voyage = payload.voyage
    booking.pol = payload.pol
    booking.pod = payload.pod
    booking.etd = payload.etd
    booking.eta = payload.eta
    booking.si_cutoff_at = payload.si_cutoff_at
    booking.vgm_cutoff_at = payload.vgm_cutoff_at
    booking.gate_in_cutoff_at = payload.gate_in_cutoff_at
    booking.container_type = payload.container_type
    booking.container_qty = payload.container_qty
    booking.empty_pickup_depot = payload.empty_pickup_depot
    booking.freight_rate = payload.freight_rate
    booking.currency = payload.currency
    booking.note = payload.note


async def create_booking(
    db: AsyncSession, payload: BookingCreateRequest, created_by: UUID
) -> Booking:
    container_id = None
    if payload.container_no:
        container = await get_container_by_no(db, payload.container_no)
        if container is None:
            raise ValueError(f"Container '{payload.container_no}' not found")
        container_id = container.id

    booking = Booking(container_id=container_id, created_by=created_by)
    _apply(booking, payload)

    db.add(booking)
    await db.commit()

    return await get_booking(db, booking.id)


async def update_booking(
    db: AsyncSession, booking_id: UUID, payload: BookingUpdateRequest
) -> Booking | None:
    booking = await get_booking(db, booking_id)
    if booking is None:
        return None

    _apply(booking, payload)
    await db.commit()

    return await get_booking(db, booking_id)


async def get_booking(db: AsyncSession, booking_id: UUID) -> Booking | None:
    result = await db.execute(
        select(Booking).options(*_LOAD_OPTIONS).where(Booking.id == booking_id)
    )
    return result.scalar_one_or_none()


async def list_bookings_for_quote(db: AsyncSession, quote_id: UUID) -> list[Booking]:
    """Các chỗ đặt gắn với một báo giá, kể cả chỗ chưa có container."""
    result = await db.execute(
        select(Booking)
        .options(*_LOAD_OPTIONS)
        .where(Booking.quote_id == quote_id)
        .order_by(Booking.created_at.desc())
    )
    return list(result.scalars().all())


async def list_bookings_for_container(
    db: AsyncSession, container_no: str
) -> list[Booking]:
    container = await get_container_by_no(db, container_no)
    if container is None:
        return []

    result = await db.execute(
        select(Booking)
        .options(*_LOAD_OPTIONS)
        .where(Booking.container_id == container.id)
        .order_by(Booking.created_at.desc())
    )
    return list(result.scalars().all())
