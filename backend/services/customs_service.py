"""Customs declarations: VNACCS phân luồng (Xanh/Vàng/Đỏ) result for a
container's shipment. Owned by `ops`; Docs/Kế toán/Admin/Manager view only.
See `plan/phase_7_customs_kanban_brief.md` Part 7A.
"""

from __future__ import annotations

import re
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.models import CustomsDeclarationCreateRequest, CustomsDeclarationUpdateRequest
from db.models import (
    ContainerFact,
    CustomsChannel,
    CustomsChannelHistory,
    CustomsDeclaration,
    CustomsDeclarationType,
)
from services.container_service import get_container_by_no

_LOAD_OPTIONS = (
    selectinload(CustomsDeclaration.channel_history),
    selectinload(CustomsDeclaration.container),
)


async def _prefill_hs_code(db: AsyncSession, container_id: UUID) -> str | None:
    """HS code the extraction pipeline may already have read from a document.
    Not built here — just looked up if a future extractor has written one."""

    result = await db.execute(
        select(ContainerFact.normalized_value, ContainerFact.field_value)
        .where(
            ContainerFact.container_id == container_id,
            ContainerFact.field_name == "hs_code",
        )
        .order_by(
            ContainerFact.source_sent_at.desc().nullslast(),
            ContainerFact.created_at.desc(),
        )
        .limit(1)
    )
    row = result.first()
    if row is None:
        return None
    normalized, raw = row
    return normalized or raw


# Fact mà thông báo hải quan đã được bóc tách ra, dùng điền sẵn form.
_PREFILL_FACT_FIELDS = {
    "customs_lane": "channel",
    "customs_registered_at": "registered_at",
    "customs_cleared_at": "cleared_at",
    "customs_tax_amount": "tax_amount",
    "hs_code": "hs_code",
    "declaration_no": "declaration_no",
}

# Hải quan Việt Nam gọi luồng bằng màu; LLM có thể trả tiếng Anh lẫn tiếng Việt.
_LANE_ALIASES = {
    "green": "green", "xanh": "green", "luong xanh": "green", "luồng xanh": "green",
    "yellow": "yellow", "vang": "yellow", "vàng": "yellow", "luồng vàng": "yellow",
    "red": "red", "do": "red", "đỏ": "red", "luồng đỏ": "red",
}


def normalize_lane(value: str | None) -> str | None:
    """Đưa cách gọi luồng về đúng ba giá trị enum, hoặc None nếu không chắc.

    Đoán bừa một luồng là chuyện nguy hiểm: luồng quyết định lô có bị kiểm hoá
    hay không, và một cảnh báo luồng Đỏ sai làm cả nhóm chạy nhầm việc.
    """
    if not value:
        return None
    return _LANE_ALIASES.get(value.strip().lower())


_AMOUNT_RE = re.compile(r"\d[\d.,]*")


def numeric_amount(value: str | None) -> str | None:
    """Bỏ ký hiệu tiền tệ và dấu phân nhóm: `"VND 42,150,000"` -> `"42150000"`.

    Ô Tiền thuế trên form là `input type="number"`; đưa vào một chuỗi có chữ
    thì trình duyệt lặng lẽ bỏ trắng ô, trong khi băng thông báo vẫn khoe "đã
    điền N trường" — Ops tưởng đã có thuế rồi lưu một tờ khai thiếu tiền.
    """
    if not value:
        return None
    match = _AMOUNT_RE.search(value)
    if match is None:
        return None
    raw = match.group(0).rstrip(".,")
    # Số Việt Nam dùng `.` phân nhóm nghìn và `,` thập phân; số Anh–Mỹ ngược
    # lại. Dấu nào xuất hiện sau cùng và chỉ một lần thì đó là dấu thập phân.
    last_dot, last_comma = raw.rfind("."), raw.rfind(",")
    decimal_sep = "." if last_dot > last_comma else ","
    if raw.count(decimal_sep) == 1 and len(raw) - raw.rfind(decimal_sep) - 1 in (1, 2):
        whole, _, frac = raw.rpartition(decimal_sep)
        cleaned = re.sub(r"\D", "", whole) + "." + frac
    else:
        cleaned = re.sub(r"\D", "", raw)
    return cleaned or None


