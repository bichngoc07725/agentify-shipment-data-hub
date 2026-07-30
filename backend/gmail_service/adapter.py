import re
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from api.models import (
    IngestAttachmentRequest,
    IngestFactRequest,
    ProcessedEmailIngestRequest,
)
from gmail_service.deterministic_extract import extract_deterministic
from gmail_service.models import (
    ExtractedRecord,
    GmailAttachmentPayload,
    GmailEmailPayload,
)

BACKEND_ROOT = Path(__file__).resolve().parents[1]
ATTACHMENT_STORAGE_DIR = BACKEND_ROOT / "storage" / "gmail_attachments"

SUMMARY_FIELDS = (
    "booking_no",
    "bl_no",
    "po_no",
    "do_no",
    "declaration_no",
    "vessel",
    "voyage",
    "pol",
    "pod",
    "etd",
    "eta",
    "ata",
)

CONTAINER_PATTERN = re.compile(r"\b([A-Z]{4}\s?-?\d{7})\b", re.IGNORECASE)
LABELED_FIELD_PATTERNS = {
    "booking_no": [
        re.compile(r"\bbooking(?:\s+no|\s+number)?\s*[:#-]?\s*([A-Z0-9-]+)\b", re.IGNORECASE)
    ],
    "bl_no": [
        re.compile(r"\bb\/l(?:\s+no|\s+number)?\s*[:#-]?\s*([A-Z0-9-]+)\b", re.IGNORECASE),
        re.compile(
            r"\bbill\s+of\s+lading(?:\s+no|\s+number)?\s*[:#-]?\s*([A-Z0-9-]+)\b",
            re.IGNORECASE,
        ),
    ],
    "po_no": [
        re.compile(r"\bpo(?:\s+no|\s+number)?\s*[:#-]?\s*([A-Z0-9-]+)\b", re.IGNORECASE)
    ],
}
DATE_FIELD_PATTERNS = {
    "etd": [
        re.compile(r"\betd\s*[:#-]?\s*(\d{4}-\d{2}-\d{2})\b", re.IGNORECASE),
    ],
    "eta": [
        re.compile(r"\beta\s*[:#-]?\s*(\d{4}-\d{2}-\d{2})\b", re.IGNORECASE),
        re.compile(
            r"\bdelivery\s+date\s*[:#-]?\s*(\d{4}-\d{2}-\d{2})\b", re.IGNORECASE
        ),
    ],
}


class AttachmentExtractionResult:
    def __init__(
        self,
        attachment: GmailAttachmentPayload,
        extracted_text: str | None,
        text_extract_status: str,
        record: ExtractedRecord,
    ) -> None:
        self.attachment = attachment
        self.extracted_text = extracted_text
        self.text_extract_status = text_extract_status
        self.record = record


class EmailTextExtractionResult:
    def __init__(
        self,
        extracted_text: str,
        record: ExtractedRecord,
    ) -> None:
        self.extracted_text = extracted_text
        self.record = record


def build_processed_email_request(
    gmail_connection_id: UUID,
    sync_job_id: UUID,
    email: GmailEmailPayload,
    attachment_results: list[AttachmentExtractionResult],
    email_text_result: EmailTextExtractionResult | None = None,
) -> ProcessedEmailIngestRequest:
    attachments = [
        IngestAttachmentRequest(
            gmail_attachment_id=result.attachment.gmail_attachment_id,
            filename=result.attachment.filename,
            mime_type=result.attachment.mime_type,
            size_bytes=result.attachment.size_bytes,
            storage_path=_persist_gmail_attachment(
                email.gmail_message_id,
                result.attachment,
            ),
            is_text_pdf=(
                not result.attachment.mime_type.startswith("image/")
                and result.text_extract_status == "extracted"
            ),
            text_extract_status=result.text_extract_status,
            extracted_text=result.extracted_text,
            document_type=result.record.doc_type,
            extracted_record=result.record.model_dump(mode="json"),
        )
        for result in attachment_results
    ]

    extracted_facts: list[IngestFactRequest] = []
    for result in attachment_results:
        source_type = (
            "image_vision"
            if result.attachment.mime_type.startswith("image/")
            else "pdf_text"
        )
        extracted_facts.extend(
            _build_record_facts(
                record=result.record,
                source_type=source_type,
                source_label=result.attachment.filename,
                attachment_filename=result.attachment.filename,
                confidence=Decimal(str(result.record.doc_type_confidence)),
                status_value=result.record.doc_type,
            )
        )

    if email_text_result is not None:
        extracted_facts.extend(
            _build_record_facts(
                record=email_text_result.record,
                source_type="email_body",
                source_label="Email body",
                attachment_filename=None,
                confidence=Decimal(str(email_text_result.record.doc_type_confidence)),
                status_value=email.subject.strip() or email_text_result.record.doc_type,
            )
        )

    extracted_facts.extend(_build_email_body_facts(email))
    extracted_facts = _dedupe_facts(extracted_facts)

    return ProcessedEmailIngestRequest(
        gmail_connection_id=gmail_connection_id,
        sync_job_id=sync_job_id,
        gmail_message_id=email.gmail_message_id,
        gmail_thread_id=email.gmail_thread_id,
        subject=email.subject,
        from_email=email.from_email,
        to_emails=email.to_emails,
        cc_emails=email.cc_emails,
        sent_at=email.sent_at,
        snippet=email.snippet,
        body_text=email.body_text,
        body_html=email.body_html,
        raw_labels=email.raw_labels,
        has_pdf_attachments=bool(email.attachments),
        attachments=attachments,
        extracted_facts=extracted_facts,
    )


