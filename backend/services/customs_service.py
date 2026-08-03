"""Customs declarations: VNACCS phân luồng (Xanh/Vàng/Đỏ) result for a
container's shipment. Owned by `ops`; Docs/Kế toán/Admin/Manager view only.
See `plan/phase_7_customs_kanban_brief.md` Part 7A.
"""

from __future__ import annotations

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
