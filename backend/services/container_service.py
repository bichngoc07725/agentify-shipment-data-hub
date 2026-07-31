from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models import Attachment, Container, ContainerFact, Email
from services.aggregation_service import refresh_container_summary


async def list_containers(
    db: AsyncSession, q: str | None, page: int, page_size: int
) -> tuple[list[Container], int]:
    stmt = select(Container).options(selectinload(Container.shipment))
    count_stmt = select(func.count(Container.id))
    if q:
        search = f"%{q.strip()}%"
        filters = or_(
            Container.container_no.ilike(search),
            Container.booking_no.ilike(search),
            Container.bl_no.ilike(search),
            Container.po_no.ilike(search),
        )
        stmt = stmt.where(filters)
        count_stmt = count_stmt.where(filters)

    stmt = (
        stmt.order_by(
            Container.updated_at.desc().nullslast(), Container.created_at.desc()
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    total_result = await db.execute(count_stmt)
    return list(result.scalars().all()), total_result.scalar_one()


async def get_container_count(db: AsyncSession) -> int:
    result = await db.execute(select(func.count(Container.id)))
    return result.scalar_one()


async def get_recent_containers(db: AsyncSession, limit: int = 6) -> list[Container]:
    result = await db.execute(
        select(Container)
        .order_by(Container.updated_at.desc().nullslast(), Container.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_container_by_no(db: AsyncSession, container_no: str) -> Container | None:
    result = await db.execute(
        select(Container)
        .where(Container.container_no == container_no.upper())
        .options(selectinload(Container.shipment))
    )
    return result.scalar_one_or_none()


async def get_container_related_emails(
    db: AsyncSession, container_id: UUID
) -> list[Email]:
    result = await db.execute(
        select(Email)
        .join(ContainerFact, ContainerFact.email_id == Email.id)
        .where(ContainerFact.container_id == container_id)
        .group_by(Email.id)
        .order_by(Email.sent_at.desc())
    )
    return list(result.scalars().all())


async def get_container_related_attachments(
    db: AsyncSession, container_id: UUID
) -> list[Attachment]:
    result = await db.execute(
        select(Attachment)
        .join(ContainerFact, ContainerFact.attachment_id == Attachment.id)
        .where(
            and_(
                ContainerFact.container_id == container_id,
                ContainerFact.attachment_id.is_not(None),
            )
        )
        .group_by(Attachment.id)
        .order_by(Attachment.created_at.desc())
    )
    return list(result.scalars().all())


async def get_container_facts(db: AsyncSession, container_id: UUID) -> list[ContainerFact]:
    result = await db.execute(
        select(ContainerFact)
        .where(ContainerFact.container_id == container_id)
        .order_by(ContainerFact.source_sent_at.desc(), ContainerFact.created_at.desc())
    )
    return list(result.scalars().all())


async def get_container_fact_by_id(
    db: AsyncSession, container_id: UUID, fact_id: UUID
) -> ContainerFact | None:
    result = await db.execute(
        select(ContainerFact).where(
            and_(ContainerFact.id == fact_id, ContainerFact.container_id == container_id)
        )
    )
    return result.scalar_one_or_none()


async def update_container_fact(
    db: AsyncSession, fact: ContainerFact, field_value: str, edited_by_username: str
) -> ContainerFact:
    """Overwrite a fact's value with a manual correction.

    Kept as an edit to the existing row (not a new fact) so the field's
    history stays a single timeline; `source_sent_at` is bumped to now so
    `refresh_container_summary` picks this as the latest value for the field.
    """

    fact.field_value = field_value
    fact.normalized_value = field_value
    fact.source_type = "manual_edit"
    fact.source_label = f"Sửa tay bởi {edited_by_username}"
    fact.source_sent_at = datetime.now(UTC)
    await db.flush()
    await refresh_container_summary(db, fact.container_id)
    await db.refresh(fact)
    return fact


async def get_email_detail(db: AsyncSession, email_id: UUID):
    email = await db.get(Email, email_id)
    if email is None:
        return None

    attachments_result = await db.execute(
        select(Attachment)
        .where(Attachment.email_id == email_id)
        .order_by(Attachment.created_at.desc())
    )
    facts_result = await db.execute(
        select(ContainerFact)
        .where(ContainerFact.email_id == email_id)
        .order_by(ContainerFact.created_at.asc())
    )
    linked_containers_result = await db.execute(
        select(Container.container_no)
        .join(ContainerFact, ContainerFact.container_id == Container.id)
        .where(ContainerFact.email_id == email_id)
        .group_by(Container.container_no)
        .order_by(Container.container_no.asc())
    )
    return {
        "email": email,
        "attachments": list(attachments_result.scalars().all()),
        "facts": list(facts_result.scalars().all()),
        "linked_containers": list(linked_containers_result.scalars().all()),
    }


async def list_emails(
    db: AsyncSession,
    gmail_connection_id: UUID | None,
    page: int,
    page_size: int,
) -> tuple[list[dict], int]:
    stmt = select(Email)
    count_stmt = select(func.count(Email.id))

    if gmail_connection_id is not None:
        stmt = stmt.where(Email.gmail_connection_id == gmail_connection_id)
        count_stmt = count_stmt.where(Email.gmail_connection_id == gmail_connection_id)

    stmt = (
        stmt.order_by(Email.sent_at.desc(), Email.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    total_result = await db.execute(count_stmt)
    emails = list(result.scalars().all())

    items: list[dict] = []
    for email in emails:
        attachments_count_result = await db.execute(
            select(func.count(Attachment.id)).where(Attachment.email_id == email.id)
        )
        facts_count_result = await db.execute(
            select(func.count(ContainerFact.id)).where(ContainerFact.email_id == email.id)
        )
        linked_containers_result = await db.execute(
            select(Container.container_no)
            .join(ContainerFact, ContainerFact.container_id == Container.id)
            .where(ContainerFact.email_id == email.id)
            .group_by(Container.container_no)
            .order_by(Container.container_no.asc())
        )

        items.append(
            {
                "email": email,
                "attachment_count": attachments_count_result.scalar_one(),
                "fact_count": facts_count_result.scalar_one(),
                "linked_containers": list(linked_containers_result.scalars().all()),
            }
        )

    return items, total_result.scalar_one()