def _persist_gmail_attachment(
    gmail_message_id: str,
    attachment: GmailAttachmentPayload,
) -> str:
    safe_filename = _sanitize_filename(attachment.filename)
    message_dir = ATTACHMENT_STORAGE_DIR / gmail_message_id
    message_dir.mkdir(parents=True, exist_ok=True)
    absolute_path = message_dir / safe_filename
    absolute_path.write_bytes(attachment.attachment_bytes)
    return absolute_path.relative_to(BACKEND_ROOT).as_posix()


def _sanitize_filename(filename: str) -> str:
    basename = Path(filename).name or "attachment.pdf"
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", basename)
    return sanitized[:240] or "attachment.pdf"


def _build_fact(
    field_name: str,
    normalized_value: str,
    container_no: str | None,
    result: AttachmentExtractionResult,
) -> IngestFactRequest:
    return IngestFactRequest(
        field_name=field_name,
        field_value=normalized_value,
        normalized_value=normalized_value,
        container_no=container_no,
        source_type="pdf_text",
        source_label=result.attachment.filename,
        document_type=result.record.doc_type,
        confidence=Decimal(str(result.record.doc_type_confidence)),
        attachment_filename=result.attachment.filename,
    )


def _build_record_facts(
    record: ExtractedRecord,
    source_type: str,
    source_label: str,
    attachment_filename: str | None,
    confidence: Decimal | None,
    status_value: str,
) -> list[IngestFactRequest]:
    facts: list[IngestFactRequest] = []
    container_nos = [
        container_no.strip().upper()
        for container_no in record.identifiers.container_no
        if container_no
    ]
    for container_no in container_nos:
        facts.append(
            _build_simple_fact(
                field_name="container_no",
                normalized_value=container_no,
                container_no=container_no,
                source_type=source_type,
                source_label=source_label,
                document_type=record.doc_type,
                confidence=confidence,
                attachment_filename=attachment_filename,
            )
        )

    for field_name in SUMMARY_FIELDS:
        value = _get_record_value(record, field_name)
        if not value:
            continue
        if container_nos:
            for container_no in container_nos:
                facts.append(
                    _build_simple_fact(
                        field_name=field_name,
                        normalized_value=str(value),
                        container_no=container_no,
                        source_type=source_type,
                        source_label=source_label,
                        document_type=record.doc_type,
                        confidence=confidence,
                        attachment_filename=attachment_filename,
                    )
                )
        else:
            facts.append(
                _build_simple_fact(
                    field_name=field_name,
                    normalized_value=str(value),
                    container_no=None,
                    source_type=source_type,
                    source_label=source_label,
                    document_type=record.doc_type,
                    confidence=confidence,
                    attachment_filename=attachment_filename,
                )
            )

    if record.free_time_days is not None:
        for container_no in container_nos or [None]:
            facts.append(
                _build_simple_fact(
                    field_name="free_time_days",
                    normalized_value=str(record.free_time_days),
                    container_no=container_no,
                    source_type=source_type,
                    source_label=source_label,
                    document_type=record.doc_type,
                    confidence=confidence,
                    attachment_filename=attachment_filename,
                )
            )

    if record.identifiers.seal_no:
        for seal_no in record.identifiers.seal_no:
            for container_no in container_nos or [None]:
                facts.append(
                    _build_simple_fact(
                        field_name="seal_no",
                        normalized_value=seal_no,
                        container_no=container_no,
                        source_type=source_type,
                        source_label=source_label,
                        document_type=record.doc_type,
                        confidence=confidence,
                        attachment_filename=attachment_filename,
                    )
                )

    for container_no in container_nos or [None]:
        facts.append(
            _build_simple_fact(
                field_name="status_text",
                normalized_value=status_value,
                container_no=container_no,
                source_type=source_type,
                source_label=source_label,
                document_type=record.doc_type,
                confidence=confidence,
                attachment_filename=attachment_filename,
            )
        )

    return facts