async def get_declaration_prefill(
    db: AsyncSession, container_no: str
) -> dict[str, str] | None:
    """Giá trị hệ thống đã đọc được từ thông báo hải quan, để điền sẵn form."""
    container = await get_container_by_no(db, container_no)
    if container is None:
        return None

    result = await db.execute(
        select(
            ContainerFact.field_name,
            ContainerFact.normalized_value,
            ContainerFact.field_value,
        )
        .where(
            ContainerFact.container_id == container.id,
            ContainerFact.field_name.in_(_PREFILL_FACT_FIELDS),
        )
        .order_by(
            ContainerFact.source_sent_at.desc().nullslast(),
            ContainerFact.created_at.desc(),
        )
    )

    prefill: dict[str, str] = {}
    for field_name, normalized, raw in result.all():
        target = _PREFILL_FACT_FIELDS[field_name]
        if target in prefill:
            continue
        value = normalized or raw
        if target == "channel":
            value = normalize_lane(value)
        if target == "tax_amount":
            value = numeric_amount(value)
        if value:
            prefill[target] = str(value)
    return prefill


async def create_declaration(
    db: AsyncSession, payload: CustomsDeclarationCreateRequest, created_by: UUID
) -> CustomsDeclaration:
    container = await get_container_by_no(db, payload.container_no)
    if container is None:
        raise ValueError(f"Container '{payload.container_no}' not found")

    hs_code = payload.hs_code or await _prefill_hs_code(db, container.id)
    channel = CustomsChannel(payload.channel) if payload.channel else None

    declaration = CustomsDeclaration(
        container_id=container.id,
        declaration_no=payload.declaration_no,
        declaration_type=CustomsDeclarationType(payload.declaration_type),
        channel=channel,
        hs_code=hs_code,
        registered_at=payload.registered_at,
        cleared_at=payload.cleared_at,
        tax_amount=payload.tax_amount,
        note=payload.note,
        created_by=created_by,
    )
    db.add(declaration)
    await db.flush()

    if channel is not None:
        db.add(
            CustomsChannelHistory(
                declaration_id=declaration.id,
                from_channel=None,
                to_channel=channel,
                changed_by=created_by,
                reason="Khởi tạo tờ khai",
            )
        )
        await db.flush()

    return await get_declaration(db, declaration.id)  # type: ignore[return-value]


async def update_declaration(
    db: AsyncSession,
    declaration: CustomsDeclaration,
    payload: CustomsDeclarationUpdateRequest,
    changed_by: UUID,
) -> CustomsDeclaration:
    old_channel = declaration.channel
    new_channel = CustomsChannel(payload.channel) if payload.channel else None

    declaration.declaration_no = payload.declaration_no
    declaration.declaration_type = CustomsDeclarationType(payload.declaration_type)
    declaration.channel = new_channel
    if payload.hs_code is not None:
        declaration.hs_code = payload.hs_code
    declaration.registered_at = payload.registered_at
    declaration.cleared_at = payload.cleared_at
    declaration.tax_amount = payload.tax_amount
    declaration.note = payload.note

    # `to_channel` is NOT NULL, so clearing a channel back to "unknown" is not
    # a re-assignment worth a history row — only a real bẻ luồng is.
    if new_channel is not None and new_channel != old_channel:
        db.add(
            CustomsChannelHistory(
                declaration_id=declaration.id,
                from_channel=old_channel,
                to_channel=new_channel,
                changed_by=changed_by,
                reason=payload.channel_change_reason,
            )
        )

    await db.flush()
    return await get_declaration(db, declaration.id)  # type: ignore[return-value]


async def get_declaration(
    db: AsyncSession, declaration_id: UUID
) -> CustomsDeclaration | None:
    # `update_declaration` re-fetches the same identity already in the
    # session (loaded once by the route handler before the edit) — without
    # `populate_existing`, SQLAlchemy would keep serving the pre-edit
    # `channel_history` collection from its identity map instead of the row
    # just flushed.
    result = await db.execute(
        select(CustomsDeclaration)
        .where(CustomsDeclaration.id == declaration_id)
        .options(*_LOAD_OPTIONS)
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


async def list_declarations_for_container(
    db: AsyncSession, container_id: UUID
) -> list[CustomsDeclaration]:
    result = await db.execute(
        select(CustomsDeclaration)
        .where(CustomsDeclaration.container_id == container_id)
        .options(*_LOAD_OPTIONS)
        .order_by(CustomsDeclaration.created_at.desc())
    )
    return list(result.scalars().all())
