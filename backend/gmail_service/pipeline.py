from pydantic import ValidationError

from gmail_service.field_extract import extract_fields, extract_fields_from_image
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

    return _build_record(email, source_name, fields)


def process_image_attachment(
    email: dict[str, str], filename: str, image_bytes: bytes, mime_type: str
) -> ExtractedRecord:
    # `extract_fields_from_image` also degrades instead of raising for provider
    # problems (see its docstring); this except path only covers unexpected errors.
    try:
        fields = extract_fields_from_image(
            email["subject"], email["sender"], image_bytes, mime_type
        )
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

    return _build_record(email, filename, fields)


def _build_record(
    email: dict[str, str], source_name: str, fields: dict
) -> ExtractedRecord:
    fields.setdefault("extraction_status", "ok")
    source = Source(
        message_id=email["message_id"],
        sender=email["sender"],
        subject=email["subject"],
        received_at=_normalize_received_at(email["received_at"]),
        attachment_name=source_name,
    )

    try:
        return ExtractedRecord(source=source, **fields)
    except ValidationError as exc:
        # A non-strict provider (e.g. Gemini's plain JSON mode, unlike Azure's
        # enforced json_schema) can return a field with the wrong shape
        # (a number instead of a string, an object instead of a string). One
        # malformed field must not crash the whole document — degrade to a
        # bare, always-valid record instead of losing it. Every value here is
        # a hardcoded-safe literal, not read back from `fields`, because the
        # field that broke validation is not known without inspecting `exc`.
        return ExtractedRecord(
            source=source,
            doc_type="other",
            doc_type_confidence=0.0,
            identifiers={},
            route={},
            extraction_status="failed",
            extraction_method="deterministic",
            extraction_error=f"Malformed extraction output: {exc}",
        )


def _normalize_received_at(value) -> str:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)
