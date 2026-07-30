import unittest
from datetime import UTC, datetime
from unittest.mock import patch

from gmail_service.pipeline import process_image_attachment, process_text_content


class GmailPipelineTest(unittest.TestCase):
    def test_process_text_content_normalizes_received_at_datetime(self) -> None:
        sent_at = datetime(2026, 6, 10, 9, 12, tzinfo=UTC)

        with patch(
            "gmail_service.pipeline.extract_fields",
            return_value={
                "doc_type": "other",
                "doc_type_confidence": 0.5,
                "identifiers": {},
                "route": {},
            },
        ):
            record = process_text_content(
                {
                    "message_id": "msg-001",
                    "sender": "ops@carrier.com",
                    "subject": "Delivery update",
                    "received_at": sent_at,
                },
                "email_body",
                "Container no: TCKU1234567",
            )

        self.assertEqual(record.source.received_at, sent_at.isoformat())

    def test_process_text_content_records_extraction_error(self) -> None:
        with patch(
            "gmail_service.pipeline.extract_fields",
            side_effect=RuntimeError("429 RESOURCE_EXHAUSTED"),
        ):
            record = process_text_content(
                {
                    "message_id": "msg-002",
                    "sender": "ops@carrier.com",
                    "subject": "Booking note",
                    "received_at": "2026-06-10T09:12:00+00:00",
                },
                "booking_note.pdf",
                "Booking No: OOL-BKG-260609",
            )

        self.assertEqual(record.extraction_status, "failed")
        self.assertEqual(record.extraction_error, "429 RESOURCE_EXHAUSTED")

    def test_process_image_attachment_builds_a_record(self) -> None:
        with patch(
            "gmail_service.pipeline.extract_fields_from_image",
            return_value={
                "doc_type": "customs_declaration",
                "doc_type_confidence": 0.9,
                "identifiers": {"declaration_no": "108234567890"},
                "route": {},
                "extraction_method": "llm",
                "extraction_status": "ok",
            },
        ):
            record = process_image_attachment(
                {
                    "message_id": "msg-003",
                    "sender": "docs@forwarder-demo.com",
                    "subject": "To khai Hai quan - MSCU1234567",
                    "received_at": "2026-07-10T09:15:00+00:00",
                },
                "customs_declaration_mscu1234567_photo.jpg",
                b"fake-bytes",
                "image/jpeg",
            )

        self.assertEqual(record.doc_type, "customs_declaration")
        self.assertEqual(record.identifiers.declaration_no, "108234567890")
        self.assertEqual(record.source.attachment_name, "customs_declaration_mscu1234567_photo.jpg")

    def test_process_image_attachment_records_extraction_error(self) -> None:
        with patch(
            "gmail_service.pipeline.extract_fields_from_image",
            side_effect=RuntimeError("no vision provider configured"),
        ):
            record = process_image_attachment(
                {
                    "message_id": "msg-004",
                    "sender": "docs@forwarder-demo.com",
                    "subject": "Customs scan",
                    "received_at": "2026-07-10T09:15:00+00:00",
                },
                "scan.jpg",
                b"fake-bytes",
                "image/jpeg",
            )

        self.assertEqual(record.extraction_status, "failed")
        self.assertEqual(record.extraction_error, "no vision provider configured")

    def test_malformed_llm_output_degrades_instead_of_crashing(self) -> None:
        # A non-strict provider (e.g. Gemini's plain JSON mode) can return a
        # field with a shape no coercion covers — here `route` as a bare
        # string instead of an object. This must not raise a pydantic
        # ValidationError out of process_image_attachment.
        with patch(
            "gmail_service.pipeline.extract_fields_from_image",
            return_value={
                "doc_type": "customs_declaration",
                "doc_type_confidence": 0.9,
                "identifiers": {},
                "route": "not an object",
                "extraction_method": "llm",
                "extraction_status": "ok",
            },
        ):
            record = process_image_attachment(
                {
                    "message_id": "msg-005",
                    "sender": "docs@forwarder-demo.com",
                    "subject": "To khai Hai quan - MSCU1234567",
                    "received_at": "2026-07-10T09:15:00+00:00",
                },
                "customs_declaration_mscu1234567_photo.jpg",
                b"fake-bytes",
                "image/jpeg",
            )

        self.assertEqual(record.extraction_status, "failed")
        self.assertEqual(record.doc_type, "other")
        self.assertIn("Malformed extraction output", record.extraction_error)

    def test_numeric_quantity_and_object_carrier_are_coerced_not_rejected(self) -> None:
        # Confirmed live against Gemini: it returns cargo_lines[].quantity as
        # a bare number (2.0) instead of "2 Bo", and carrier as {"name": ...}
        # instead of a plain string. Both should still produce a usable record.
        with patch(
            "gmail_service.pipeline.extract_fields_from_image",
            return_value={
                "doc_type": "customs_declaration",
                "doc_type_confidence": 0.9,
                "identifiers": {},
                "route": {},
                "carrier": {"name": "Maersk"},
                "cargo_lines": [{"quantity": 2.0, "description": "CNC machine"}],
                "extraction_method": "llm",
                "extraction_status": "ok",
            },
        ):
            record = process_image_attachment(
                {
                    "message_id": "msg-006",
                    "sender": "docs@forwarder-demo.com",
                    "subject": "To khai Hai quan - MSCU1234567",
                    "received_at": "2026-07-10T09:15:00+00:00",
                },
                "customs_declaration_mscu1234567_photo.jpg",
                b"fake-bytes",
                "image/jpeg",
            )

        self.assertEqual(record.extraction_status, "ok")
        self.assertEqual(record.carrier, "Maersk")
        self.assertEqual(record.cargo_lines[0].quantity, "2.0")


if __name__ == "__main__":
    unittest.main()
