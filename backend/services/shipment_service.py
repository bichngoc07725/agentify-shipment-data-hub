"""Shipment/job Kanban board: groups containers under one 6-step job (RFQ →
booking → documents → customs → delivery → reconciliation → closed). See
`plan/phase_7_customs_kanban_brief.md` Part 7B.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.models import ShipmentCreateRequest
from db.models import Container, CustomsDeclarationType, Shipment, ShipmentStage, UserRole

# Kanban column order — `advance_stage` walks this list; `closed` is terminal.
STAGE_ORDER: list[ShipmentStage] = [
    ShipmentStage.RFQ,
    ShipmentStage.BOOKING,
    ShipmentStage.DOCUMENTS,
    ShipmentStage.CUSTOMS,
    ShipmentStage.DELIVERY,
    ShipmentStage.RECONCILIATION,
    ShipmentStage.CLOSED,
]

# Stage → (role that owns it, SLA to clear it). `closed` has neither.
STAGE_CONFIG: dict[ShipmentStage, tuple[UserRole | None, timedelta | None]] = {
    ShipmentStage.RFQ: (UserRole.SALES_CS, timedelta(hours=24)),
    ShipmentStage.BOOKING: (UserRole.OPS, timedelta(hours=24)),
    ShipmentStage.DOCUMENTS: (UserRole.DOCS, timedelta(hours=48)),
    ShipmentStage.CUSTOMS: (UserRole.OPS, timedelta(hours=48)),
    ShipmentStage.DELIVERY: (UserRole.OPS, timedelta(hours=24)),
    ShipmentStage.RECONCILIATION: (UserRole.ACCOUNTANT, timedelta(hours=72)),
    ShipmentStage.CLOSED: (None, None),
}

_LOAD_OPTIONS = (
    selectinload(Shipment.containers),
    selectinload(Shipment.quote),
)


class StageAdvanceError(Exception):
    """Raised when a shipment can't move to its next stage (already closed)."""


class StageOwnerError(Exception):
    """Raised when the caller's role doesn't own the shipment's current stage."""


def build_shipment_no(year: int, sequence: int) -> str:
    return f"JOB-{year}-{sequence:04d}"


def next_stage(current: ShipmentStage) -> ShipmentStage | None:
    index = STAGE_ORDER.index(current)
    if index + 1 >= len(STAGE_ORDER):
        return None
    return STAGE_ORDER[index + 1]


def owner_role_for(stage: ShipmentStage) -> UserRole | None:
    return STAGE_CONFIG[stage][0]


def sla_due_at_for(stage: ShipmentStage, now: datetime) -> datetime | None:
    sla = STAGE_CONFIG[stage][1]
    return now + sla if sla is not None else None


def is_sla_breached(shipment: Shipment, now: datetime | None = None) -> bool:
    if shipment.stage == ShipmentStage.CLOSED or shipment.sla_due_at is None:
        return False
    return (now or datetime.now(UTC)) > shipment.sla_due_at


def can_advance(shipment: Shipment, role: UserRole) -> bool:
    """Only the role that owns the current stage (or Admin/Manager, who
    oversee every stage) may push a job forward — a stage's owner is the one
    person accountable for clearing it, so anyone else advancing it would
    hide who actually did the work."""

    if role in (UserRole.ADMIN, UserRole.MANAGER):
        return True
    return role == shipment.owner_role


async def _next_sequence_for_year(db: AsyncSession, year: int) -> int:
    prefix = f"JOB-{year}-"
    result = await db.execute(
        select(func.count()).where(Shipment.shipment_no.like(f"{prefix}%"))
    )
    return (result.scalar_one() or 0) + 1


async def create_shipment(db: AsyncSession, payload: ShipmentCreateRequest) -> Shipment:
    now = datetime.now(UTC)
    sequence = await _next_sequence_for_year(db, now.year)

    shipment = Shipment(
        shipment_no=build_shipment_no(now.year, sequence),
        customer_name=payload.customer_name,
        direction=CustomsDeclarationType(payload.direction) if payload.direction else None,
        stage=ShipmentStage.RFQ,
        quote_id=payload.quote_id,
        owner_role=owner_role_for(ShipmentStage.RFQ),
        sla_due_at=sla_due_at_for(ShipmentStage.RFQ, now),
    )
    db.add(shipment)
    await db.flush()

    if payload.container_nos:
        await db.execute(
            Container.__table__.update()
            .where(Container.container_no.in_(payload.container_nos))
            .values(shipment_id=shipment.id)
        )
        await db.flush()

    return await get_shipment(db, shipment.id)  # type: ignore[return-value]


async def advance_stage(db: AsyncSession, shipment: Shipment, role: UserRole) -> Shipment:
    if not can_advance(shipment, role):
        raise StageOwnerError(
            f"Role '{role.value}' does not own stage '{shipment.stage.value}'"
        )

    target = next_stage(shipment.stage)
    if target is None:
        raise StageAdvanceError("Shipment is already closed")

    now = datetime.now(UTC)
    shipment.stage = target
    shipment.owner_role = owner_role_for(target)
    shipment.sla_due_at = sla_due_at_for(target, now)
    await db.flush()

    return await get_shipment(db, shipment.id)  # type: ignore[return-value]


async def move_to_stage(
    db: AsyncSession, shipment: Shipment, target: ShipmentStage, role: UserRole
) -> Shipment:
    """Drop a job onto any column, forwards or backwards.

    `advance_stage` only ever steps forward, which cannot express "this was
    moved on too early, put it back". Permission is the same rule: the owner
    of the stage the job is leaving, or Admin/Manager who oversee all of them.
    """

    if not can_advance(shipment, role):
        raise StageOwnerError(
            f"Role '{role.value}' does not own stage '{shipment.stage.value}'"
        )

    if target == shipment.stage:
        return await get_shipment(db, shipment.id)  # type: ignore[return-value]

    now = datetime.now(UTC)
    shipment.stage = target
    shipment.owner_role = owner_role_for(target)
    shipment.sla_due_at = sla_due_at_for(target, now)
    await db.flush()

    return await get_shipment(db, shipment.id)  # type: ignore[return-value]


async def get_shipment(db: AsyncSession, shipment_id: UUID) -> Shipment | None:
    result = await db.execute(
        select(Shipment).where(Shipment.id == shipment_id).options(*_LOAD_OPTIONS)
    )
    return result.scalar_one_or_none()


async def list_shipments(db: AsyncSession) -> list[Shipment]:
    result = await db.execute(
        select(Shipment).options(*_LOAD_OPTIONS).order_by(Shipment.created_at.desc())
    )
    return list(result.scalars().all())


@dataclass
class ShipmentBoard:
    columns: dict[ShipmentStage, list[Shipment]]


async def get_board(db: AsyncSession) -> ShipmentBoard:
    shipments = await list_shipments(db)
    columns: dict[ShipmentStage, list[Shipment]] = {stage: [] for stage in STAGE_ORDER}
    for shipment in shipments:
        columns[shipment.stage].append(shipment)
    return ShipmentBoard(columns=columns)
