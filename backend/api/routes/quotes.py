from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps.permissions import CurrentUser, require_permission
from api.models import (
    QuoteChargeResponse,
    QuoteCreateRequest,
    QuoteListResponse,
    QuoteResponse,
    QuoteUpdateRequest,
)
from db.database import get_db
from db.models import Quote
from services.container_service import get_container_by_no
from services.quote_service import (
    create_quote,
    delete_quote,
    get_quote,
    list_quotes,
    list_quotes_for_container,
    total_amount,
    update_quote,
)

router = APIRouter(prefix="/api/v1", tags=["quotes"])


def _to_response(quote: Quote) -> QuoteResponse:
    return QuoteResponse(
        id=quote.id,
        quote_no=quote.quote_no,
        customer_name=quote.customer_name,
        status=quote.status.value,
        pol=quote.pol,
        pod=quote.pod,
        commodity=quote.commodity,
        is_dangerous=quote.is_dangerous,
        is_reefer=quote.is_reefer,
        container_type=quote.container_type,
        container_qty=quote.container_qty,
        gross_weight_kg=quote.gross_weight_kg,
        cargo_ready_date=quote.cargo_ready_date,
        incoterm=quote.incoterm,
        payment_term=quote.payment_term,
        transit_time=quote.transit_time,
        valid_until=quote.valid_until,
        note=quote.note,
        currency=quote.currency,
        created_by=quote.created_by,
        container_id=quote.container_id,
        container_no=quote.container.container_no if quote.container else None,
        charges=[
            QuoteChargeResponse(
                id=charge.id,
                charge_group=charge.charge_group.value,
                charge_code=charge.charge_code,
                description=charge.description,
                unit_price=charge.unit_price,
                currency=charge.currency,
                quantity=charge.quantity,
                amount=charge.amount,
            )
            for charge in quote.charges
        ],
        total_amount=total_amount(quote),
        created_at=quote.created_at,
        updated_at=quote.updated_at,
    )


@router.post("/quotes", response_model=QuoteResponse)
async def create_quote_endpoint(
    payload: QuoteCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission("quote", "create")),
) -> QuoteResponse:
    try:
        quote = await create_quote(db, payload, UUID(current_user.user_id))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _to_response(quote)


@router.get("/quotes", response_model=QuoteListResponse)
async def list_quotes_endpoint(
    customer_name: str | None = Query(default=None),
    status: str | None = Query(default=None),
    container_no: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_permission("quote", "view")),
) -> QuoteListResponse:
    quotes, total = await list_quotes(
        db,
        customer_name=customer_name,
        status=status,
        container_no=container_no,
        page=page,
        page_size=page_size,
    )
    return QuoteListResponse(items=[_to_response(quote) for quote in quotes], total=total)


@router.get("/quotes/{quote_id}", response_model=QuoteResponse)
async def get_quote_endpoint(
    quote_id: UUID,
    db: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_permission("quote", "view")),
) -> QuoteResponse:
    quote = await get_quote(db, quote_id)
    if quote is None:
        raise HTTPException(status_code=404, detail="Quote not found")
    return _to_response(quote)


@router.put("/quotes/{quote_id}", response_model=QuoteResponse)
async def update_quote_endpoint(
    quote_id: UUID,
    payload: QuoteUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_permission("quote", "edit")),
) -> QuoteResponse:
    quote = await get_quote(db, quote_id)
    if quote is None:
        raise HTTPException(status_code=404, detail="Quote not found")
    try:
        updated = await update_quote(db, quote, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _to_response(updated)


@router.delete("/quotes/{quote_id}", status_code=204)
async def delete_quote_endpoint(
    quote_id: UUID,
    db: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_permission("quote", "delete")),
) -> None:
    quote = await get_quote(db, quote_id)
    if quote is None:
        raise HTTPException(status_code=404, detail="Quote not found")
    await delete_quote(db, quote)


@router.get("/containers/{container_no}/quotes", response_model=QuoteListResponse)
async def get_container_quotes_endpoint(
    container_no: str,
    db: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_permission("quote", "view")),
) -> QuoteListResponse:
    container = await get_container_by_no(db, container_no)
    if container is None:
        raise HTTPException(status_code=404, detail="Container not found")
    quotes = await list_quotes_for_container(db, container.id)
    return QuoteListResponse(
        items=[_to_response(quote) for quote in quotes], total=len(quotes)
    )
