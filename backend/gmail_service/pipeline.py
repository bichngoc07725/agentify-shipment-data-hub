from gmail_service.field_extract import extract_fields
from gmail_service.models import ExtractedRecord, Source
from gmail_service.pdf_reader import read_pdf_text


def process_pdf_attachment(
    email: dict[str, str], filename: str, pdf_bytes: bytes
) -> ExtractedRecord:
    text = read_pdf_text(pdf_bytes)
    return process_text_content(email, filename, text)


def process_pdf_text(
    email: dict[str, str], filename: str, extracted_text: str
) -> ExtractedRecord:
    return process_text_content(email, filename, extracted_text)


def process_text_content(
    email: dict[str, str], source_name: str, extracted_text: str
) -> ExtractedRecord:
    # `extract_fields` degrades to rule-only output instead of raising when the
    # LLM provider fails, so this except path only covers unexpected errors.
    try:
        fields = extract_fields(email["subject"], email["sender"], extracted_text)
    except Exception as exc:
        fields = {
            "doc_type": "other",
            "doc_type_confidence": 0.0,
            "identifiers": {},
            "route": {},
            "extraction_status": "failed",
            "extraction_error": str(exc),
            "extraction_method": "deterministic",
        }

    fields.setdefault("extraction_status", "ok")

    return ExtractedRecord(
        source=Source(
            message_id=email["message_id"],
            sender=email["sender"],
            subject=email["subject"],
            received_at=_normalize_received_at(email["received_at"]),
            attachment_name=source_name,
        ),
        **fields,
    )


def _normalize_received_at(value) -> str:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)
