"""Quotes (RFQ/báo giá) — the price baseline Bước 6 reconciliation compares
real costs against. Owned by `sales_cs`; see `plan/phase_4_quote_brief.md`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.models import QuoteChargeRequest, QuoteCreateRequest, QuoteUpdateRequest
from db.models import ChargeGroup, Quote, QuoteCharge, QuoteStatus
from services.container_service import get_container_by_no

_LOAD_OPTIONS = (selectinload(Quote.charges), selectinload(Quote.container))


def compute_charge_amount(unit_price: Decimal, quantity: Decimal) -> Decimal:
    return unit_price * quantity


def build_quote_no(year: int, sequence: int) -> str:
    """`Q-2026-0001` style — sequence is 1-based, per calendar year."""
    return f"Q-{year}-{sequence:04d}"


def total_amount(quote: Quote) -> Decimal:
    return sum((charge.amount for charge in quote.charges), Decimal("0"))


async def _next_quote_no(db: AsyncSession, year: int) -> str:
    prefix = f"Q-{year}-"
    result = await db.execute(
        select(func.count(Quote.id)).where(Quote.quote_no.like(f"{prefix}%"))
    )
    count = result.scalar_one()
    return build_quote_no(year, count + 1)


def _build_charge(payload: QuoteChargeRequest) -> QuoteCharge:
    return QuoteCharge(
        charge_group=ChargeGroup(payload.charge_group),
        charge_code=payload.charge_code,
        description=payload.description,
        unit_price=payload.unit_price,
        currency=payload.currency,
        quantity=payload.quantity,
        amount=compute_charge_amount(payload.unit_price, payload.quantity),
    )


async def _resolve_container_id(
    db: AsyncSession, container_no: str | None
) -> UUID | None:
    if not container_no:
        return None
    container = await get_container_by_no(db, container_no)
    if container is None:
        raise ValueError(f"Container '{container_no}' not found")
    return container.id


async def create_quote(
    db: AsyncSession, payload: QuoteCreateRequest, created_by: UUID
) -> Quote:
    container_id = await _resolve_container_id(db, payload.container_no)
    now = datetime.now(UTC)

    quote = Quote(
        quote_no=await _next_quote_no(db, now.year),
        customer_name=payload.customer_name,
        status=QuoteStatus(payload.status),
        pol=payload.pol,
        pod=payload.pod,
        commodity=payload.commodity,
        is_dangerous=payload.is_dangerous,
        is_reefer=payload.is_reefer,
        container_type=payload.container_type,
        container_qty=payload.container_qty,
        gross_weight_kg=payload.gross_weight_kg,
        cargo_ready_date=payload.cargo_ready_date,
        incoterm=payload.incoterm,
        payment_term=payload.payment_term,
        transit_time=payload.transit_time,
        valid_until=payload.valid_until,
        note=payload.note,
        currency=payload.currency,
        created_by=created_by,
        container_id=container_id,
        charges=[_build_charge(charge) for charge in payload.charges],
    )
    db.add(quote)
    await db.flush()
    return await get_quote(db, quote.id)  # type: ignore[return-value]


async def get_quote(db: AsyncSession, quote_id: UUID) -> Quote | None:
    result = await db.execute(
        select(Quote).where(Quote.id == quote_id).options(*_LOAD_OPTIONS)
    )
    return result.scalar_one_or_none()


async def list_quotes(
    db: AsyncSession,
    customer_name: str | None = None,
    status: str | None = None,
    container_no: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Quote], int]:
    stmt = select(Quote).options(*_LOAD_OPTIONS)
    count_stmt = select(func.count(Quote.id))

    if customer_name:
        pattern = f"%{customer_name.strip()}%"
        stmt = stmt.where(Quote.customer_name.ilike(pattern))
        count_stmt = count_stmt.where(Quote.customer_name.ilike(pattern))
    if status:
        stmt = stmt.where(Quote.status == QuoteStatus(status))
        count_stmt = count_stmt.where(Quote.status == QuoteStatus(status))
    if container_no:
        container = await get_container_by_no(db, container_no)
        if container is None:
            # `Quote.container_id == None` would compile to `IS NULL` and
            # match every quote with no container at all — the opposite of
            # "no quotes for this (nonexistent) container".
            return [], 0
        stmt = stmt.where(Quote.container_id == container.id)
        count_stmt = count_stmt.where(Quote.container_id == container.id)

    stmt = (
        stmt.order_by(Quote.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    total_result = await db.execute(count_stmt)
    return list(result.scalars().all()), total_result.scalar_one()


async def list_quotes_for_container(
    db: AsyncSession, container_id: UUID
) -> list[Quote]:
    result = await db.execute(
        select(Quote)
        .where(Quote.container_id == container_id)
        .options(*_LOAD_OPTIONS)
        .order_by(Quote.created_at.desc())
    )
    return list(result.scalars().all())


async def update_quote(
    db: AsyncSession, quote: Quote, payload: QuoteUpdateRequest
) -> Quote:
    quote.container_id = await _resolve_container_id(db, payload.container_no)
    quote.customer_name = payload.customer_name
    quote.status = QuoteStatus(payload.status)
    quote.pol = payload.pol
    quote.pod = payload.pod
    quote.commodity = payload.commodity
    quote.is_dangerous = payload.is_dangerous
    quote.is_reefer = payload.is_reefer
    quote.container_type = payload.container_type
    quote.container_qty = payload.container_qty
    quote.gross_weight_kg = payload.gross_weight_kg
    quote.cargo_ready_date = payload.cargo_ready_date
    quote.incoterm = payload.incoterm
    quote.payment_term = payload.payment_term
    quote.transit_time = payload.transit_time
    quote.valid_until = payload.valid_until
    quote.note = payload.note
    quote.currency = payload.currency
    quote.charges = [_build_charge(charge) for charge in payload.charges]

    await db.flush()
    return await get_quote(db, quote.id)  # type: ignore[return-value]


async def delete_quote(db: AsyncSession, quote: Quote) -> None:
    await db.delete(quote)
    await db.flush()
