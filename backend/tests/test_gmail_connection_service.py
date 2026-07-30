from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from services import gmail_connection_service
from services.gmail_connection_service import disconnect_gmail_connection


class DisconnectGmailConnectionTest(IsolatedAsyncioTestCase):
    async def test_disconnect_revokes_the_token_and_clears_it_locally(self) -> None:
        connection = SimpleNamespace(
            id=uuid4(),
            account_email="ops@agentify.vn",
            status="connected",
            encrypted_refresh_token="refresh-token-abc",
        )
        db = AsyncMock()
        db.get.return_value = connection

        with patch.object(gmail_connection_service, "revoke_token") as mock_revoke:
            result = await disconnect_gmail_connection(db, connection.id)

        mock_revoke.assert_called_once_with("refresh-token-abc")
        self.assertIs(result, connection)
        self.assertEqual(result.status, "disconnected")
        self.assertIsNone(result.encrypted_refresh_token)
        db.flush.assert_awaited_once()
        # Without this, FastAPI's response serialization can hit a
        # MissingGreenlet error reading server-generated columns like
        # `updated_at`, which only refresh() (not flush()) resolves.
        db.refresh.assert_awaited_once_with(connection)

    async def test_disconnect_returns_none_for_an_unknown_connection(self) -> None:
        db = AsyncMock()
        db.get.return_value = None

        result = await disconnect_gmail_connection(db, uuid4())

        self.assertIsNone(result)

    async def test_disconnect_skips_revocation_when_no_token_is_stored(self) -> None:
        # Already disconnected once before — nothing to revoke a second time.
        connection = SimpleNamespace(
            id=uuid4(),
            account_email="ops@agentify.vn",
            status="disconnected",
            encrypted_refresh_token=None,
        )
        db = AsyncMock()
        db.get.return_value = connection

        with patch.object(gmail_connection_service, "revoke_token") as mock_revoke:
            await disconnect_gmail_connection(db, connection.id)

        mock_revoke.assert_not_called()


if __name__ == "__main__":
    import unittest

    unittest.main()
