import base64
import mimetypes
from datetime import UTC, datetime
from email.utils import getaddresses, parsedate_to_datetime
from typing import Any

from gmail_service.config import GMAIL_QUERY
from gmail_service.models import GmailAttachmentPayload, GmailEmailPayload

# Photographed/scanned documents. HEIC/HEIF (iPhone camera default) is
# deliberately excluded — neither the Azure Responses API nor Gemini accept it
# directly, and converting it would need a new dependency (e.g. pillow-heif).
_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")
_IMAGE_MIME_TYPES = ("image/jpeg", "image/png", "image/webp")


def list_new_messages(
    service: Any, query: str | None = None, max_results: int = 100
) -> list[str]:
    effective_query = query or GMAIL_QUERY
    response = (
        service.users()
        .messages()
        .list(userId="me", q=effective_query, maxResults=max_results)
        .execute()
    )
    return [message["id"] for message in response.get("messages", [])]


def resolve_sync_message_ids(
    service: Any,
    query: str | None = None,
    max_results: int = 100,
    sync_cursor: str | None = None,
) -> tuple[list[str], str | None]:
    if sync_cursor:
        try:
            message_ids = list_changed_messages(
                service,
                start_history_id=sync_cursor,
                max_results=max_results,
            )
            return message_ids, get_latest_history_id(service)
        except Exception as exc:
            if not _is_invalid_history_cursor_error(exc):
                raise

    message_ids = list_new_messages(service, query=query, max_results=max_results)
    return message_ids, get_latest_history_id(service)


def list_changed_messages(
    service: Any,
    start_history_id: str,
    max_results: int = 100,
) -> list[str]:
    message_ids: list[str] = []
    seen: set[str] = set()
    page_token: str | None = None

    while len(message_ids) < max_results:
        request = (
            service.users()
            .history()
            .list(
                userId="me",
                startHistoryId=start_history_id,
                historyTypes=["messageAdded"],
                pageToken=page_token,
            )
        )
        response = request.execute()
        for history_entry in response.get("history", []):
            for message_added in history_entry.get("messagesAdded", []):
                message = message_added.get("message", {})
                message_id = message.get("id")
                if not message_id or message_id in seen:
                    continue
                seen.add(message_id)
                message_ids.append(message_id)
                if len(message_ids) >= max_results:
                    break
            if len(message_ids) >= max_results:
                break

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return message_ids


def get_latest_history_id(service: Any) -> str | None:
    profile = service.users().getProfile(userId="me").execute()
    history_id = profile.get("historyId")
    return str(history_id) if history_id is not None else None


def get_email(service: Any, msg_id: str) -> GmailEmailPayload:
    message = (
        service.users().messages().get(userId="me", id=msg_id, format="full").execute()
    )
    headers = {
        header["name"]: header["value"]
        for header in message["payload"].get("headers", [])
    }
    attachments: list[GmailAttachmentPayload] = []
    body_text, body_html = _collect_body_parts(message["payload"])
    _collect_document_attachments(service, msg_id, message["payload"], attachments)

    return GmailEmailPayload(
        gmail_message_id=msg_id,
        gmail_thread_id=message.get("threadId"),
        subject=headers.get("Subject", ""),
        from_email=_extract_single_address(headers.get("From", "")),
        to_emails=_extract_addresses(headers.get("To", "")),
        cc_emails=_extract_addresses(headers.get("Cc", "")),
        sent_at=_normalize_datetime(headers.get("Date")),
        snippet=message.get("snippet"),
        body_text=body_text,
        body_html=body_html,
        raw_labels=message.get("labelIds", []),
        attachments=attachments,
    )


def _is_collectible_attachment(filename: str, mime_type: str) -> bool:
    lower_name = filename.lower()
    return (
        lower_name.endswith(".pdf")
        or lower_name.endswith(_IMAGE_EXTENSIONS)
        or mime_type in _IMAGE_MIME_TYPES
    )


def _resolve_mime_type(filename: str, mime_type: str) -> str:
    if mime_type and mime_type != "application/octet-stream":
        return mime_type
    guessed, _ = mimetypes.guess_type(filename)
    if guessed:
        return guessed
    return "application/pdf" if filename.lower().endswith(".pdf") else mime_type


def _collect_document_attachments(
    service: Any,
    msg_id: str,
    part: dict[str, Any],
    out: list[GmailAttachmentPayload],
) -> None:
    filename = part.get("filename", "")
    body = part.get("body", {})
    reported_mime_type = part.get("mimeType", "")
    if _is_collectible_attachment(filename, reported_mime_type):
        if "attachmentId" in body:
            attachment = (
                service.users()
                .messages()
                .attachments()
                .get(userId="me", messageId=msg_id, id=body["attachmentId"])
                .execute()
            )
            data = base64.urlsafe_b64decode(attachment["data"])
            gmail_attachment_id = body["attachmentId"]
        else:
            data = base64.urlsafe_b64decode(body["data"])
            gmail_attachment_id = None
        out.append(
            GmailAttachmentPayload(
                gmail_attachment_id=gmail_attachment_id,
                filename=filename,
                mime_type=_resolve_mime_type(filename, reported_mime_type),
                size_bytes=body.get("size"),
                attachment_bytes=data,
            )
        )

    for child_part in part.get("parts", []):
        _collect_document_attachments(service, msg_id, child_part, out)


def _collect_body_parts(part: dict[str, Any]) -> tuple[str | None, str | None]:
    body_text: list[str] = []
    body_html: list[str] = []
    _walk_body_parts(part, body_text, body_html)
    text = "\n".join(fragment for fragment in body_text if fragment.strip()) or None
    html = "\n".join(fragment for fragment in body_html if fragment.strip()) or None
    return text, html


def _walk_body_parts(
    part: dict[str, Any], body_text: list[str], body_html: list[str]
) -> None:
    mime_type = part.get("mimeType", "")
    body = part.get("body", {})
    data = body.get("data")
    if data and not part.get("filename"):
        decoded = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
        if mime_type == "text/plain":
            body_text.append(decoded)
        elif mime_type == "text/html":
            body_html.append(decoded)
    for child_part in part.get("parts", []):
        _walk_body_parts(child_part, body_text, body_html)


def _extract_addresses(value: str) -> list[str]:
    return [email for _, email in getaddresses([value]) if email]


def _extract_single_address(value: str) -> str:
    addresses = _extract_addresses(value)
    return addresses[0] if addresses else value


def _normalize_datetime(value: str | None) -> datetime:
    if not value:
        return datetime.now(UTC)
    try:
        return parsedate_to_datetime(value).astimezone(UTC)
    except (TypeError, ValueError, IndexError):
        return datetime.now(UTC)


def _is_invalid_history_cursor_error(exc: Exception) -> bool:
    status_code = getattr(getattr(exc, "resp", None), "status", None)
    if status_code == 404:
        return True
    message = str(exc)
    return "startHistoryId" in message or "historyId" in message
