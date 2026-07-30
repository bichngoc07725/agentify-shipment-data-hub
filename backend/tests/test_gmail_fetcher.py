import base64
import unittest
from unittest.mock import Mock

from gmail_service.fetcher import _collect_document_attachments, resolve_sync_message_ids
from gmail_service.models import GmailAttachmentPayload


class _InvalidHistoryError(Exception):
    pass


class GmailFetcherTest(unittest.TestCase):
    def test_resolve_sync_message_ids_uses_full_list_without_cursor(self) -> None:
        service = Mock()
        (
            service.users.return_value.messages.return_value.list.return_value.execute.return_value
        ) = {"messages": [{"id": "msg-001"}, {"id": "msg-002"}]}
        service.users.return_value.getProfile.return_value.execute.return_value = {
            "historyId": "history-002"
        }

        message_ids, next_cursor = resolve_sync_message_ids(
            service,
            query="newer_than:7d",
            max_results=48,
            sync_cursor=None,
        )

        self.assertEqual(message_ids, ["msg-001", "msg-002"])
        self.assertEqual(next_cursor, "history-002")

    def test_resolve_sync_message_ids_uses_history_when_cursor_exists(self) -> None:
        service = Mock()
        (
            service.users.return_value.history.return_value.list.return_value.execute.return_value
        ) = {
            "history": [
                {"messagesAdded": [{"message": {"id": "msg-003"}}]},
                {"messagesAdded": [{"message": {"id": "msg-004"}}]},
            ]
        }
        service.users.return_value.getProfile.return_value.execute.return_value = {
            "historyId": "history-004"
        }

        message_ids, next_cursor = resolve_sync_message_ids(
            service,
            max_results=48,
            sync_cursor="history-002",
        )

        self.assertEqual(message_ids, ["msg-003", "msg-004"])
        self.assertEqual(next_cursor, "history-004")

    def test_resolve_sync_message_ids_falls_back_when_cursor_invalid(self) -> None:
        service = Mock()
        history_request = service.users.return_value.history.return_value.list.return_value
        history_request.execute.side_effect = _InvalidHistoryError(
            "Requested entity was not found: startHistoryId"
        )
        (
            service.users.return_value.messages.return_value.list.return_value.execute.return_value
        ) = {"messages": [{"id": "msg-005"}]}
        service.users.return_value.getProfile.return_value.execute.return_value = {
            "historyId": "history-005"
        }

        message_ids, next_cursor = resolve_sync_message_ids(
            service,
            query="newer_than:7d",
            max_results=48,
            sync_cursor="history-002",
        )

        self.assertEqual(message_ids, ["msg-005"])
        self.assertEqual(next_cursor, "history-005")


class CollectDocumentAttachmentsTest(unittest.TestCase):
    def test_collects_pdf_and_image_but_skips_other_types(self) -> None:
        service = Mock()
        image_bytes = b"fake-jpeg-bytes"
        pdf_bytes = b"fake-pdf-bytes"
        docx_bytes = b"fake-docx-bytes"
        part = {
            "parts": [
                {
                    "filename": "customs_photo.jpg",
                    "mimeType": "image/jpeg",
                    "body": {
                        "data": base64.urlsafe_b64encode(image_bytes).decode(),
                        "size": len(image_bytes),
                    },
                },
                {
                    "filename": "invoice.pdf",
                    "mimeType": "application/pdf",
                    "body": {
                        "data": base64.urlsafe_b64encode(pdf_bytes).decode(),
                        "size": len(pdf_bytes),
                    },
                },
                {
                    "filename": "notes.docx",
                    "mimeType": (
                        "application/vnd.openxmlformats-officedocument"
                        ".wordprocessingml.document"
                    ),
                    "body": {
                        "data": base64.urlsafe_b64encode(docx_bytes).decode(),
                        "size": len(docx_bytes),
                    },
                },
            ]
        }

        out: list[GmailAttachmentPayload] = []
        _collect_document_attachments(service, "msg-001", part, out)

        filenames = [attachment.filename for attachment in out]
        self.assertEqual(filenames, ["customs_photo.jpg", "invoice.pdf"])
        self.assertEqual(out[0].mime_type, "image/jpeg")
        self.assertEqual(out[0].attachment_bytes, image_bytes)
        self.assertEqual(out[1].mime_type, "application/pdf")

    def test_image_reported_as_octet_stream_is_still_collected_by_extension(self) -> None:
        service = Mock()
        image_bytes = b"fake-png-bytes"
        part = {
            "filename": "scan.png",
            "mimeType": "application/octet-stream",
            "body": {
                "data": base64.urlsafe_b64encode(image_bytes).decode(),
                "size": len(image_bytes),
            },
        }

        out: list[GmailAttachmentPayload] = []
        _collect_document_attachments(service, "msg-001", part, out)

        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].mime_type, "image/png")


if __name__ == "__main__":
    unittest.main()
