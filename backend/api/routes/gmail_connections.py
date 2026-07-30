import base64
import json
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import (
    GmailOAuthStartResponse,
    GmailConnectionResponse,
    GmailConnectionUpsertRequest,
)
from db.database import get_db
from gmail_service.auth import build_authorization_url, exchange_code_for_tokens
from gmail_service.config import GMAIL_FRONTEND_RETURN_URL
from services.gmail_connection_service import (
    disconnect_gmail_connection,
    list_gmail_connections,
    upsert_gmail_connection,
)
from services.gmail_ingestion_service import build_gmail_oauth_payload

router = APIRouter(prefix="/api/v1/gmail-connections", tags=["gmail-connections"])


@router.get("", response_model=list[GmailConnectionResponse])
async def get_gmail_connections(
    db: AsyncSession = Depends(get_db),
) -> list[GmailConnectionResponse]:
    return await list_gmail_connections(db)


@router.post("", response_model=GmailConnectionResponse)
async def create_or_update_gmail_connection(
    payload: GmailConnectionUpsertRequest,
    db: AsyncSession = Depends(get_db),
) -> GmailConnectionResponse:
    return await upsert_gmail_connection(db, payload)


@router.post("/{connection_id}/disconnect", response_model=GmailConnectionResponse)
async def disconnect_gmail_connection_endpoint(
    connection_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> GmailConnectionResponse:
    connection = await disconnect_gmail_connection(db, connection_id)
    if connection is None:
        raise HTTPException(status_code=404, detail="Gmail connection not found")
    return connection


@router.get("/oauth/start", response_model=GmailOAuthStartResponse)
async def start_gmail_oauth(
    redirect_to: str | None = Query(default=None),
) -> GmailOAuthStartResponse:
    state = _encode_state({"redirect_to": redirect_to or GMAIL_FRONTEND_RETURN_URL})
    return GmailOAuthStartResponse(authorization_url=build_authorization_url(state))


@router.get("/oauth/callback")
async def gmail_oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    redirect_to = GMAIL_FRONTEND_RETURN_URL
    try:
        state_payload = _decode_state(state)
        redirect_to = state_payload.get("redirect_to") or redirect_to
        tokens = exchange_code_for_tokens(code, state)
        gmail_payload = build_gmail_oauth_payload(
            tokens["refresh_token"], scopes=tokens.get("scopes")
        )
        await upsert_gmail_connection(db, GmailConnectionUpsertRequest(**gmail_payload))
        return RedirectResponse(url=f"{redirect_to}?gmail_oauth=success")
    except Exception as exc:
        error_query = urlencode({"gmail_oauth": "error", "message": str(exc)})
        return RedirectResponse(url=f"{redirect_to}?{error_query}")


def _encode_state(payload: dict[str, str]) -> str:
    raw = json.dumps(payload).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("utf-8")


def _decode_state(state: str) -> dict[str, str]:
    try:
        raw = base64.urlsafe_b64decode(state.encode("utf-8"))
        return json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid Gmail OAuth state") from exc
