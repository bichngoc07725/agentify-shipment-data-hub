from datetime import UTC, datetime
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from api.models import ProcessedEmailIngestRequest
from gmail_service.models import ExtractedRecord, GmailEmailPayload, Identifiers, Route, Source
from services.gmail_ingestion_service import (
    build_processed_email_from_gmail_payload,
    execute_sync_job,
)


class ExecuteSyncJobTest(IsolatedAsyncioTestCase):
    async def test_execute_sync_job_updates_job_and_connection_from_processed_emails(
        self,
    ) -> None:
        sent_at = datetime(2026, 6, 9, 3, 45, tzinfo=UTC)
        connection = SimpleNamespace(
            id=uuid4(),
            account_email="demo-logistics@agentify.vn",
            encrypted_refresh_token="refresh-token",
            sync_cursor=None,
            last_synced_at=None,
        )
        job = SimpleNamespace(
            id=uuid4(),
            gmail_connection_id=connection.id,
            query="label:inbox newer_than:7d",
            max_results=25,
            status="queued",
            emails_fetched=0,
            attachments_found=0,
            pdf_text_extracted=0,
            containers_upserted=0,
            error_message=None,
            started_at=None,
            completed_at=None,
        )
        processed_email = ProcessedEmailIngestRequest(
            gmail_connection_id=connection.id,
            sync_job_id=job.id,
            gmail_message_id="msg-001",
            gmail_thread_id="thread-001",
            subject="Arrival Notice - MSCU1234567",
            from_email="ops@carrier.com",
            to_emails=["cs@agentify.vn"],
            sent_at=sent_at,
            has_pdf_attachments=True,
        )

        result = await execute_sync_job(
            db=AsyncMock(),
            connection=connection,
            job=job,
            create_service=Mock(return_value=object()),
            resolve_message_ids=Mock(return_value=(["msg-001"], "history-002")),
            filter_message_ids=AsyncMock(return_value=["msg-001"]),
            fetch_email=Mock(return_value={"gmail_message_id": "msg-001"}),
            process_email=Mock(return_value=processed_email),
            ingest_email=AsyncMock(
                return_value={
                    "email_id": uuid4(),
                    "created": True,
                    "attachment_count": 1,
                    "fact_count": 5,
                    "linked_containers": ["MSCU1234567"],
                }
            ),
        )

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.emails_fetched, 1)
        self.assertEqual(result.attachments_found, 1)
        self.assertEqual(result.pdf_text_extracted, 1)
        self.assertEqual(result.containers_upserted, 1)
        self.assertIsNotNone(result.started_at)
        self.assertIsNotNone(result.completed_at)
        self.assertEqual(connection.sync_cursor, "history-002")
        self.assertEqual(connection.last_synced_at, result.completed_at)

    async def test_execute_sync_job_refreshes_job_before_returning(self) -> None:
        sent_at = datetime(2026, 6, 9, 3, 45, tzinfo=UTC)
        connection = SimpleNamespace(
            id=uuid4(),
            account_email="demo-logistics@agentify.vn",
            encrypted_refresh_token="refresh-token",
            sync_cursor=None,
            last_synced_at=None,
        )
        job = SimpleNamespace(
            id=uuid4(),
            gmail_connection_id=connection.id,
            query="label:inbox newer_than:7d",
            max_results=25,
            status="queued",
            emails_fetched=0,
            attachments_found=0,
            pdf_text_extracted=0,
            containers_upserted=0,
            error_message=None,
            started_at=None,
            completed_at=None,
        )
        processed_email = ProcessedEmailIngestRequest(
            gmail_connection_id=connection.id,
            sync_job_id=job.id,
            gmail_message_id="msg-001",
            gmail_thread_id="thread-001",
            subject="Arrival Notice - MSCU1234567",
            from_email="ops@carrier.com",
            to_emails=["cs@agentify.vn"],
            sent_at=sent_at,
            has_pdf_attachments=True,
        )
        db = AsyncMock()

        await execute_sync_job(
            db=db,
            connection=connection,
            job=job,
            create_service=Mock(return_value=object()),
            resolve_message_ids=Mock(return_value=(["msg-001"], "history-002")),
            filter_message_ids=AsyncMock(return_value=["msg-001"]),
            fetch_email=Mock(return_value={"gmail_message_id": "msg-001"}),
            process_email=Mock(return_value=processed_email),
            ingest_email=AsyncMock(
                return_value={
                    "email_id": uuid4(),
                    "created": True,
                    "attachment_count": 1,
                    "fact_count": 5,
                    "linked_containers": ["MSCU1234567"],
                }
            ),
        )

        db.refresh.assert_awaited()

    async def test_execute_sync_job_rolls_back_before_marking_failed(self) -> None:
        connection = SimpleNamespace(
            id=uuid4(),
            account_email="demo-logistics@agentify.vn",
            encrypted_refresh_token="refresh-token",
            sync_cursor=None,
            last_synced_at=None,
        )
        job = SimpleNamespace(
            id=uuid4(),
            gmail_connection_id=connection.id,
            query="has:attachment newer_than:7d",
            max_results=48,
            status="queued",
            emails_fetched=0,
            attachments_found=0,
            pdf_text_extracted=0,
            containers_upserted=0,
            error_message=None,
            started_at=None,
            completed_at=None,
        )
        db = AsyncMock()

        result = await execute_sync_job(
            db=db,
            connection=connection,
            job=job,
            create_service=Mock(return_value=object()),
            resolve_message_ids=Mock(return_value=(["msg-001"], "history-002")),
            filter_message_ids=AsyncMock(return_value=["msg-001"]),
            fetch_email=Mock(return_value={"gmail_message_id": "msg-001"}),
            process_email=Mock(return_value=Mock(attachments=[])),
            ingest_email=AsyncMock(side_effect=ValueError("value too long for type character varying(255)")),
        )

        db.rollback.assert_awaited_once()
        self.assertEqual(result.status, "failed")
        self.assertEqual(
            result.error_message,
            "value too long for type character varying(255)",
        )
        db.refresh.assert_awaited()

    async def _run_failing_sync(self, error: Exception, *, refresh_token="refresh-token"):
        connection = SimpleNamespace(
            id=uuid4(),
            account_email="demo-logistics@agentify.vn",
            encrypted_refresh_token=refresh_token,
            sync_cursor=None,
            last_synced_at=None,
            status="connected",
        )
        job = SimpleNamespace(
            id=uuid4(),
            gmail_connection_id=connection.id,
            query="subject:AGENTIFY-DEMO",
            max_results=48,
            status="queued",
            emails_fetched=0,
            attachments_found=0,
            pdf_text_extracted=0,
            containers_upserted=0,
            error_message=None,
            started_at=None,
            completed_at=None,
        )
        result = await execute_sync_job(
            db=AsyncMock(),
            connection=connection,
            job=job,
            create_service=Mock(return_value=object()),
            resolve_message_ids=Mock(side_effect=error),
            filter_message_ids=AsyncMock(return_value=["msg-001"]),
            fetch_email=Mock(return_value={"gmail_message_id": "msg-001"}),
            process_email=Mock(return_value=Mock(attachments=[])),
            ingest_email=AsyncMock(),
        )
        return connection, result

    async def test_a_revoked_token_marks_the_connection_expired(self) -> None:
        # Kết nối chết mà vẫn báo "connected" là hệ thống nói sai về chính nó:
        # màn hình Setup xanh lè trong khi không thư nào về được nữa.
        connection, result = await self._run_failing_sync(
            RuntimeError("('invalid_grant: Token has been expired or revoked.', {})")
        )

        self.assertEqual(result.status, "failed")
        self.assertEqual(connection.status, "expired")

    async def test_a_transient_error_leaves_the_connection_alone(self) -> None:
        # Lỗi mạng nhất thời thì thử lại là xong — bắt người dùng đi cấp quyền
        # lại vì một cú timeout là làm phiền vô cớ.
        connection, result = await self._run_failing_sync(
            TimeoutError("connection timed out")
        )

        self.assertEqual(result.status, "failed")
        self.assertEqual(connection.status, "connected")

    async def test_a_missing_refresh_token_marks_the_connection_expired(self) -> None:
        connection, result = await self._run_failing_sync(
            RuntimeError("unused"), refresh_token=None
        )

        self.assertEqual(result.status, "failed")
        self.assertEqual(connection.status, "expired")

    async def test_execute_sync_job_skips_already_synced_messages(self) -> None:
        sent_at = datetime(2026, 6, 9, 3, 45, tzinfo=UTC)
        connection = SimpleNamespace(
            id=uuid4(),
            account_email="demo-logistics@agentify.vn",
            encrypted_refresh_token="refresh-token",
            sync_cursor="history-001",
            last_synced_at=None,
        )
        job = SimpleNamespace(
            id=uuid4(),
            gmail_connection_id=connection.id,
            query="label:inbox newer_than:7d",
            max_results=25,
            status="queued",
            emails_fetched=0,
            attachments_found=0,
            pdf_text_extracted=0,
            containers_upserted=0,
            error_message=None,
            started_at=None,
            completed_at=None,
        )
        processed_email = ProcessedEmailIngestRequest(
            gmail_connection_id=connection.id,
            sync_job_id=job.id,
            gmail_message_id="msg-002",
            gmail_thread_id="thread-002",
            subject="Arrival Notice - MSCU1234567",
            from_email="ops@carrier.com",
            to_emails=["cs@agentify.vn"],
            sent_at=sent_at,
            has_pdf_attachments=True,
        )
        gmail_api = object()
        fetch_email = Mock(return_value={"gmail_message_id": "msg-002"})

        result = await execute_sync_job(
            db=AsyncMock(),
            connection=connection,
            job=job,
            create_service=Mock(return_value=gmail_api),
            resolve_message_ids=Mock(return_value=(["msg-001", "msg-002"], "history-003")),
            filter_message_ids=AsyncMock(return_value=["msg-002"]),
            fetch_email=fetch_email,
            process_email=Mock(return_value=processed_email),
            ingest_email=AsyncMock(
                return_value={
                    "email_id": uuid4(),
                    "created": True,
                    "attachment_count": 1,
                    "fact_count": 5,
                    "linked_containers": ["MSCU1234567"],
                }
            ),
        )

        fetch_email.assert_called_once_with(gmail_api, "msg-002")
        self.assertEqual(result.emails_fetched, 1)