def _build_simple_fact(
    field_name: str,
    normalized_value: str,
    container_no: str | None,
    source_type: str,
    source_label: str,
    document_type: str | None,
    confidence: Decimal | None,
    attachment_filename: str | None,
) -> IngestFactRequest:
    return IngestFactRequest(
        field_name=field_name,
        field_value=normalized_value,
        normalized_value=normalized_value,
        container_no=container_no,
        source_type=source_type,
        source_label=source_label,
        document_type=document_type,
        confidence=confidence,
        attachment_filename=attachment_filename,
    )


def _build_email_body_facts(email: GmailEmailPayload) -> list[IngestFactRequest]:
    content = _collect_email_text_content(email)
    if not content:
        return []

    container_nos = _extract_container_nos(content)
    default_container_no = container_nos[0] if len(container_nos) == 1 else None
    facts: list[IngestFactRequest] = []

    for container_no in container_nos:
        facts.append(
            IngestFactRequest(
                field_name="container_no",
                field_value=container_no,
                normalized_value=container_no,
                container_no=container_no,
                source_type="email_body",
                source_label="Email body",
            )
        )

    for field_name, patterns in LABELED_FIELD_PATTERNS.items():
        value = _extract_first_match(content, patterns)
        if not value:
            continue
        facts.append(
            IngestFactRequest(
                field_name=field_name,
                field_value=value,
                normalized_value=value,
                container_no=default_container_no,
                source_type="email_body",
                source_label="Email body",
            )
        )

    for field_name, patterns in DATE_FIELD_PATTERNS.items():
        value = _extract_first_match(content, patterns)
        if not value:
            continue
        facts.append(
            IngestFactRequest(
                field_name=field_name,
                field_value=value,
                normalized_value=value,
                container_no=default_container_no,
                source_type="email_body",
                source_label="Email body",
            )
        )

    # Fields the exception engine depends on, which the patterns above predate.
    for field_name, value in _extract_risk_fields(content).items():
        facts.append(
            IngestFactRequest(
                field_name=field_name,
                field_value=value,
                normalized_value=value,
                container_no=default_container_no,
                source_type="email_body",
                source_label="Email body",
            )
        )

    status_text = _derive_status_text(email.subject)
    if status_text:
        facts.append(
            IngestFactRequest(
                field_name="status_text",
                field_value=status_text,
                normalized_value=status_text,
                container_no=default_container_no,
                source_type="email_body",
                source_label="Email subject",
            )
        )

    return facts


def _extract_risk_fields(content: str) -> dict[str, str]:
    """Pull ATA, D/O number and free time out of an email body.

    These drive the free-time and missing-D/O exceptions, so they are read from
    the body as well as from attachments.
    """
    deterministic = extract_deterministic("", "", content)
    values: dict[str, str] = {}

    ata = (deterministic.get("route") or {}).get("ata")
    if ata:
        values["ata"] = str(ata)

    do_no = (deterministic.get("identifiers") or {}).get("do_no")
    if do_no:
        values["do_no"] = str(do_no)

    free_time_days = deterministic.get("free_time_days")
    if free_time_days is not None:
        values["free_time_days"] = str(free_time_days)

    return values


def _collect_email_text_content(email: GmailEmailPayload) -> str:
    content_parts = [
        email.body_text,
        _strip_html(email.body_html) if email.body_html else None,
        email.snippet,
        email.subject,
    ]
    return "\n".join(part.strip() for part in content_parts if part and part.strip())


def _extract_container_nos(content: str) -> list[str]:
    seen: set[str] = set()
    values: list[str] = []
    for match in CONTAINER_PATTERN.finditer(content):
        container_no = match.group(1).replace(" ", "").replace("-", "").upper()
        if container_no in seen:
            continue
        seen.add(container_no)
        values.append(container_no)
    return values


def _extract_first_match(content: str, patterns: list[re.Pattern[str]]) -> str | None:
    for pattern in patterns:
        match = pattern.search(content)
        if match:
            return match.group(1).strip().upper()
    return None


def _strip_html(value: str) -> str:
    return re.sub(r"<[^>]+>", " ", value)


def _derive_status_text(subject: str) -> str | None:
    normalized_subject = subject.strip()
    if not normalized_subject:
        return None
    return normalized_subject[:255]


def _dedupe_facts(facts: list[IngestFactRequest]) -> list[IngestFactRequest]:
    deduped: list[IngestFactRequest] = []
    seen: set[tuple[str, str, str | None, str, str | None]] = set()
    for fact in facts:
        key = (
            fact.field_name,
            fact.normalized_value or fact.field_value,
            fact.container_no,
            fact.source_type,
            fact.attachment_filename,
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(fact)
    return deduped


def _get_record_value(record: ExtractedRecord, field_name: str) -> str | None:
    if hasattr(record.identifiers, field_name):
        return getattr(record.identifiers, field_name)
    if hasattr(record.route, field_name):
        return getattr(record.route, field_name)
    return None
