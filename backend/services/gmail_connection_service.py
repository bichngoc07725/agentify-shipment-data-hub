from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import GmailConnectionUpsertRequest
from db.models import GmailConnection
from gmail_service.auth import revoke_token


async def upsert_gmail_connection(
    db: AsyncSession, payload: GmailConnectionUpsertRequest
) -> GmailConnection:
    result = await db.execute(
        select(GmailConnection).where(
            GmailConnection.account_email == payload.account_email
        )
    )
    connection = result.scalar_one_or_none()
    if connection is None:
        connection = GmailConnection(
            account_email=payload.account_email,
            display_name=payload.display_name,
            google_account_id=payload.google_account_id,
            encrypted_refresh_token=payload.encrypted_refresh_token,
            access_scope=payload.access_scope,
            status=payload.status,
        )
        db.add(connection)
        await db.flush()
        return connection

    connection.display_name = payload.display_name
    connection.google_account_id = payload.google_account_id
    connection.encrypted_refresh_token = payload.encrypted_refresh_token
    connection.access_scope = payload.access_scope
    connection.status = payload.status
    await db.flush()
    await db.refresh(connection)
    return connection


async def list_gmail_connections(db: AsyncSession) -> list[GmailConnection]:
    result = await db.execute(
        select(GmailConnection).order_by(GmailConnection.created_at.desc())
    )
    return list(result.scalars().all())


async def get_gmail_connection(
    db: AsyncSession, connection_id
) -> GmailConnection | None:
    return await db.get(GmailConnection, connection_id)


async def disconnect_gmail_connection(
    db: AsyncSession, connection_id
) -> GmailConnection | None:
    """Log the mailbox out: revoke the refresh token at Google and forget our
    local copy, so a future "Connect Gmail" for this or a different account
    starts from a clean slate rather than silently reusing stale credentials.
    """
    connection = await db.get(GmailConnection, connection_id)
    if connection is None:
        return None

    if connection.encrypted_refresh_token:
        revoke_token(connection.encrypted_refresh_token)

    connection.status = "disconnected"
    connection.encrypted_refresh_token = None
    await db.flush()
    await db.refresh(connection)
    return connection