class BuildProcessedEmailPayloadTest(IsolatedAsyncioTestCase):
    async def test_build_processed_email_from_gmail_payload_extracts_from_body_text(
        self,
    ) -> None:
        sent_at = datetime(2026, 6, 10, 9, 12, tzinfo=UTC)
        connection_id = uuid4()
        sync_job_id = uuid4()
        email = GmailEmailPayload(
            gmail_message_id="msg-003",
            gmail_thread_id="thread-003",
            subject="Delivery update",
            from_email="ops@carrier.com",
            to_emails=["cs@agentify.vn"],
            sent_at=sent_at,
            snippet="Final delivery completed.",
            body_text=(
                "Container no: TCKU1234567\n"
                "Booking number: HLCSG112233\n"
                "Bill of lading number: OOLU99887766\n"
                "ETA: 2026-06-21\n"
            ),
        )
        body_record = ExtractedRecord(
            source=Source(
                message_id="msg-003",
                sender="ops@carrier.com",
                subject="Delivery update",
                received_at=sent_at.isoformat(),
                attachment_name="email_body",
            ),
            doc_type="other",
            doc_type_confidence=0.81,
            identifiers=Identifiers(
                container_no=["TCKU1234567"],
                booking_no="HLCSG112233",
                bl_no="OOLU99887766",
            ),
            route=Route(eta="2026-06-21"),
            extraction_status="ok",
        )

        with patch(
            "services.gmail_ingestion_service.process_text_content",
            return_value=body_record,
        ) as process_text:
            payload = build_processed_email_from_gmail_payload(
                connection_id,
                sync_job_id,
                email,
            )

        process_text.assert_called_once()
        facts = {
            (fact.field_name, fact.normalized_value, fact.container_no, fact.source_type)
            for fact in payload.extracted_facts
        }
        self.assertIn(
            ("container_no", "TCKU1234567", "TCKU1234567", "email_body"),
            facts,
        )
        self.assertIn(
            ("booking_no", "HLCSG112233", "TCKU1234567", "email_body"),
            facts,
        )
        self.assertIn(
            ("bl_no", "OOLU99887766", "TCKU1234567", "email_body"),
            facts,
        )
        self.assertIn(
            ("eta", "2026-06-21", "TCKU1234567", "email_body"),
            facts,
        )
