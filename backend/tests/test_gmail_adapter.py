import unittest
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

from api.models import ProcessedEmailIngestRequest
from gmail_service.adapter import (
    BACKEND_ROOT,
    AttachmentExtractionResult,
    GmailAttachmentPayload,
    GmailEmailPayload,
    build_processed_email_request,
)
from gmail_service.models import Cargo, ExtractedRecord, Identifiers, Route, Source


class GmailAdapterTest(unittest.TestCase):
    def test_build_processed_email_request_flattens_gmail_extraction_output(self) -> None:
        gmail_connection_id = uuid4()
        sync_job_id = uuid4()
        sent_at = datetime(2026, 6, 9, 3, 45, tzinfo=UTC)
        email = GmailEmailPayload(
            gmail_message_id="msg-001",
            gmail_thread_id="thread-001",
            subject="Arrival Notice - MSCU1234567",
            from_email="ops@carrier.com",
            to_emails=["cs@agentify.vn"],
            cc_emails=["ops@agentify.vn"],
            sent_at=sent_at,
            snippet="Please find attached arrival notice",
            body_text="Attached is the latest arrival notice for MSCU1234567.",
            body_html="<p>Attached is the latest arrival notice for MSCU1234567.</p>",
            raw_labels=["INBOX"],
            attachments=[
                GmailAttachmentPayload(
                    gmail_attachment_id="att-001",
                    filename="arrival_notice.pdf",
                    mime_type="application/pdf",
                    size_bytes=4096,
                    attachment_bytes=b"%PDF",
                )
            ],
        )
        record = ExtractedRecord(
            source=Source(
                message_id="msg-001",
                sender="ops@carrier.com",
                subject="Arrival Notice - MSCU1234567",
                received_at=sent_at.isoformat(),
                attachment_name="arrival_notice.pdf",
            ),
            doc_type="arrival_notice",
            doc_type_confidence=0.97,
            identifiers=Identifiers(
                container_no=["MSCU1234567"],
                booking_no="BKG-001",
                bl_no="BL-001",
                po_no="PO-001",
                seal_no=["SEAL-01"],
            ),
            route=Route(
                vessel="WAN HAI 517",
                voyage="V12E",
                pol="Shanghai",
                pod="Hai Phong",
                eta="2026-06-12",
                etd="2026-06-10",
            ),
            cargo=Cargo(
                gross_weight_kg=1234.5,
                packages="42 CTNS",
            ),
            extraction_status="ok",
        )

        # Anchor on the same constant the adapter uses, so the returned
        # relative `storage_path` resolves regardless of the pytest cwd
        # (repo root or `backend/`).
        backend_root = BACKEND_ROOT
        storage_root = backend_root / "storage"
        storage_root.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=storage_root) as temp_dir:
            with patch("gmail_service.adapter.ATTACHMENT_STORAGE_DIR", Path(temp_dir)):
                payload = build_processed_email_request(
                    gmail_connection_id=gmail_connection_id,
                    sync_job_id=sync_job_id,
                    email=email,
                    attachment_results=[
                        AttachmentExtractionResult(
                            attachment=email.attachments[0],
                            extracted_text="Container No: MSCU1234567",
                            text_extract_status="extracted",
                            record=record,
                        )
                    ],
                )

                self.assertIsNotNone(payload.attachments[0].storage_path)
                stored_path = backend_root / payload.attachments[0].storage_path
                self.assertTrue(stored_path.is_file())
                self.assertEqual(stored_path.read_bytes(), b"%PDF")

        self.assertIsInstance(payload, ProcessedEmailIngestRequest)
        self.assertEqual(payload.gmail_connection_id, gmail_connection_id)
        self.assertEqual(payload.sync_job_id, sync_job_id)
        self.assertEqual(payload.gmail_message_id, "msg-001")
        self.assertTrue(payload.has_pdf_attachments)
        self.assertEqual(len(payload.attachments), 1)
        self.assertEqual(payload.attachments[0].document_type, "arrival_notice")
        self.assertEqual(payload.attachments[0].extracted_text, "Container No: MSCU1234567")
        self.assertEqual(
            payload.attachments[0].extracted_record["identifiers"]["container_no"],
            ["MSCU1234567"],
        )
        self.assertEqual(
            payload.attachments[0].extracted_record["route"]["pod"],
            "Hai Phong",
        )

        facts = {
            (fact.field_name, fact.normalized_value, fact.container_no)
            for fact in payload.extracted_facts
        }
        self.assertIn(("container_no", "MSCU1234567", "MSCU1234567"), facts)
        self.assertIn(("booking_no", "BKG-001", "MSCU1234567"), facts)
        self.assertIn(("bl_no", "BL-001", "MSCU1234567"), facts)
        self.assertIn(("eta", "2026-06-12", "MSCU1234567"), facts)
        self.assertIn(("status_text", "arrival_notice", "MSCU1234567"), facts)

    def test_build_processed_email_request_extracts_facts_from_email_body_without_pdf(
        self,
    ) -> None:
        gmail_connection_id = uuid4()
        sync_job_id = uuid4()
        sent_at = datetime(2026, 6, 10, 9, 12, tzinfo=UTC)
        email = GmailEmailPayload(
            gmail_message_id="msg-002",
            gmail_thread_id="thread-002",
            subject="Delivered - container MSCU7812456 completed on 2026-06-20",
            from_email="ops@carrier.com",
            to_emails=["cs@agentify.vn"],
            sent_at=sent_at,
            snippet=(
                "Container no: MSCU7812456 Booking no: BKGMYC8821 "
                "B/L no: MAEU260619771"
            ),
            body_text=(
                "Dear team,\n\n"
                "Final delivery has been completed.\n\n"
                "Container no: MSCU7812456\n"
                "Booking no: BKGMYC8821\n"
                "B/L no: MAEU260619771\n"
                "Delivery date: 2026-06-20\n"
                "Delivery point: Shah Alam DC\n"
                "Receiver: Metro Fashion Malaysia\n"
            ),
            raw_labels=["INBOX"],
        )

        payload = build_processed_email_request(
            gmail_connection_id=gmail_connection_id,
            sync_job_id=sync_job_id,
            email=email,
            attachment_results=[],
        )

        self.assertFalse(payload.has_pdf_attachments)
        facts = {
            (fact.field_name, fact.normalized_value, fact.container_no, fact.source_type)
            for fact in payload.extracted_facts
        }
        self.assertIn(
            ("container_no", "MSCU7812456", "MSCU7812456", "email_body"),
            facts,
        )
        self.assertIn(
            ("booking_no", "BKGMYC8821", "MSCU7812456", "email_body"),
            facts,
        )
        self.assertIn(
            ("bl_no", "MAEU260619771", "MSCU7812456", "email_body"),
            facts,
        )
        self.assertIn(
            ("eta", "2026-06-20", "MSCU7812456", "email_body"),
            facts,
        )

    def test_build_processed_email_request_uses_body_text_without_subject_identifiers(
        self,
    ) -> None:
        gmail_connection_id = uuid4()
        sync_job_id = uuid4()
        sent_at = datetime(2026, 6, 10, 9, 12, tzinfo=UTC)
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
            raw_labels=["INBOX"],
        )

        payload = build_processed_email_request(
            gmail_connection_id=gmail_connection_id,
            sync_job_id=sync_job_id,
            email=email,
            attachment_results=[],
        )

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

    def test_image_attachment_gets_image_vision_source_and_is_not_text_pdf(
        self,
    ) -> None:
        gmail_connection_id = uuid4()
        sync_job_id = uuid4()
        sent_at = datetime(2026, 7, 10, 9, 15, tzinfo=UTC)
        email = GmailEmailPayload(
            gmail_message_id="msg-004",
            gmail_thread_id="thread-004",
            subject="To khai Hai quan - MSCU1234567",
            from_email="docs@forwarder-demo.com",
            to_emails=["cs@agentify.vn"],
            sent_at=sent_at,
            snippet="",
            body_text="",
            raw_labels=["INBOX"],
            attachments=[
                GmailAttachmentPayload(
                    gmail_attachment_id="att-pdf-001",
                    filename="invoice.pdf",
                    mime_type="application/pdf",
                    size_bytes=2048,
                    attachment_bytes=b"%PDF",
                ),
                GmailAttachmentPayload(
                    gmail_attachment_id="att-img-001",
                    filename="customs_declaration_photo.jpg",
                    mime_type="image/jpeg",
                    size_bytes=4096,
                    attachment_bytes=b"fake-jpeg-bytes",
                ),
            ],
        )
        pdf_record = ExtractedRecord(
            source=Source(
                message_id="msg-004",
                sender="docs@forwarder-demo.com",
                subject="To khai Hai quan - MSCU1234567",
                received_at=sent_at.isoformat(),
                attachment_name="invoice.pdf",
            ),
            doc_type="invoice",
            doc_type_confidence=0.9,
            identifiers=Identifiers(container_no=["MSCU1234567"]),
            route=Route(),
            extraction_status="ok",
        )
        image_record = ExtractedRecord(
            source=Source(
                message_id="msg-004",
                sender="docs@forwarder-demo.com",
                subject="To khai Hai quan - MSCU1234567",
                received_at=sent_at.isoformat(),
                attachment_name="customs_declaration_photo.jpg",
            ),
            doc_type="customs_declaration",
            doc_type_confidence=0.9,
            identifiers=Identifiers(
                container_no=["MSCU1234567"], declaration_no="108234567890"
            ),
            route=Route(),
            extraction_status="ok",
            extraction_method="llm",
        )

        backend_root = Path("backend").resolve()
        storage_root = backend_root / "storage"
        storage_root.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=storage_root) as temp_dir:
            with patch("gmail_service.adapter.ATTACHMENT_STORAGE_DIR", Path(temp_dir)):
                payload = build_processed_email_request(
                    gmail_connection_id=gmail_connection_id,
                    sync_job_id=sync_job_id,
                    email=email,
                    attachment_results=[
                        AttachmentExtractionResult(
                            attachment=email.attachments[0],
                            extracted_text="Invoice No: INV-001",
                            text_extract_status="extracted",
                            record=pdf_record,
                        ),
                        AttachmentExtractionResult(
                            attachment=email.attachments[1],
                            extracted_text=None,
                            text_extract_status="extracted",
                            record=image_record,
                        ),
                    ],
                )

        pdf_attachment = next(
            a for a in payload.attachments if a.filename == "invoice.pdf"
        )
        image_attachment = next(
            a
            for a in payload.attachments
            if a.filename == "customs_declaration_photo.jpg"
        )
        self.assertTrue(pdf_attachment.is_text_pdf)
        self.assertFalse(image_attachment.is_text_pdf)

        declaration_fact = next(
            fact
            for fact in payload.extracted_facts
            if fact.field_name == "declaration_no"
        )
        self.assertEqual(declaration_fact.source_type, "image_vision")
        self.assertEqual(declaration_fact.container_no, "MSCU1234567")

        status_facts_by_source = {
            fact.source_type
            for fact in payload.extracted_facts
            if fact.field_name == "status_text" and fact.container_no == "MSCU1234567"
        }
        self.assertIn("pdf_text", status_facts_by_source)
        self.assertIn("image_vision", status_facts_by_source)


if __name__ == "__main__":
    unittest.main()
