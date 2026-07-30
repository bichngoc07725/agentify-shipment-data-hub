from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text

from scripts._path import ensure_backend_root_on_path

ensure_backend_root_on_path(__file__)
from api.models import (
    IngestAttachmentRequest,
    IngestFactRequest,
    ProcessedEmailIngestRequest,
)
from db.database import AsyncSessionLocal
from db.models import GmailConnection, SyncJob
from services.ingestion_service import ingest_processed_email

DEMO_ACCOUNT_EMAIL = "demo-logistics@agentify.vn"
DEMO_DISPLAY_NAME = "Agentify Demo Logistics"
DEMO_GOOGLE_ACCOUNT_ID = "agentify-demo-google-account"
BACKEND_ROOT = Path(__file__).resolve().parents[1]
DEMO_PDF_DIR = BACKEND_ROOT / "storage" / "demo_pdfs"
DEMO_CONTAINER_NOS = [
    "MSCU1234567",
    "TGHU7654321",
    "OOLU9988776",
    "WHLU4455667",
    "CAIU7788990",
    "SEGU5566778",
    "TRHU3344556",
    "FSCU2211334",
    "CMAU6677889",
    "TEMU5544332",
]


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _escape_pdf_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _build_text_pdf_bytes(lines: list[str]) -> bytes:
    text_lines = [_escape_pdf_text(line) for line in lines if line.strip()]
    if not text_lines:
        text_lines = ["Agentify demo PDF"]

    content_lines = ["BT", "/F1 12 Tf", "50 780 Td", "14 TL"]
    for index, line in enumerate(text_lines):
        if index == 0:
            content_lines.append(f"({line}) Tj")
        else:
            content_lines.append("T*")
            content_lines.append(f"({line}) Tj")
    content_lines.append("ET")
    stream = "\n".join(content_lines).encode("latin-1", errors="replace")

    objects = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj",
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj",
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj",
        b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj",
        b"5 0 obj << /Length %d >> stream\n%b\nendstream endobj" % (len(stream), stream),
    ]

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(pdf))
        pdf.extend(obj)
        pdf.extend(b"\n")

    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(offsets)}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        (
            f"trailer << /Size {len(offsets)} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(pdf)


def _materialize_demo_pdf(filename: str, extracted_text: str | None) -> tuple[str, int]:
    DEMO_PDF_DIR.mkdir(parents=True, exist_ok=True)
    relative_path = Path("storage") / "demo_pdfs" / filename
    absolute_path = BACKEND_ROOT / relative_path
    lines = (extracted_text or filename).splitlines()
    absolute_path.write_bytes(_build_text_pdf_bytes(lines))
    return relative_path.as_posix(), absolute_path.stat().st_size


def build_demo_payloads(
    gmail_connection_id: UUID,
    sync_job_id: UUID,
) -> list[ProcessedEmailIngestRequest]:
    payloads = [
        ProcessedEmailIngestRequest(
            gmail_connection_id=gmail_connection_id,
            sync_job_id=sync_job_id,
            gmail_message_id="demo-msg-001",
            gmail_thread_id="demo-thread-001",
            subject="Booking Confirmation - MSCU1234567 - BKG-88921",
            from_email="booking@maersk-demo.com",
            to_emails=["ops@agentify.vn"],
            sent_at=_dt("2026-06-05T08:15:00Z"),
            snippet="Đã xác nhận booking cho MSCU1234567 trên tàu MAERSK HANOI 126E.",
            body_text=(
                "Container MSCU1234567 đã được đặt chỗ. Tàu MAERSK HANOI 126E. "
                "ETD 2026-06-06 từ Shanghai đi Hai Phong."
            ),
            raw_labels=["INBOX", "LOGISTICS"],
            has_pdf_attachments=True,
            attachments=[
                IngestAttachmentRequest(
                    gmail_attachment_id="demo-att-001",
                    filename="booking_confirmation_mscu1234567.pdf",
                    mime_type="application/pdf",
                    size_bytes=212_548,
                    storage_path="/demo/booking_confirmation_mscu1234567.pdf",
                    is_text_pdf=True,
                    text_extract_status="extracted",
                    extracted_text=(
                        "Container: MSCU1234567\n"
                        "Booking No: BKG-88921\n"
                        "POL: Shanghai\n"
                        "POD: Hai Phong\n"
                        "Vessel/Voyage: MAERSK HANOI / 126E\n"
                        "ETD: 2026-06-06"
                    ),
                    document_type="booking_confirmation",
                )
            ],
            extracted_facts=[
                IngestFactRequest(
                    field_name="container_no",
                    field_value="MSCU1234567",
                    normalized_value="MSCU1234567",
                    container_no="MSCU1234567",
                    source_type="email_subject",
                    source_label="Booking Confirmation - MSCU1234567 - BKG-88921",
                    document_type="booking_confirmation",
                    confidence=Decimal("0.9900"),
                ),
                IngestFactRequest(
                    field_name="booking_no",
                    field_value="BKG-88921",
                    normalized_value="BKG-88921",
                    container_no="MSCU1234567",
                    source_type="pdf_text",
                    source_label="Booking No: BKG-88921",
                    document_type="booking_confirmation",
                    confidence=Decimal("0.9800"),
                    attachment_filename="booking_confirmation_mscu1234567.pdf",
                ),
                IngestFactRequest(
                    field_name="vessel",
                    field_value="MAERSK HANOI",
                    normalized_value="MAERSK HANOI",
                    container_no="MSCU1234567",
                    source_type="pdf_text",
                    source_label="Vessel/Voyage: MAERSK HANOI / 126E",
                    document_type="booking_confirmation",
                    confidence=Decimal("0.9700"),
                    attachment_filename="booking_confirmation_mscu1234567.pdf",
                ),
                IngestFactRequest(
                    field_name="voyage",
                    field_value="126E",
                    normalized_value="126E",
                    container_no="MSCU1234567",
                    source_type="pdf_text",
                    source_label="Vessel/Voyage: MAERSK HANOI / 126E",
                    document_type="booking_confirmation",
                    confidence=Decimal("0.9700"),
                    attachment_filename="booking_confirmation_mscu1234567.pdf",
                ),
                IngestFactRequest(
                    field_name="pol",
                    field_value="Shanghai",
                    normalized_value="Shanghai",
                    container_no="MSCU1234567",
                    source_type="pdf_text",
                    source_label="POL: Shanghai",
                    document_type="booking_confirmation",
                    confidence=Decimal("0.9600"),
                    attachment_filename="booking_confirmation_mscu1234567.pdf",
                ),
                IngestFactRequest(
                    field_name="pod",
                    field_value="Hai Phong",
                    normalized_value="Hai Phong",
                    container_no="MSCU1234567",
                    source_type="pdf_text",
                    source_label="POD: Hai Phong",
                    document_type="booking_confirmation",
                    confidence=Decimal("0.9600"),
                    attachment_filename="booking_confirmation_mscu1234567.pdf",
                ),
                IngestFactRequest(
                    field_name="etd",
                    field_value="2026-06-06",
                    normalized_value="2026-06-06",
                    container_no="MSCU1234567",
                    source_type="pdf_text",
                    source_label="ETD: 2026-06-06",
                    document_type="booking_confirmation",
                    confidence=Decimal("0.9600"),
                    attachment_filename="booking_confirmation_mscu1234567.pdf",
                ),
                IngestFactRequest(
                    field_name="status_text",
                    field_value="Đã xác nhận booking",
                    normalized_value="Đã xác nhận booking",
                    container_no="MSCU1234567",
                    source_type="email_body",
                    source_label="Container MSCU1234567 đã được đặt chỗ.",
                    document_type="booking_confirmation",
                    confidence=Decimal("0.9500"),
                ),
            ],
        ),
        ProcessedEmailIngestRequest(
            gmail_connection_id=gmail_connection_id,
            sync_job_id=sync_job_id,
            gmail_message_id="demo-msg-002",
            gmail_thread_id="demo-thread-001",
            subject="Arrival Notice - MSCU1234567 - ETA 2026-06-12",
            from_email="arrival@maersk-demo.com",
            to_emails=["cs@agentify.vn"],
            sent_at=_dt("2026-06-08T03:40:00Z"),
            snippet="Thông báo hàng đến cho MSCU1234567, ETA ngày 12/06.",
            body_text="Vui lòng xem thông báo hàng đến đính kèm cho container MSCU1234567.",
            raw_labels=["INBOX", "ARRIVAL"],
            has_pdf_attachments=True,
            attachments=[
                IngestAttachmentRequest(
                    gmail_attachment_id="demo-att-002",
                    filename="arrival_notice_mscu1234567_v1.pdf",
                    mime_type="application/pdf",
                    size_bytes=148_210,
                    storage_path="/demo/arrival_notice_mscu1234567_v1.pdf",
                    is_text_pdf=True,
                    text_extract_status="extracted",
                    extracted_text=(
                        "Container No: MSCU1234567\n"
                        "B/L No: HLCUSHA250601234\n"
                        "ETA: 2026-06-12\n"
                        "Status: Da nhan thong bao hang den"
                    ),
                    document_type="arrival_notice",
                )
            ],
            extracted_facts=[
                IngestFactRequest(
                    field_name="container_no",
                    field_value="MSCU1234567",
                    normalized_value="MSCU1234567",
                    container_no="MSCU1234567",
                    source_type="email_subject",
                    source_label="Arrival Notice - MSCU1234567 - ETA 2026-06-12",
                    document_type="arrival_notice",
                    confidence=Decimal("0.9900"),
                ),
                IngestFactRequest(
                    field_name="bl_no",
                    field_value="HLCUSHA250601234",
                    normalized_value="HLCUSHA250601234",
                    container_no="MSCU1234567",
                    source_type="pdf_text",
                    source_label="B/L No: HLCUSHA250601234",
                    document_type="arrival_notice",
                    confidence=Decimal("0.9800"),
                    attachment_filename="arrival_notice_mscu1234567_v1.pdf",
                ),
                IngestFactRequest(
                    field_name="eta",
                    field_value="2026-06-12",
                    normalized_value="2026-06-12",
                    container_no="MSCU1234567",
                    source_type="pdf_text",
                    source_label="ETA: 2026-06-12",
                    document_type="arrival_notice",
                    confidence=Decimal("0.9800"),
                    attachment_filename="arrival_notice_mscu1234567_v1.pdf",
                ),
                IngestFactRequest(
                    field_name="status_text",
                    field_value="Đã nhận thông báo hàng đến",
                    normalized_value="Đã nhận thông báo hàng đến",
                    container_no="MSCU1234567",
                    source_type="pdf_text",
                    source_label="Status: Da nhan thong bao hang den",
                    document_type="arrival_notice",
                    confidence=Decimal("0.9600"),
                    attachment_filename="arrival_notice_mscu1234567_v1.pdf",
                ),
            ],
        ),
        ProcessedEmailIngestRequest(
            gmail_connection_id=gmail_connection_id,
            sync_job_id=sync_job_id,
            gmail_message_id="demo-msg-003",
            gmail_thread_id="demo-thread-001",
            subject="Revised Arrival Notice - MSCU1234567 - ETA 2026-06-14",
            from_email="arrival@maersk-demo.com",
            to_emails=["cs@agentify.vn"],
            sent_at=_dt("2026-06-09T05:10:00Z"),
            snippet="ETA của MSCU1234567 đã được cập nhật sang ngày 14/06.",
            body_text="ETA đã được điều chỉnh do ùn tắc cảng.",
            raw_labels=["INBOX", "ARRIVAL"],
            has_pdf_attachments=True,
            attachments=[
                IngestAttachmentRequest(
                    gmail_attachment_id="demo-att-003",
                    filename="arrival_notice_mscu1234567_v2.pdf",
                    mime_type="application/pdf",
                    size_bytes=149_882,
                    storage_path="/demo/arrival_notice_mscu1234567_v2.pdf",
                    is_text_pdf=True,
                    text_extract_status="extracted",
                    extracted_text=(
                        "Container No: MSCU1234567\n"
                        "ETA revised: 2026-06-14\n"
                        "Status: ETA da dieu chinh do un tac cang"
                    ),
                    document_type="arrival_notice",
                )
            ],
            extracted_facts=[
                IngestFactRequest(
                    field_name="container_no",
                    field_value="MSCU1234567",
                    normalized_value="MSCU1234567",
                    container_no="MSCU1234567",
                    source_type="email_subject",
                    source_label="Revised Arrival Notice - MSCU1234567 - ETA 2026-06-14",
                    document_type="arrival_notice",
                    confidence=Decimal("0.9900"),
                ),
                IngestFactRequest(
                    field_name="eta",
                    field_value="2026-06-14",
                    normalized_value="2026-06-14",
                    container_no="MSCU1234567",
                    source_type="pdf_text",
                    source_label="ETA revised: 2026-06-14",
                    document_type="arrival_notice",
                    confidence=Decimal("0.9800"),
                    attachment_filename="arrival_notice_mscu1234567_v2.pdf",
                ),
                IngestFactRequest(
                    field_name="status_text",
                    field_value="ETA đã điều chỉnh do ùn tắc cảng",
                    normalized_value="ETA đã điều chỉnh do ùn tắc cảng",
                    container_no="MSCU1234567",
                    source_type="pdf_text",
                    source_label="Status: ETA da dieu chinh do un tac cang",
                    document_type="arrival_notice",
                    confidence=Decimal("0.9700"),
                    attachment_filename="arrival_notice_mscu1234567_v2.pdf",
                ),
            ],
        ),
        ProcessedEmailIngestRequest(
            gmail_connection_id=gmail_connection_id,
            sync_job_id=sync_job_id,
            gmail_message_id="demo-msg-004",
            gmail_thread_id="demo-thread-002",
            subject="Shipping Instruction - TGHU7654321 - PO 450012345",
            from_email="docs@shipper-demo.com",
            to_emails=["docs@agentify.vn"],
            sent_at=_dt("2026-06-07T01:25:00Z"),
            snippet="Hướng dẫn giao hàng cho TGHU7654321.",
            body_text="Vui lòng xử lý SI cho container TGHU7654321.",
            raw_labels=["INBOX", "DOCS"],
            has_pdf_attachments=True,
            attachments=[
                IngestAttachmentRequest(
                    gmail_attachment_id="demo-att-004",
                    filename="shipping_instruction_tghu7654321.pdf",
                    mime_type="application/pdf",
                    size_bytes=175_320,
                    storage_path="/demo/shipping_instruction_tghu7654321.pdf",
                    is_text_pdf=True,
                    text_extract_status="extracted",
                    extracted_text=(
                        "Container: TGHU7654321\n"
                        "PO No: 450012345\n"
                        "Booking No: BKG-99100\n"
                        "POL: Ningbo\n"
                        "POD: Ho Chi Minh\n"
                        "Vessel/Voyage: ONE FOCUS / 019S"
                    ),
                    document_type="shipping_instruction",
                )
            ],
            extracted_facts=[
                IngestFactRequest(
                    field_name="container_no",
                    field_value="TGHU7654321",
                    normalized_value="TGHU7654321",
                    container_no="TGHU7654321",
                    source_type="email_subject",
                    source_label="Shipping Instruction - TGHU7654321 - PO 450012345",
                    document_type="shipping_instruction",
                    confidence=Decimal("0.9900"),
                ),
                IngestFactRequest(
                    field_name="po_no",
                    field_value="450012345",
                    normalized_value="450012345",
                    container_no="TGHU7654321",
                    source_type="pdf_text",
                    source_label="PO No: 450012345",
                    document_type="shipping_instruction",
                    confidence=Decimal("0.9800"),
                    attachment_filename="shipping_instruction_tghu7654321.pdf",
                ),
                IngestFactRequest(
                    field_name="booking_no",
                    field_value="BKG-99100",
                    normalized_value="BKG-99100",
                    container_no="TGHU7654321",
                    source_type="pdf_text",
                    source_label="Booking No: BKG-99100",
                    document_type="shipping_instruction",
                    confidence=Decimal("0.9700"),
                    attachment_filename="shipping_instruction_tghu7654321.pdf",
                ),
                IngestFactRequest(
                    field_name="pol",
                    field_value="Ningbo",
                    normalized_value="Ningbo",
                    container_no="TGHU7654321",
                    source_type="pdf_text",
                    source_label="POL: Ningbo",
                    document_type="shipping_instruction",
                    confidence=Decimal("0.9700"),
                    attachment_filename="shipping_instruction_tghu7654321.pdf",
                ),
                IngestFactRequest(
                    field_name="pod",
                    field_value="Ho Chi Minh",
                    normalized_value="Ho Chi Minh",
                    container_no="TGHU7654321",
                    source_type="pdf_text",
                    source_label="POD: Ho Chi Minh",
                    document_type="shipping_instruction",
                    confidence=Decimal("0.9700"),
                    attachment_filename="shipping_instruction_tghu7654321.pdf",
                ),
                IngestFactRequest(
                    field_name="vessel",
                    field_value="ONE FOCUS",
                    normalized_value="ONE FOCUS",
                    container_no="TGHU7654321",
                    source_type="pdf_text",
                    source_label="Vessel/Voyage: ONE FOCUS / 019S",
                    document_type="shipping_instruction",
                    confidence=Decimal("0.9700"),
                    attachment_filename="shipping_instruction_tghu7654321.pdf",
                ),
                IngestFactRequest(
                    field_name="voyage",
                    field_value="019S",
                    normalized_value="019S",
                    container_no="TGHU7654321",
                    source_type="pdf_text",
                    source_label="Vessel/Voyage: ONE FOCUS / 019S",
                    document_type="shipping_instruction",
                    confidence=Decimal("0.9700"),
                    attachment_filename="shipping_instruction_tghu7654321.pdf",
                ),
                IngestFactRequest(
                    field_name="status_text",
                    field_value="Đã nhận hướng dẫn giao hàng",
                    normalized_value="Đã nhận hướng dẫn giao hàng",
                    container_no="TGHU7654321",
                    source_type="email_body",
                    source_label="Vui lòng xử lý SI cho container TGHU7654321.",
                    document_type="shipping_instruction",
                    confidence=Decimal("0.9400"),
                ),
            ],
        ),
        ProcessedEmailIngestRequest(
            gmail_connection_id=gmail_connection_id,
            sync_job_id=sync_job_id,
            gmail_message_id="demo-msg-005",
            gmail_thread_id="demo-thread-002",
            subject="Draft BL - TGHU7654321 - BL OOLUNB26060077",
            from_email="docs@carrier-demo.com",
            to_emails=["docs@agentify.vn"],
            sent_at=_dt("2026-06-08T10:55:00Z"),
            snippet="Đã đính kèm bản nháp vận đơn cho TGHU7654321.",
            body_text="Bản nháp vận đơn gửi để kiểm tra.",
            raw_labels=["INBOX", "DOCS"],
            has_pdf_attachments=True,
            attachments=[
                IngestAttachmentRequest(
                    gmail_attachment_id="demo-att-005",
                    filename="draft_bl_tghu7654321.pdf",
                    mime_type="application/pdf",
                    size_bytes=196_480,
                    storage_path="/demo/draft_bl_tghu7654321.pdf",
                    is_text_pdf=True,
                    text_extract_status="extracted",
                    extracted_text=(
                        "Container No: TGHU7654321\n"
                        "B/L No: OOLUNB26060077\n"
                        "Seal No: SL998821\n"
                        "ETD: 2026-06-10\n"
                        "ETA: 2026-06-15"
                    ),
                    document_type="draft_bl",
                )
            ],
            extracted_facts=[
                IngestFactRequest(
                    field_name="container_no",
                    field_value="TGHU7654321",
                    normalized_value="TGHU7654321",
                    container_no="TGHU7654321",
                    source_type="email_subject",
                    source_label="Draft BL - TGHU7654321 - BL OOLUNB26060077",
                    document_type="draft_bl",
                    confidence=Decimal("0.9900"),
                ),
                IngestFactRequest(
                    field_name="bl_no",
                    field_value="OOLUNB26060077",
                    normalized_value="OOLUNB26060077",
                    container_no="TGHU7654321",
                    source_type="pdf_text",
                    source_label="B/L No: OOLUNB26060077",
                    document_type="draft_bl",
                    confidence=Decimal("0.9800"),
                    attachment_filename="draft_bl_tghu7654321.pdf",
                ),
                IngestFactRequest(
                    field_name="seal_no",
                    field_value="SL998821",
                    normalized_value="SL998821",
                    container_no="TGHU7654321",
                    source_type="pdf_text",
                    source_label="Seal No: SL998821",
                    document_type="draft_bl",
                    confidence=Decimal("0.9700"),
                    attachment_filename="draft_bl_tghu7654321.pdf",
                ),
                IngestFactRequest(
                    field_name="etd",
                    field_value="2026-06-10",
                    normalized_value="2026-06-10",
                    container_no="TGHU7654321",
                    source_type="pdf_text",
                    source_label="ETD: 2026-06-10",
                    document_type="draft_bl",
                    confidence=Decimal("0.9700"),
                    attachment_filename="draft_bl_tghu7654321.pdf",
                ),
                IngestFactRequest(
                    field_name="eta",
                    field_value="2026-06-15",
                    normalized_value="2026-06-15",
                    container_no="TGHU7654321",
                    source_type="pdf_text",
                    source_label="ETA: 2026-06-15",
                    document_type="draft_bl",
                    confidence=Decimal("0.9700"),
                    attachment_filename="draft_bl_tghu7654321.pdf",
                ),
                IngestFactRequest(
                    field_name="status_text",
                    field_value="Đã nhận bản nháp vận đơn",
                    normalized_value="Đã nhận bản nháp vận đơn",
                    container_no="TGHU7654321",
                    source_type="email_body",
                    source_label="Bản nháp vận đơn gửi để kiểm tra.",
                    document_type="draft_bl",
                    confidence=Decimal("0.9400"),
                ),
            ],
        ),
        ProcessedEmailIngestRequest(
            gmail_connection_id=gmail_connection_id,
            sync_job_id=sync_job_id,
            gmail_message_id="demo-msg-006",
            gmail_thread_id="demo-thread-003",
            subject="Delivery Order Release - OOLU9988776",
            from_email="release@forwarder-demo.com",
            to_emails=["account@agentify.vn"],
            sent_at=_dt("2026-06-08T13:20:00Z"),
            snippet="Đã phát hành lệnh giao hàng cho OOLU9988776.",
            body_text="Lệnh giao hàng đã được phát hành sau khi xác nhận thanh toán.",
            raw_labels=["INBOX", "RELEASE"],
            has_pdf_attachments=True,
            attachments=[
                IngestAttachmentRequest(
                    gmail_attachment_id="demo-att-006",
                    filename="delivery_order_oolu9988776.pdf",
                    mime_type="application/pdf",
                    size_bytes=126_940,
                    storage_path="/demo/delivery_order_oolu9988776.pdf",
                    is_text_pdf=True,
                    text_extract_status="extracted",
                    extracted_text=(
                        "Container No: OOLU9988776\n"
                        "Booking No: BKG-55678\n"
                        "B/L No: EMCNSZX26061199\n"
                        "POD: Cat Lai\n"
                        "Status: Da phat hanh lenh giao hang"
                    ),
                    document_type="delivery_order",
                )
            ],
            extracted_facts=[
                IngestFactRequest(
                    field_name="container_no",
                    field_value="OOLU9988776",
                    normalized_value="OOLU9988776",
                    container_no="OOLU9988776",
                    source_type="email_subject",
                    source_label="Delivery Order Release - OOLU9988776",
                    document_type="delivery_order",
                    confidence=Decimal("0.9900"),
                ),
                IngestFactRequest(
                    field_name="booking_no",
                    field_value="BKG-55678",
                    normalized_value="BKG-55678",
                    container_no="OOLU9988776",
                    source_type="pdf_text",
                    source_label="Booking No: BKG-55678",
                    document_type="delivery_order",
                    confidence=Decimal("0.9700"),
                    attachment_filename="delivery_order_oolu9988776.pdf",
                ),
                IngestFactRequest(
                    field_name="bl_no",
                    field_value="EMCNSZX26061199",
                    normalized_value="EMCNSZX26061199",
                    container_no="OOLU9988776",
                    source_type="pdf_text",
                    source_label="B/L No: EMCNSZX26061199",
                    document_type="delivery_order",
                    confidence=Decimal("0.9700"),
                    attachment_filename="delivery_order_oolu9988776.pdf",
                ),
                IngestFactRequest(
                    field_name="pod",
                    field_value="Cat Lai",
                    normalized_value="Cat Lai",
                    container_no="OOLU9988776",
                    source_type="pdf_text",
                    source_label="POD: Cat Lai",
                    document_type="delivery_order",
                    confidence=Decimal("0.9600"),
                    attachment_filename="delivery_order_oolu9988776.pdf",
                ),
                IngestFactRequest(
                    field_name="status_text",
                    field_value="Đã phát hành lệnh giao hàng",
                    normalized_value="Đã phát hành lệnh giao hàng",
                    container_no="OOLU9988776",
                    source_type="pdf_text",
                    source_label="Status: Da phat hanh lenh giao hang",
                    document_type="delivery_order",
                    confidence=Decimal("0.9600"),
                    attachment_filename="delivery_order_oolu9988776.pdf",
                ),
            ],
        ),
        ProcessedEmailIngestRequest(
            gmail_connection_id=gmail_connection_id,
            sync_job_id=sync_job_id,
            gmail_message_id="demo-msg-007",
            gmail_thread_id="demo-thread-004",
            subject="Booking Note - WHLU4455667",
            from_email="ops@carrier-demo.com",
            to_emails=["ops@agentify.vn"],
            sent_at=_dt("2026-06-09T02:20:00Z"),
            snippet="Đã nhận booking note cho WHLU4455667, chưa thấy ETA.",
            body_text="Container WHLU4455667 đã có booking. Chưa có ETA và chưa có B/L.",
            raw_labels=["INBOX", "LOGISTICS"],
            has_pdf_attachments=True,
            attachments=[
                IngestAttachmentRequest(
                    gmail_attachment_id="demo-att-007",
                    filename="booking_note_whlu4455667.pdf",
                    mime_type="application/pdf",
                    size_bytes=118_210,
                    storage_path="/demo/booking_note_whlu4455667.pdf",
                    is_text_pdf=True,
                    text_extract_status="extracted",
                    extracted_text=(
                        "Container No: WHLU4455667\n"
                        "Booking No: BKG-77220\n"
                        "POL: Yantian\n"
                        "POD: Hai Phong\n"
                        "Status: Dang cho hang tau cap ETA"
                    ),
                    document_type="booking_confirmation",
                )
            ],
            extracted_facts=[
                IngestFactRequest(
                    field_name="container_no",
                    field_value="WHLU4455667",
                    normalized_value="WHLU4455667",
                    container_no="WHLU4455667",
                    source_type="email_subject",
                    source_label="Booking Note - WHLU4455667",
                    document_type="booking_confirmation",
                    confidence=Decimal("0.9900"),
                ),
                IngestFactRequest(
                    field_name="booking_no",
                    field_value="BKG-77220",
                    normalized_value="BKG-77220",
                    container_no="WHLU4455667",
                    source_type="pdf_text",
                    source_label="Booking No: BKG-77220",
                    document_type="booking_confirmation",
                    confidence=Decimal("0.9700"),
                    attachment_filename="booking_note_whlu4455667.pdf",
                ),
                IngestFactRequest(
                    field_name="pol",
                    field_value="Yantian",
                    normalized_value="Yantian",
                    container_no="WHLU4455667",
                    source_type="pdf_text",
                    source_label="POL: Yantian",
                    document_type="booking_confirmation",
                    confidence=Decimal("0.9600"),
                    attachment_filename="booking_note_whlu4455667.pdf",
                ),
                IngestFactRequest(
                    field_name="pod",
                    field_value="Hai Phong",
                    normalized_value="Hai Phong",
                    container_no="WHLU4455667",
                    source_type="pdf_text",
                    source_label="POD: Hai Phong",
                    document_type="booking_confirmation",
                    confidence=Decimal("0.9600"),
                    attachment_filename="booking_note_whlu4455667.pdf",
                ),
                IngestFactRequest(
                    field_name="status_text",
                    field_value="Đang chờ hãng tàu cấp ETA",
                    normalized_value="Đang chờ hãng tàu cấp ETA",
                    container_no="WHLU4455667",
                    source_type="pdf_text",
                    source_label="Status: Dang cho hang tau cap ETA",
                    document_type="booking_confirmation",
                    confidence=Decimal("0.9500"),
                    attachment_filename="booking_note_whlu4455667.pdf",
                ),
            ],
        ),
        ProcessedEmailIngestRequest(
            gmail_connection_id=gmail_connection_id,
            sync_job_id=sync_job_id,
            gmail_message_id="demo-msg-008",
            gmail_thread_id="demo-thread-005",
            subject="Booking Request Received - CAIU7788990",
            from_email="sales@shipper-demo.com",
            to_emails=["cs@agentify.vn"],
            sent_at=_dt("2026-06-09T03:05:00Z"),
            snippet="Mới nhận email booking cho CAIU7788990, chưa có file đính kèm.",
            body_text=(
                "Khách vừa gửi yêu cầu đặt chỗ cho container CAIU7788990. "
                "Chỉ mới nhận email đặt chỗ, chưa có file PDF."
            ),
            raw_labels=["INBOX", "LOGISTICS"],
            has_pdf_attachments=False,
            attachments=[],
            extracted_facts=[
                IngestFactRequest(
                    field_name="container_no",
                    field_value="CAIU7788990",
                    normalized_value="CAIU7788990",
                    container_no="CAIU7788990",
                    source_type="email_subject",
                    source_label="Booking Request Received - CAIU7788990",
                    document_type="booking_confirmation",
                    confidence=Decimal("0.9900"),
                ),
                IngestFactRequest(
                    field_name="status_text",
                    field_value="Chỉ mới nhận email đặt chỗ, chưa có file PDF",
                    normalized_value="Chỉ mới nhận email đặt chỗ, chưa có file PDF",
                    container_no="CAIU7788990",
                    source_type="email_body",
                    source_label="Chỉ mới nhận email đặt chỗ, chưa có file PDF.",
                    document_type="booking_confirmation",
                    confidence=Decimal("0.9200"),
                ),
            ],
        ),
        ProcessedEmailIngestRequest(
            gmail_connection_id=gmail_connection_id,
            sync_job_id=sync_job_id,
            gmail_message_id="demo-msg-009",
            gmail_thread_id="demo-thread-006",
            subject="Booking Confirmation - SEGU5566778 - BKG-66001",
            from_email="booking@one-demo.com",
            to_emails=["ops@agentify.vn"],
            sent_at=_dt("2026-06-06T07:50:00Z"),
            snippet="Đã xác nhận booking cho SEGU5566778.",
            body_text="Container SEGU5566778 đã được đặt chỗ, ETD dự kiến ngày 08/06.",
            raw_labels=["INBOX", "LOGISTICS"],
            has_pdf_attachments=True,
            attachments=[
                IngestAttachmentRequest(
                    gmail_attachment_id="demo-att-008",
                    filename="booking_confirmation_segu5566778.pdf",
                    mime_type="application/pdf",
                    size_bytes=145_920,
                    storage_path="/demo/booking_confirmation_segu5566778.pdf",
                    is_text_pdf=True,
                    text_extract_status="extracted",
                    extracted_text=(
                        "Container No: SEGU5566778\n"
                        "Booking No: BKG-66001\n"
                        "POL: Shekou\n"
                        "POD: Cat Lai\n"
                        "ETD: 2026-06-08\n"
                        "Vessel/Voyage: ONE INTEGRITY / 031S"
                    ),
                    document_type="booking_confirmation",
                )
            ],
            extracted_facts=[
                IngestFactRequest(
                    field_name="container_no",
                    field_value="SEGU5566778",
                    normalized_value="SEGU5566778",
                    container_no="SEGU5566778",
                    source_type="email_subject",
                    source_label="Booking Confirmation - SEGU5566778 - BKG-66001",
                    document_type="booking_confirmation",
                    confidence=Decimal("0.9900"),
                ),
                IngestFactRequest(
                    field_name="booking_no",
                    field_value="BKG-66001",
                    normalized_value="BKG-66001",
                    container_no="SEGU5566778",
                    source_type="pdf_text",
                    source_label="Booking No: BKG-66001",
                    document_type="booking_confirmation",
                    confidence=Decimal("0.9800"),
                    attachment_filename="booking_confirmation_segu5566778.pdf",
                ),
                IngestFactRequest(
                    field_name="pol",
                    field_value="Shekou",
                    normalized_value="Shekou",
                    container_no="SEGU5566778",
                    source_type="pdf_text",
                    source_label="POL: Shekou",
                    document_type="booking_confirmation",
                    confidence=Decimal("0.9600"),
                    attachment_filename="booking_confirmation_segu5566778.pdf",
                ),
                IngestFactRequest(
                    field_name="pod",
                    field_value="Cat Lai",
                    normalized_value="Cat Lai",
                    container_no="SEGU5566778",
                    source_type="pdf_text",
                    source_label="POD: Cat Lai",
                    document_type="booking_confirmation",
                    confidence=Decimal("0.9600"),
                    attachment_filename="booking_confirmation_segu5566778.pdf",
                ),
                IngestFactRequest(
                    field_name="etd",
                    field_value="2026-06-08",
                    normalized_value="2026-06-08",
                    container_no="SEGU5566778",
                    source_type="pdf_text",
                    source_label="ETD: 2026-06-08",
                    document_type="booking_confirmation",
                    confidence=Decimal("0.9600"),
                    attachment_filename="booking_confirmation_segu5566778.pdf",
                ),
                IngestFactRequest(
                    field_name="vessel",
                    field_value="ONE INTEGRITY",
                    normalized_value="ONE INTEGRITY",
                    container_no="SEGU5566778",
                    source_type="pdf_text",
                    source_label="Vessel/Voyage: ONE INTEGRITY / 031S",
                    document_type="booking_confirmation",
                    confidence=Decimal("0.9600"),
                    attachment_filename="booking_confirmation_segu5566778.pdf",
                ),
                IngestFactRequest(
                    field_name="voyage",
                    field_value="031S",
                    normalized_value="031S",
                    container_no="SEGU5566778",
                    source_type="pdf_text",
                    source_label="Vessel/Voyage: ONE INTEGRITY / 031S",
                    document_type="booking_confirmation",
                    confidence=Decimal("0.9600"),
                    attachment_filename="booking_confirmation_segu5566778.pdf",
                ),
                IngestFactRequest(
                    field_name="status_text",
                    field_value="Đã xác nhận booking, chờ thông báo hàng đến",
                    normalized_value="Đã xác nhận booking, chờ thông báo hàng đến",
                    container_no="SEGU5566778",
                    source_type="email_body",
                    source_label="Container SEGU5566778 đã được đặt chỗ, ETD dự kiến ngày 08/06.",
                    document_type="booking_confirmation",
                    confidence=Decimal("0.9400"),
                ),
            ],
        ),
        ProcessedEmailIngestRequest(
            gmail_connection_id=gmail_connection_id,
            sync_job_id=sync_job_id,
            gmail_message_id="demo-msg-010",
            gmail_thread_id="demo-thread-006",
            subject="Arrival Notice - SEGU5566778 - ETA 2026-06-13",
            from_email="arrival@one-demo.com",
            to_emails=["cs@agentify.vn"],
            sent_at=_dt("2026-06-09T04:15:00Z"),
            snippet="Thông báo hàng đến cho SEGU5566778, ETA ngày 13/06.",
            body_text="SEGU5566778 đã có thông báo hàng đến, ETA hiện là ngày 13/06.",
            raw_labels=["INBOX", "ARRIVAL"],
            has_pdf_attachments=True,
            attachments=[
                IngestAttachmentRequest(
                    gmail_attachment_id="demo-att-009",
                    filename="arrival_notice_segu5566778.pdf",
                    mime_type="application/pdf",
                    size_bytes=132_884,
                    storage_path="/demo/arrival_notice_segu5566778.pdf",
                    is_text_pdf=True,
                    text_extract_status="extracted",
                    extracted_text=(
                        "Container No: SEGU5566778\n"
                        "ETA: 2026-06-13\n"
                        "B/L No: ONECATL26061355\n"
                        "Status: Da nhan thong bao hang den"
                    ),
                    document_type="arrival_notice",
                )
            ],
            extracted_facts=[
                IngestFactRequest(
                    field_name="container_no",
                    field_value="SEGU5566778",
                    normalized_value="SEGU5566778",
                    container_no="SEGU5566778",
                    source_type="email_subject",
                    source_label="Arrival Notice - SEGU5566778 - ETA 2026-06-13",
                    document_type="arrival_notice",
                    confidence=Decimal("0.9900"),
                ),
                IngestFactRequest(
                    field_name="eta",
                    field_value="2026-06-13",
                    normalized_value="2026-06-13",
                    container_no="SEGU5566778",
                    source_type="pdf_text",
                    source_label="ETA: 2026-06-13",
                    document_type="arrival_notice",
                    confidence=Decimal("0.9800"),
                    attachment_filename="arrival_notice_segu5566778.pdf",
                ),
                IngestFactRequest(
                    field_name="bl_no",
                    field_value="ONECATL26061355",
                    normalized_value="ONECATL26061355",
                    container_no="SEGU5566778",
                    source_type="pdf_text",
                    source_label="B/L No: ONECATL26061355",
                    document_type="arrival_notice",
                    confidence=Decimal("0.9700"),
                    attachment_filename="arrival_notice_segu5566778.pdf",
                ),
                IngestFactRequest(
                    field_name="status_text",
                    field_value="Đã nhận thông báo hàng đến",
                    normalized_value="Đã nhận thông báo hàng đến",
                    container_no="SEGU5566778",
                    source_type="pdf_text",
                    source_label="Status: Da nhan thong bao hang den",
                    document_type="arrival_notice",
                    confidence=Decimal("0.9600"),
                    attachment_filename="arrival_notice_segu5566778.pdf",
                ),
            ],
        ),
        ProcessedEmailIngestRequest(
            gmail_connection_id=gmail_connection_id,
            sync_job_id=sync_job_id,
            gmail_message_id="demo-msg-011",
            gmail_thread_id="demo-thread-007",
            subject="Delivery Order Advice - TRHU3344556",
            from_email="release@forwarder-demo.com",
            to_emails=["account@agentify.vn"],
            sent_at=_dt("2026-06-09T06:40:00Z"),
            snippet="Đã có lệnh giao hàng cho TRHU3344556.",
            body_text="TRHU3344556 đã có lệnh giao hàng, nhưng chưa thấy booking và ETA.",
            raw_labels=["INBOX", "RELEASE"],
            has_pdf_attachments=True,
            attachments=[
                IngestAttachmentRequest(
                    gmail_attachment_id="demo-att-010",
                    filename="delivery_order_trhu3344556.pdf",
                    mime_type="application/pdf",
                    size_bytes=121_330,
                    storage_path="/demo/delivery_order_trhu3344556.pdf",
                    is_text_pdf=True,
                    text_extract_status="extracted",
                    extracted_text=(
                        "Container No: TRHU3344556\n"
                        "B/L No: SITGN26061118\n"
                        "POD: Da Nang\n"
                        "Status: Da co lenh giao hang"
                    ),
                    document_type="delivery_order",
                )
            ],
            extracted_facts=[
                IngestFactRequest(
                    field_name="container_no",
                    field_value="TRHU3344556",
                    normalized_value="TRHU3344556",
                    container_no="TRHU3344556",
                    source_type="email_subject",
                    source_label="Delivery Order Advice - TRHU3344556",
                    document_type="delivery_order",
                    confidence=Decimal("0.9900"),
                ),
                IngestFactRequest(
                    field_name="bl_no",
                    field_value="SITGN26061118",
                    normalized_value="SITGN26061118",
                    container_no="TRHU3344556",
                    source_type="pdf_text",
                    source_label="B/L No: SITGN26061118",
                    document_type="delivery_order",
                    confidence=Decimal("0.9700"),
                    attachment_filename="delivery_order_trhu3344556.pdf",
                ),
                IngestFactRequest(
                    field_name="pod",
                    field_value="Da Nang",
                    normalized_value="Da Nang",
                    container_no="TRHU3344556",
                    source_type="pdf_text",
                    source_label="POD: Da Nang",
                    document_type="delivery_order",
                    confidence=Decimal("0.9600"),
                    attachment_filename="delivery_order_trhu3344556.pdf",
                ),
                IngestFactRequest(
                    field_name="status_text",
                    field_value="Đã có lệnh giao hàng, chưa thấy booking và ETA",
                    normalized_value="Đã có lệnh giao hàng, chưa thấy booking và ETA",
                    container_no="TRHU3344556",
                    source_type="email_body",
                    source_label="TRHU3344556 đã có lệnh giao hàng, nhưng chưa thấy booking và ETA.",
                    document_type="delivery_order",
                    confidence=Decimal("0.9500"),
                ),
            ],
        ),
        ProcessedEmailIngestRequest(
            gmail_connection_id=gmail_connection_id,
            sync_job_id=sync_job_id,
            gmail_message_id="demo-msg-012",
            gmail_thread_id="demo-thread-008",
            subject="Booking Confirmation - FSCU2211334 - BKG-99001",
            from_email="booking@maersk-demo.com",
            to_emails=["ops@agentify.vn"],
            sent_at=_dt("2026-06-08T06:25:00Z"),
            snippet="Đã xác nhận booking đầy đủ cho FSCU2211334.",
            body_text="Container FSCU2211334 đã được xác nhận booking, chờ tàu chạy.",
            raw_labels=["INBOX", "LOGISTICS"],
            has_pdf_attachments=True,
            attachments=[
                IngestAttachmentRequest(
                    gmail_attachment_id="demo-att-011",
                    filename="booking_confirmation_fscu2211334.pdf",
                    mime_type="application/pdf",
                    size_bytes=201_105,
                    storage_path="/demo/booking_confirmation_fscu2211334.pdf",
                    is_text_pdf=True,
                    text_extract_status="extracted",
                    extracted_text=(
                        "Container No: FSCU2211334\n"
                        "Booking No: BKG-99001\n"
                        "PO No: 450077889\n"
                        "Seal No: SL332211\n"
                        "POL: Shanghai\n"
                        "POD: Cat Lai\n"
                        "Vessel/Voyage: MAERSK SAIGON / 028S\n"
                        "ETD: 2026-06-08"
                    ),
                    document_type="booking_confirmation",
                )
            ],
            extracted_facts=[
                IngestFactRequest(
                    field_name="container_no",
                    field_value="FSCU2211334",
                    normalized_value="FSCU2211334",
                    container_no="FSCU2211334",
                    source_type="email_subject",
                    source_label="Booking Confirmation - FSCU2211334 - BKG-99001",
                    document_type="booking_confirmation",
                    confidence=Decimal("0.9900"),
                ),
                IngestFactRequest(
                    field_name="booking_no",
                    field_value="BKG-99001",
                    normalized_value="BKG-99001",
                    container_no="FSCU2211334",
                    source_type="pdf_text",
                    source_label="Booking No: BKG-99001",
                    document_type="booking_confirmation",
                    confidence=Decimal("0.9800"),
                    attachment_filename="booking_confirmation_fscu2211334.pdf",
                ),
                IngestFactRequest(
                    field_name="po_no",
                    field_value="450077889",
                    normalized_value="450077889",
                    container_no="FSCU2211334",
                    source_type="pdf_text",
                    source_label="PO No: 450077889",
                    document_type="booking_confirmation",
                    confidence=Decimal("0.9700"),
                    attachment_filename="booking_confirmation_fscu2211334.pdf",
                ),
                IngestFactRequest(
                    field_name="seal_no",
                    field_value="SL332211",
                    normalized_value="SL332211",
                    container_no="FSCU2211334",
                    source_type="pdf_text",
                    source_label="Seal No: SL332211",
                    document_type="booking_confirmation",
                    confidence=Decimal("0.9700"),
                    attachment_filename="booking_confirmation_fscu2211334.pdf",
                ),
                IngestFactRequest(
                    field_name="pol",
                    field_value="Shanghai",
                    normalized_value="Shanghai",
                    container_no="FSCU2211334",
                    source_type="pdf_text",
                    source_label="POL: Shanghai",
                    document_type="booking_confirmation",
                    confidence=Decimal("0.9600"),
                    attachment_filename="booking_confirmation_fscu2211334.pdf",
                ),
                IngestFactRequest(
                    field_name="pod",
                    field_value="Cat Lai",
                    normalized_value="Cat Lai",
                    container_no="FSCU2211334",
                    source_type="pdf_text",
                    source_label="POD: Cat Lai",
                    document_type="booking_confirmation",
                    confidence=Decimal("0.9600"),
                    attachment_filename="booking_confirmation_fscu2211334.pdf",
                ),
                IngestFactRequest(
                    field_name="vessel",
                    field_value="MAERSK SAIGON",
                    normalized_value="MAERSK SAIGON",
                    container_no="FSCU2211334",
                    source_type="pdf_text",
                    source_label="Vessel/Voyage: MAERSK SAIGON / 028S",
                    document_type="booking_confirmation",
                    confidence=Decimal("0.9600"),
                    attachment_filename="booking_confirmation_fscu2211334.pdf",
                ),
                IngestFactRequest(
                    field_name="voyage",
                    field_value="028S",
                    normalized_value="028S",
                    container_no="FSCU2211334",
                    source_type="pdf_text",
                    source_label="Vessel/Voyage: MAERSK SAIGON / 028S",
                    document_type="booking_confirmation",
                    confidence=Decimal("0.9600"),
                    attachment_filename="booking_confirmation_fscu2211334.pdf",
                ),
                IngestFactRequest(
                    field_name="etd",
                    field_value="2026-06-08",
                    normalized_value="2026-06-08",
                    container_no="FSCU2211334",
                    source_type="pdf_text",
                    source_label="ETD: 2026-06-08",
                    document_type="booking_confirmation",
                    confidence=Decimal("0.9600"),
                    attachment_filename="booking_confirmation_fscu2211334.pdf",
                ),
                IngestFactRequest(
                    field_name="status_text",
                    field_value="Chờ tàu khởi hành theo lịch dự kiến",
                    normalized_value="Chờ tàu khởi hành theo lịch dự kiến",
                    container_no="FSCU2211334",
                    source_type="email_body",
                    source_label="Container FSCU2211334 đã được xác nhận booking, chờ tàu chạy.",
                    document_type="booking_confirmation",
                    confidence=Decimal("0.9500"),
                ),
            ],
        ),
        ProcessedEmailIngestRequest(
            gmail_connection_id=gmail_connection_id,
            sync_job_id=sync_job_id,
            gmail_message_id="demo-msg-013",
            gmail_thread_id="demo-thread-008",
            subject="Arrival Notice - FSCU2211334 - ETA 2026-06-12",
            from_email="arrival@maersk-demo.com",
            to_emails=["cs@agentify.vn"],
            sent_at=_dt("2026-06-09T07:15:00Z"),
            snippet="FSCU2211334 đang vận chuyển, ETA ngày 12/06.",
            body_text="Tàu đang vận chuyển về cảng đích, ETA hiện tại là ngày 12/06.",
            raw_labels=["INBOX", "ARRIVAL"],
            has_pdf_attachments=True,
            attachments=[
                IngestAttachmentRequest(
                    gmail_attachment_id="demo-att-012",
                    filename="arrival_notice_fscu2211334.pdf",
                    mime_type="application/pdf",
                    size_bytes=151_220,
                    storage_path="/demo/arrival_notice_fscu2211334.pdf",
                    is_text_pdf=True,
                    text_extract_status="extracted",
                    extracted_text=(
                        "Container No: FSCU2211334\n"
                        "B/L No: MAEU260612345\n"
                        "ETA: 2026-06-12\n"
                        "Status: Dang van chuyen ve cang dich"
                    ),
                    document_type="arrival_notice",
                )
            ],
            extracted_facts=[
                IngestFactRequest(
                    field_name="container_no",
                    field_value="FSCU2211334",
                    normalized_value="FSCU2211334",
                    container_no="FSCU2211334",
                    source_type="email_subject",
                    source_label="Arrival Notice - FSCU2211334 - ETA 2026-06-12",
                    document_type="arrival_notice",
                    confidence=Decimal("0.9900"),
                ),
                IngestFactRequest(
                    field_name="bl_no",
                    field_value="MAEU260612345",
                    normalized_value="MAEU260612345",
                    container_no="FSCU2211334",
                    source_type="pdf_text",
                    source_label="B/L No: MAEU260612345",
                    document_type="arrival_notice",
                    confidence=Decimal("0.9800"),
                    attachment_filename="arrival_notice_fscu2211334.pdf",
                ),
                IngestFactRequest(
                    field_name="eta",
                    field_value="2026-06-12",
                    normalized_value="2026-06-12",
                    container_no="FSCU2211334",
                    source_type="pdf_text",
                    source_label="ETA: 2026-06-12",
                    document_type="arrival_notice",
                    confidence=Decimal("0.9800"),
                    attachment_filename="arrival_notice_fscu2211334.pdf",
                ),
                IngestFactRequest(
                    field_name="status_text",
                    field_value="Đang vận chuyển về cảng đích",
                    normalized_value="Đang vận chuyển về cảng đích",
                    container_no="FSCU2211334",
                    source_type="pdf_text",
                    source_label="Status: Dang van chuyen ve cang dich",
                    document_type="arrival_notice",
                    confidence=Decimal("0.9700"),
                    attachment_filename="arrival_notice_fscu2211334.pdf",
                ),
            ],
        ),
        ProcessedEmailIngestRequest(
            gmail_connection_id=gmail_connection_id,
            sync_job_id=sync_job_id,
            gmail_message_id="demo-msg-014",
            gmail_thread_id="demo-thread-009",
            subject="Export Schedule - CMAU6677889 - ETD 2026-06-11",
            from_email="booking@carrier-demo.com",
            to_emails=["ops@agentify.vn"],
            sent_at=_dt("2026-06-09T07:40:00Z"),
            snippet="CMAU6677889 đang chờ xuất cảng theo lịch ngày 11/06.",
            body_text="Container CMAU6677889 đang chờ xuất cảng, chưa có B/L và ETA.",
            raw_labels=["INBOX", "LOGISTICS"],
            has_pdf_attachments=True,
            attachments=[
                IngestAttachmentRequest(
                    gmail_attachment_id="demo-att-013",
                    filename="export_schedule_cmau6677889.pdf",
                    mime_type="application/pdf",
                    size_bytes=133_540,
                    storage_path="/demo/export_schedule_cmau6677889.pdf",
                    is_text_pdf=True,
                    text_extract_status="extracted",
                    extracted_text=(
                        "Container No: CMAU6677889\n"
                        "Booking No: BKG-77110\n"
                        "POL: Qingdao\n"
                        "POD: Ho Chi Minh\n"
                        "Vessel/Voyage: TSL HAI PHONG / 018S\n"
                        "ETD: 2026-06-11\n"
                        "Status: Cho xuat cang"
                    ),
                    document_type="booking_confirmation",
                )
            ],
            extracted_facts=[
                IngestFactRequest(
                    field_name="container_no",
                    field_value="CMAU6677889",
                    normalized_value="CMAU6677889",
                    container_no="CMAU6677889",
                    source_type="email_subject",
                    source_label="Export Schedule - CMAU6677889 - ETD 2026-06-11",
                    document_type="booking_confirmation",
                    confidence=Decimal("0.9900"),
                ),
                IngestFactRequest(
                    field_name="booking_no",
                    field_value="BKG-77110",
                    normalized_value="BKG-77110",
                    container_no="CMAU6677889",
                    source_type="pdf_text",
                    source_label="Booking No: BKG-77110",
                    document_type="booking_confirmation",
                    confidence=Decimal("0.9700"),
                    attachment_filename="export_schedule_cmau6677889.pdf",
                ),
                IngestFactRequest(
                    field_name="pol",
                    field_value="Qingdao",
                    normalized_value="Qingdao",
                    container_no="CMAU6677889",
                    source_type="pdf_text",
                    source_label="POL: Qingdao",
                    document_type="booking_confirmation",
                    confidence=Decimal("0.9600"),
                    attachment_filename="export_schedule_cmau6677889.pdf",
                ),
                IngestFactRequest(
                    field_name="pod",
                    field_value="Ho Chi Minh",
                    normalized_value="Ho Chi Minh",
                    container_no="CMAU6677889",
                    source_type="pdf_text",
                    source_label="POD: Ho Chi Minh",
                    document_type="booking_confirmation",
                    confidence=Decimal("0.9600"),
                    attachment_filename="export_schedule_cmau6677889.pdf",
                ),
                IngestFactRequest(
                    field_name="vessel",
                    field_value="TSL HAI PHONG",
                    normalized_value="TSL HAI PHONG",
                    container_no="CMAU6677889",
                    source_type="pdf_text",
                    source_label="Vessel/Voyage: TSL HAI PHONG / 018S",
                    document_type="booking_confirmation",
                    confidence=Decimal("0.9600"),
                    attachment_filename="export_schedule_cmau6677889.pdf",
                ),
                IngestFactRequest(
                    field_name="voyage",
                    field_value="018S",
                    normalized_value="018S",
                    container_no="CMAU6677889",
                    source_type="pdf_text",
                    source_label="Vessel/Voyage: TSL HAI PHONG / 018S",
                    document_type="booking_confirmation",
                    confidence=Decimal("0.9600"),
                    attachment_filename="export_schedule_cmau6677889.pdf",
                ),
                IngestFactRequest(
                    field_name="etd",
                    field_value="2026-06-11",
                    normalized_value="2026-06-11",
                    container_no="CMAU6677889",
                    source_type="pdf_text",
                    source_label="ETD: 2026-06-11",
                    document_type="booking_confirmation",
                    confidence=Decimal("0.9600"),
                    attachment_filename="export_schedule_cmau6677889.pdf",
                ),
                IngestFactRequest(
                    field_name="status_text",
                    field_value="Chờ xuất cảng",
                    normalized_value="Chờ xuất cảng",
                    container_no="CMAU6677889",
                    source_type="pdf_text",
                    source_label="Status: Cho xuat cang",
                    document_type="booking_confirmation",
                    confidence=Decimal("0.9500"),
                    attachment_filename="export_schedule_cmau6677889.pdf",
                ),
            ],
        ),
        ProcessedEmailIngestRequest(
            gmail_connection_id=gmail_connection_id,
            sync_job_id=sync_job_id,
            gmail_message_id="demo-msg-015",
            gmail_thread_id="demo-thread-010",
            subject="Customs Update - TEMU5544332",
            from_email="docs@forwarder-demo.com",
            to_emails=["cs@agentify.vn"],
            sent_at=_dt("2026-06-09T08:20:00Z"),
            snippet="TEMU5544332 đang chờ thông quan để lấy lệnh giao hàng.",
            body_text="Container TEMU5544332 đã đến cảng, đang chờ thông quan để lấy lệnh giao hàng.",
            raw_labels=["INBOX", "DOCS"],
            has_pdf_attachments=True,
            attachments=[
                IngestAttachmentRequest(
                    gmail_attachment_id="demo-att-014",
                    filename="customs_update_temu5544332.pdf",
                    mime_type="application/pdf",
                    size_bytes=129_660,
                    storage_path="/demo/customs_update_temu5544332.pdf",
                    is_text_pdf=True,
                    text_extract_status="extracted",
                    extracted_text=(
                        "Container No: TEMU5544332\n"
                        "Booking No: BKG-88012\n"
                        "B/L No: TSLHPH26061588\n"
                        "POD: Hai Phong\n"
                        "ETA: 2026-06-15\n"
                        "Status: Cho thong quan de lay lenh giao hang"
                    ),
                    document_type="arrival_notice",
                )
            ],
            extracted_facts=[
                IngestFactRequest(
                    field_name="container_no",
                    field_value="TEMU5544332",
                    normalized_value="TEMU5544332",
                    container_no="TEMU5544332",
                    source_type="email_subject",
                    source_label="Customs Update - TEMU5544332",
                    document_type="arrival_notice",
                    confidence=Decimal("0.9900"),
                ),
                IngestFactRequest(
                    field_name="booking_no",
                    field_value="BKG-88012",
                    normalized_value="BKG-88012",
                    container_no="TEMU5544332",
                    source_type="pdf_text",
                    source_label="Booking No: BKG-88012",
                    document_type="arrival_notice",
                    confidence=Decimal("0.9700"),
                    attachment_filename="customs_update_temu5544332.pdf",
                ),
                IngestFactRequest(
                    field_name="bl_no",
                    field_value="TSLHPH26061588",
                    normalized_value="TSLHPH26061588",
                    container_no="TEMU5544332",
                    source_type="pdf_text",
                    source_label="B/L No: TSLHPH26061588",
                    document_type="arrival_notice",
                    confidence=Decimal("0.9700"),
                    attachment_filename="customs_update_temu5544332.pdf",
                ),
                IngestFactRequest(
                    field_name="pod",
                    field_value="Hai Phong",
                    normalized_value="Hai Phong",
                    container_no="TEMU5544332",
                    source_type="pdf_text",
                    source_label="POD: Hai Phong",
                    document_type="arrival_notice",
                    confidence=Decimal("0.9600"),
                    attachment_filename="customs_update_temu5544332.pdf",
                ),
                IngestFactRequest(
                    field_name="eta",
                    field_value="2026-06-15",
                    normalized_value="2026-06-15",
                    container_no="TEMU5544332",
                    source_type="pdf_text",
                    source_label="ETA: 2026-06-15",
                    document_type="arrival_notice",
                    confidence=Decimal("0.9600"),
                    attachment_filename="customs_update_temu5544332.pdf",
                ),
                IngestFactRequest(
                    field_name="status_text",
                    field_value="Chờ thông quan để lấy lệnh giao hàng",
                    normalized_value="Chờ thông quan để lấy lệnh giao hàng",
                    container_no="TEMU5544332",
                    source_type="pdf_text",
                    source_label="Status: Cho thong quan de lay lenh giao hang",
                    document_type="arrival_notice",
                    confidence=Decimal("0.9600"),
                    attachment_filename="customs_update_temu5544332.pdf",
                ),
            ],
        ),
        ProcessedEmailIngestRequest(
            gmail_connection_id=gmail_connection_id,
            sync_job_id=sync_job_id,
            gmail_message_id="demo-msg-016",
            gmail_thread_id="demo-thread-001",
            subject="To khai Hai quan (thong quan) - MSCU1234567 - TK 108234567890",
            from_email="docs@dai-duong-logistics-demo.vn",
            to_emails=["ops@agentify.vn"],
            sent_at=_dt("2026-06-16T09:20:00Z"),
            snippet="Da thong quan container MSCU1234567, so to khai 108234567890.",
            body_text=(
                "Gui anh/chi to khai hai quan da thong quan cho container "
                "MSCU1234567, so to khai 108234567890."
            ),
            raw_labels=["INBOX", "LOGISTICS"],
            has_pdf_attachments=True,
            attachments=[
                IngestAttachmentRequest(
                    gmail_attachment_id="demo-att-016",
                    filename="customs_declaration_mscu1234567_demo.pdf",
                    mime_type="application/pdf",
                    size_bytes=9_491,
                    storage_path="/demo/customs_declaration_mscu1234567_demo.pdf",
                    is_text_pdf=True,
                    text_extract_status="extracted",
                    extracted_text=(
                        "So to khai: 108234567890\n"
                        "Ma loai hinh: A11 2 [4]\n"
                        "Nguoi nhap khau: CONG TY TNHH XUAT NHAP KHAU DAI DUONG\n"
                        "So van don: HBLGER2607001\n"
                        "So hieu container: MSCU1234567\n"
                        "Phuong tien van chuyen: MV NORTHERN LYRA / 074E\n"
                        "Dia diem xep hang: HAMBURG\n"
                        "Dia diem do hang: CANG CAT LAI (HCM)\n"
                        "Ngay hang den: 05/07/2026\n"
                        "Ma ket qua phan luong: Vang (2)\n"
                        "Tong so tien thue phai nop: VND 22,506,000"
                    ),
                    document_type="customs_declaration",
                )
            ],
            extracted_facts=[
                IngestFactRequest(
                    field_name="container_no",
                    field_value="MSCU1234567",
                    normalized_value="MSCU1234567",
                    container_no="MSCU1234567",
                    source_type="pdf_text",
                    source_label="So hieu container: MSCU1234567",
                    document_type="customs_declaration",
                    confidence=Decimal("0.9800"),
                    attachment_filename="customs_declaration_mscu1234567_demo.pdf",
                ),
                IngestFactRequest(
                    field_name="declaration_no",
                    field_value="108234567890",
                    normalized_value="108234567890",
                    container_no="MSCU1234567",
                    source_type="pdf_text",
                    source_label="So to khai: 108234567890",
                    document_type="customs_declaration",
                    confidence=Decimal("0.9800"),
                    attachment_filename="customs_declaration_mscu1234567_demo.pdf",
                ),
                IngestFactRequest(
                    field_name="bl_no",
                    field_value="HBLGER2607001",
                    normalized_value="HBLGER2607001",
                    container_no="MSCU1234567",
                    source_type="pdf_text",
                    source_label="So van don: HBLGER2607001",
                    document_type="customs_declaration",
                    confidence=Decimal("0.9600"),
                    attachment_filename="customs_declaration_mscu1234567_demo.pdf",
                ),
                IngestFactRequest(
                    field_name="status_text",
                    field_value="Da thong quan",
                    normalized_value="Da thong quan",
                    container_no="MSCU1234567",
                    source_type="email_body",
                    source_label="Da thong quan container MSCU1234567.",
                    document_type="customs_declaration",
                    confidence=Decimal("0.9500"),
                ),
            ],
        ),
    ]

    for payload in payloads:
        for attachment in payload.attachments:
            attachment.storage_path, attachment.size_bytes = _materialize_demo_pdf(
                attachment.filename,
                attachment.extracted_text,
            )

    return payloads


async def _get_or_create_demo_connection(session) -> GmailConnection:
    result = await session.execute(
        text(
            """
            SELECT id
            FROM gmail_connections
            WHERE account_email = :account_email
            LIMIT 1
            """
        ),
        {"account_email": DEMO_ACCOUNT_EMAIL},
    )
    row = result.first()
    if row:
        connection = await session.get(GmailConnection, row.id)
        assert connection is not None
        connection.display_name = DEMO_DISPLAY_NAME
        connection.google_account_id = DEMO_GOOGLE_ACCOUNT_ID
        connection.status = "connected"
        connection.access_scope = "gmail.readonly"
        connection.encrypted_refresh_token = "demo-refresh-token"
        connection.sync_cursor = "demo-history-id-20260608"
        connection.extra_metadata = {"seeded_by": "seed_demo_data.py"}
        return connection

    connection = GmailConnection(
        account_email=DEMO_ACCOUNT_EMAIL,
        display_name=DEMO_DISPLAY_NAME,
        google_account_id=DEMO_GOOGLE_ACCOUNT_ID,
        encrypted_refresh_token="demo-refresh-token",
        access_scope="gmail.readonly",
        status="connected",
        sync_cursor="demo-history-id-20260608",
        extra_metadata={"seeded_by": "seed_demo_data.py"},
    )
    session.add(connection)
    await session.flush()
    return connection


async def _create_sync_jobs(
    session,
    gmail_connection_id: UUID,
    email_count: int,
    attachment_count: int,
    container_count: int,
) -> tuple[SyncJob, SyncJob]:
    completed_job = SyncJob(
        gmail_connection_id=gmail_connection_id,
        query="label:LOGISTICS newer_than:30d",
        max_results=200,
        status="completed",
        emails_fetched=email_count,
        attachments_found=attachment_count,
        pdf_text_extracted=attachment_count,
        containers_upserted=container_count,
        started_at=_dt("2026-06-08T03:00:00Z"),
        completed_at=_dt("2026-06-08T03:02:30Z"),
    )
    queued_job = SyncJob(
        gmail_connection_id=gmail_connection_id,
        query="label:LOGISTICS newer_than:7d",
        max_results=100,
        status="queued",
        emails_fetched=0,
        attachments_found=0,
        pdf_text_extracted=0,
        containers_upserted=0,
    )
    session.add_all([completed_job, queued_job])
    await session.flush()
    return completed_job, queued_job


async def _truncate_all(session) -> None:
    await session.execute(
        text(
            "TRUNCATE TABLE "
            "container_facts, attachments, emails, sync_jobs, gmail_connections, containers "
            "RESTART IDENTITY CASCADE"
        )
    )


async def _delete_demo_only(session) -> None:
    await session.execute(
        text(
            """
            DELETE FROM container_facts
            WHERE email_id IN (
                SELECT id FROM emails WHERE gmail_message_id LIKE 'demo-msg-%'
            )
            """
        )
    )
    await session.execute(
        text(
            """
            DELETE FROM attachments
            WHERE email_id IN (
                SELECT id FROM emails WHERE gmail_message_id LIKE 'demo-msg-%'
            )
            """
        )
    )
    await session.execute(
        text("DELETE FROM emails WHERE gmail_message_id LIKE 'demo-msg-%'")
    )
    await session.execute(
        text(
            """
            DELETE FROM sync_jobs
            WHERE gmail_connection_id IN (
                SELECT id FROM gmail_connections
                WHERE account_email = :account_email
            )
            """
        )
        ,
        {"account_email": DEMO_ACCOUNT_EMAIL},
    )
    await session.execute(
        text("DELETE FROM gmail_connections WHERE account_email = :account_email"),
        {"account_email": DEMO_ACCOUNT_EMAIL},
    )
    await session.execute(
        text(
            """
            DELETE FROM containers
            WHERE container_no = ANY(:container_nos)
            """
        )
        ,
        {"container_nos": DEMO_CONTAINER_NOS},
    )


async def seed_demo_data(truncate: bool) -> dict[str, int]:
    async with AsyncSessionLocal() as session:
        if truncate:
            await _truncate_all(session)
        else:
            await _delete_demo_only(session)

        connection = await _get_or_create_demo_connection(session)
        payloads = build_demo_payloads(connection.id, UUID(int=0))
        completed_job, _ = await _create_sync_jobs(
            session,
            connection.id,
            email_count=len(payloads),
            attachment_count=sum(len(payload.attachments) for payload in payloads),
            container_count=len(DEMO_CONTAINER_NOS),
        )

        for payload in payloads:
            payload.sync_job_id = completed_job.id
            await ingest_processed_email(session, payload)

        connection.last_synced_at = _dt("2026-06-08T03:02:30Z")
        await session.commit()

        return {
            "gmail_connections": 1,
            "sync_jobs": 2,
            "emails": len(payloads),
            "attachments": sum(len(payload.attachments) for payload in payloads),
            "containers": len(DEMO_CONTAINER_NOS),
            "container_facts": sum(len(payload.extracted_facts) for payload in payloads),
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed demo logistics data.")
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="Truncate all prototype tables before inserting demo data.",
    )
    args = parser.parse_args()
    summary = asyncio.run(seed_demo_data(truncate=args.truncate))
    for key, value in summary.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
