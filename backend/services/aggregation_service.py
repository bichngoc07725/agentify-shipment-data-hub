from datetime import date, datetime, timezone

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Container, ContainerFact

AGGREGATE_FIELDS = {
    "booking_no": "booking_no",
    "bl_no": "bl_no",
    "po_no": "po_no",
    "do_no": "do_no",
    "seal_no": "seal_no",
    "vessel": "vessel",
    "voyage": "voyage",
    "pol": "pol",
    "pod": "pod",
    "etd": "etd",
    "eta": "eta",
    "ata": "ata",
    "free_time_days": "free_time_days",
    "status_text": "status_text",
}

DATE_FIELDS = {"etd", "eta", "ata"}
INTEGER_FIELDS = {"free_time_days"}


def normalize_container_no(value: str) -> str:
    return value.replace(" ", "").replace("-", "").upper().strip()


def normalize_date_value(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def normalize_integer_value(value: str) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


async def get_or_create_container(
    db: AsyncSession, container_no: str, source_sent_at: datetime
) -> Container:
    normalized = normalize_container_no(container_no)
    result = await db.execute(
        select(Container).where(Container.container_no == normalized)
    )
    container = result.scalar_one_or_none()
    if container:
        if source_sent_at < container.first_seen_at:
            container.first_seen_at = source_sent_at
        if source_sent_at > container.last_seen_at:
            container.last_seen_at = source_sent_at
        return container

    container = Container(
        container_no=normalized,
        first_seen_at=source_sent_at,
        last_seen_at=source_sent_at,
    )
    db.add(container)
    await db.flush()
    return container


async def refresh_container_summary(db: AsyncSession, container_id) -> Container | None:
    result = await db.execute(select(Container).where(Container.id == container_id))
    container = result.scalar_one_or_none()
    if not container:
        return None

    for column_name in AGGREGATE_FIELDS.values():
        setattr(container, column_name, None)

    for field_name, column_name in AGGREGATE_FIELDS.items():
        fact_result = await db.execute(
            select(ContainerFact)
            .where(
                and_(
                    ContainerFact.container_id == container_id,
                    ContainerFact.field_name == field_name,
                )
            )
            .order_by(
                ContainerFact.source_sent_at.desc().nullslast(),
                ContainerFact.created_at.desc(),
            )
            .limit(1)
        )
        fact = fact_result.scalar_one_or_none()
        if not fact:
            continue

        value = fact.normalized_value or fact.field_value
        if field_name in DATE_FIELDS:
            setattr(container, column_name, normalize_date_value(value))
        elif field_name in INTEGER_FIELDS:
            setattr(container, column_name, normalize_integer_value(value))
        else:
            setattr(container, column_name, value)

    counts_result = await db.execute(
        select(
            func.count(func.distinct(ContainerFact.email_id)),
            func.count(func.distinct(ContainerFact.attachment_id)),
        ).where(ContainerFact.container_id == container_id)
    )
    email_count, attachment_count = counts_result.one()
    container.source_count = email_count or 0
    container.attachment_count = attachment_count or 0
    container.updated_at = datetime.now(timezone.utc)

    latest_sent_at_result = await db.execute(
        select(func.max(ContainerFact.source_sent_at)).where(
            ContainerFact.container_id == container_id
        )
    )
    latest_sent_at = latest_sent_at_result.scalar_one_or_none()
    if latest_sent_at:
        container.last_seen_at = latest_sent_at

    return container
