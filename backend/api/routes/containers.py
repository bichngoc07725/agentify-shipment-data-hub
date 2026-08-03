from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps.permissions import CurrentUser, require_permission
from api.routes.attachments import attachment_file_url
from api.models import (
    ContainerDetailResponse,
    ContainerFactsListResponse,
    ContainerFactResponse,
    ContainerListItem,
    ContainerListResponse,
    ContainerShipmentSummary,
    EditContainerFactRequest,
    RelatedAttachmentSummary,
    RelatedEmailSummary,
)
from config.permissions import ROLE_FIELD_GROUP, field_group_for
from db.database import get_db
from services.audit_service import record_audit
from services.container_service import (
    get_container_by_no,
    get_container_facts,
    get_container_fact_by_id,
    get_container_related_attachments,
    get_container_related_emails,
    list_containers,
    update_container_fact,
)
from services.shipment_service import is_sla_breached

router = APIRouter(prefix="/api/v1/containers", tags=["containers"])


def _to_container_item(container) -> ContainerListItem:
    shipment = container.shipment
    return ContainerListItem(
        id=container.id,
        container_no=container.container_no,
        booking_no=container.booking_no,
        bl_no=container.bl_no,
        po_no=container.po_no,
        do_no=container.do_no,
        vessel=container.vessel,
        voyage=container.voyage,
        pol=container.pol,
        pod=container.pod,
        etd=container.etd,
        eta=container.eta,
        ata=container.ata,
        free_time_days=container.free_time_days,
        status_text=container.status_text,
        source_count=container.source_count,
        attachment_count=container.attachment_count,
        updated_at=container.updated_at,
        shipment=(
            ContainerShipmentSummary(
                id=shipment.id,
                stage=shipment.stage.value,
                sla_breached=is_sla_breached(shipment),
                sla_due_at=shipment.sla_due_at,
            )
            if shipment is not None
            else None
        ),
    )


@router.get("", response_model=ContainerListResponse)
async def list_containers_endpoint(
    q: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(
        require_permission("container_facts", "view")
    ),
) -> ContainerListResponse:
    items, total = await list_containers(db, q=q, page=page, page_size=page_size)
    return ContainerListResponse(
        items=[_to_container_item(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{container_no}", response_model=ContainerDetailResponse)
async def get_container_detail_endpoint(
    container_no: str,
    db: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(
        require_permission("container_facts", "view")
    ),
) -> ContainerDetailResponse:
    container = await get_container_by_no(db, container_no)
    if container is None:
        raise HTTPException(status_code=404, detail="Container not found")

    emails = await get_container_related_emails(db, container.id)
    attachments = await get_container_related_attachments(db, container.id)
    return ContainerDetailResponse(
        container=_to_container_item(container),
        related_emails=[
            RelatedEmailSummary(
                id=email.id,
                subject=email.subject,
                from_email=email.from_email,
                sent_at=email.sent_at,
                channel=email.channel,
            )
            for email in emails
        ],
        related_attachments=[
            RelatedAttachmentSummary(
                id=attachment.id,
                filename=attachment.filename,
                email_id=attachment.email_id,
                document_type=attachment.document_type,
                file_url=attachment_file_url(attachment),
            )
            for attachment in attachments
        ],
    )


def _to_fact_response(fact) -> ContainerFactResponse:
    return ContainerFactResponse(
        id=fact.id,
        field_name=fact.field_name,
        field_value=fact.field_value,
        normalized_value=fact.normalized_value,
        source_type=fact.source_type,
        source_label=fact.source_label,
        document_type=fact.document_type,
        confidence=fact.confidence,
        source_sent_at=fact.source_sent_at,
        email_id=fact.email_id,
        attachment_id=fact.attachment_id,
    )


@router.get("/{container_no}/facts", response_model=ContainerFactsListResponse)
async def get_container_facts_endpoint(
    container_no: str,
    db: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(
        require_permission("container_facts", "view")
    ),
) -> ContainerFactsListResponse:
    container = await get_container_by_no(db, container_no)
    if container is None:
        raise HTTPException(status_code=404, detail="Container not found")

    facts = await get_container_facts(db, container.id)
    return ContainerFactsListResponse(
        items=[_to_fact_response(fact) for fact in facts]
    )


@router.patch(
    "/{container_no}/facts/{fact_id}", response_model=ContainerFactResponse
)
async def edit_container_fact_endpoint(
    container_no: str,
    fact_id: UUID,
    payload: EditContainerFactRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_permission("container_facts", "edit")
    ),
) -> ContainerFactResponse:
    """Manual correction of a single fact.

    Two permission layers: `require_permission` above is layer 1 (can this
    role edit container_facts *at all*); layer 2 below checks the fact's
    field belongs to *this role's own group* (document/operation/finance) —
    Docs cannot touch an Ops field even though both may edit facts in general.
    """

    container = await get_container_by_no(db, container_no)
    if container is None:
        raise HTTPException(status_code=404, detail="Container not found")

    fact = await get_container_fact_by_id(db, container.id, fact_id)
    if fact is None:
        raise HTTPException(status_code=404, detail="Container fact not found")

    field_group = field_group_for(fact.field_name)
    role_group = ROLE_FIELD_GROUP.get(current_user.role)
    if field_group is None or field_group != role_group:
        raise HTTPException(
            status_code=403,
            detail=(
                f"Role '{current_user.role.value}' cannot edit field "
                f"'{fact.field_name}' (group: {field_group or 'unclassified'})"
            ),
        )

    old_value = fact.field_value
    updated = await update_container_fact(
        db, fact, payload.field_value, current_user.username
    )
    await record_audit(
        db,
        user_id=UUID(current_user.user_id),
        role_used=current_user.role,
        action="edit",
        resource_type="container_fact",
        resource_id=fact.id,
        detail={
            "container_no": container_no.upper(),
            "field_name": fact.field_name,
            "old_value": old_value,
            "new_value": payload.field_value,
        },
    )
    return _to_fact_response(updated)
