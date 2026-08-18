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
from db.models import Booking, BookingStatus, ContainerFact, Email, Quote
from gmail_service.deterministic_extract import extract_deterministic
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
_PREFILL_FIELDS = (
    "booking_no",
    "vessel",
    "voyage",
    "pol",
    "pod",
    "etd",
    "eta",
    # Đúng mười ô của bảng "cập nhật sau khi hãng tàu xác nhận" (Bước 2.4).
    # Thiếu bốn trường này thì nút điền sẵn chỉ đỡ được một nửa, và nửa còn lại
    # lại là nửa quan trọng hơn — ba mốc chốt.
    "si_cutoff_at",
    "vgm_cutoff_at",
    "gate_in_cutoff_at",
    "empty_pickup_depot",
)


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


async def get_booking_prefill_from_email(
    db: AsyncSession, email_id: UUID
) -> dict[str, str] | None:
    """Thông tin đặt chỗ đọc thẳng từ MỘT thư do người dùng chỉ định.

    Đây là nguồn đúng ở Bước 2.4. Lúc đó chỗ đặt vẫn chưa gắn container — 2.1
    cố ý để trống vì hãng tàu chưa cấp — nên không có đường nào đi từ chỗ đặt
    tới `container_facts`, còn báo giá thì không bao giờ biết số booking hay ba
    mốc cut-off. Người dùng vừa đọc thư xác nhận ở 2.3, nên để họ chỉ đúng thư
    đó là cách duy nhất không phải đoán.

    Trả cả `container_no`: chính khoảnh khắc này container mới ra đời, và gõ
    lại một số container 11 ký tự là chỗ dễ sai nhất trong cả bước.
    """
    result = await db.execute(
        select(Email).options(selectinload(Email.attachments)).where(Email.id == email_id)
    )
    email = result.scalar_one_or_none()
    if email is None:
        return None

    parts = [email.subject or "", email.body_text or ""]
    parts.extend(a.extracted_text for a in email.attachments if a.extracted_text)
    content = "\n".join(part for part in parts if part.strip())

    fields = extract_deterministic(email.subject or "", email.from_email or "", content)
    identifiers = fields.get("identifiers") or {}
    route = fields.get("route") or {}

    prefill: dict[str, str | None] = {
        field: route.get(field) or identifiers.get(field) for field in _PREFILL_FIELDS
    }
    container_nos = identifiers.get("container_no") or []
    # Chỉ nhận khi thư nói tới đúng một container. Thư nhắc nhiều container thì
    # không có căn cứ chọn cái nào, và điền nhầm số container vào chỗ đặt là
    # loại lỗi phải lần ngược từ cảng mới phát hiện.
    if len(container_nos) == 1:
        prefill["container_no"] = container_nos[0]
    prefill["carrier"] = fields.get("carrier")

    return {key: str(value) for key, value in prefill.items() if value}


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
    await db.flush()
    await _link_quote_to_container(db, booking)
    await db.commit()

    return await get_booking(db, booking.id)


async def update_booking(
    db: AsyncSession, booking_id: UUID, payload: BookingUpdateRequest
) -> Booking | None:
    booking = await get_booking(db, booking_id)
    if booking is None:
        return None

    if payload.container_no:
        container = await get_container_by_no(db, payload.container_no)
        if container is None:
            raise ValueError(f"Container '{payload.container_no}' not found")
        booking.container_id = container.id
        # Session dùng `expire_on_commit=False`, nên quan hệ `container` đã nạp
        # là None sẽ ở nguyên None sau khi commit dù khoá ngoại đã đổi — bản ghi
        # trong DB đúng mà phản hồi trả về vẫn báo chưa có container.
        booking.container = container

    _apply(booking, payload)
    await _link_quote_to_container(db, booking)
    await db.commit()

    return await get_booking(db, booking_id)


async def _link_quote_to_container(db: AsyncSession, booking: Booking) -> None:
    """Nối báo giá với container ngay khi chỗ đặt biết cả hai đầu.

    Đây là khoảnh khắc DUY NHẤT trong toàn bộ luồng mà quan hệ này lộ ra: Bước 1
    lập báo giá khi chưa có container, Bước 2.4 hãng tàu xác nhận thì container
    mới ra đời, và chỗ đặt là bản ghi duy nhất cầm cả `quote_id` lẫn
    `container_id`.

    Không truyền sang thì `quotes.container_id` mãi rỗng, và Bước 6 — vốn tra
    báo giá THEO CONTAINER — báo "container chưa có báo giá nào" dù báo giá nằm
    ngay đó. Đối soát mất luôn mốc để so, tức mất cả mục đích của bước.

    Chỉ điền khi đang rỗng: báo giá đã trỏ sang container khác là chuyện người
    dùng cố ý, không được đè.
    """
    if booking.quote_id is None or booking.container_id is None:
        return

    result = await db.execute(select(Quote).where(Quote.id == booking.quote_id))
    quote = result.scalar_one_or_none()
    if quote is not None and quote.container_id is None:
        quote.container_id = booking.container_id


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
