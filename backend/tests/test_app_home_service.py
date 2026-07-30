from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock
from uuid import uuid4

from services.app_home_service import build_app_home_payload


class AppHomeServiceTest(IsolatedAsyncioTestCase):
    async def test_builds_home_payload_from_connections_jobs_and_containers(self):
        connection = SimpleNamespace(
            id=uuid4(),
            account_email="demo-logistics@agentify.vn",
            status="connected",
        )
        latest_job = SimpleNamespace(
            completed_at=datetime(2026, 6, 8, 4, 35, tzinfo=UTC)
        )
        recent_container = SimpleNamespace(
            container_no="MSCU1234567",
            booking_no="BKG-88921",
            bl_no="HLCUSHA250601234",
            pod="Hai Phong",
            etd=date(2026, 6, 6),
            status_text="ETA đã điều chỉnh do ùn tắc cảng",
            eta=date(2026, 6, 14),
            source_count=4,
            attachment_count=3,
            updated_at=datetime(2026, 6, 8, 4, 35, tzinfo=UTC),
        )

        payload = await build_app_home_payload(
            db=AsyncMock(),
            list_connections=AsyncMock(return_value=[connection]),
            get_latest_completed_job=AsyncMock(return_value=latest_job),
            list_recent_containers=AsyncMock(return_value=[recent_container]),
            count_containers=AsyncMock(return_value=3),
        )

        self.assertTrue(payload.has_data)
        self.assertEqual(payload.container_count, 3)
        self.assertEqual(
            payload.connected_mailboxes[0].account_email, "demo-logistics@agentify.vn"
        )
        self.assertEqual(payload.recent_containers[0].container_no, "MSCU1234567")
        self.assertEqual(payload.recent_containers[0].booking_no, "BKG-88921")
        self.assertEqual(payload.recent_containers[0].bl_no, "HLCUSHA250601234")
        self.assertEqual(payload.recent_containers[0].pod, "Hai Phong")

    async def test_disconnected_mailboxes_are_not_shown_as_connected(self):
        connected = SimpleNamespace(
            id=uuid4(), account_email="active@agentify.vn", status="connected"
        )
        disconnected = SimpleNamespace(
            id=uuid4(), account_email="old@agentify.vn", status="disconnected"
        )

        payload = await build_app_home_payload(
            db=AsyncMock(),
            list_connections=AsyncMock(return_value=[connected, disconnected]),
            get_latest_completed_job=AsyncMock(return_value=None),
            list_recent_containers=AsyncMock(return_value=[]),
            count_containers=AsyncMock(return_value=0),
        )

        emails = [mailbox.account_email for mailbox in payload.connected_mailboxes]
        self.assertEqual(emails, ["active@agentify.vn"])
