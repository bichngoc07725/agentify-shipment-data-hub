"""Dựng bản nháp báo giá từ một email hỏi giá (Bước 1).

Vì sao phải bóc lại thay vì đọc dữ liệu đã lưu: `ingestion_service` chỉ tạo
`container_facts` cho fact nào gắn được vào một container. Mail hỏi giá thì
CHƯA có container — chưa đặt tàu thì lấy đâu ra số cont — nên mọi thứ pipeline
đọc được (POL, POD, tên hàng) bị bỏ ngay tại đó. `Attachment.extracted_record`
cũng không cứu được: nó đang rỗng với file PDF từ Gmail.

Hệ quả là Sales phải đọc mail rồi gõ tay lại. Module này bóc lại nội dung email
theo yêu cầu (người dùng bấm nút) và trả về đúng hình dạng form báo giá.

Kết quả luôn là GỢI Ý: người bán chịu trách nhiệm về con số gửi khách, nên
không có gì được ghi thẳng vào báo giá.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models import Email
from gmail_service.field_extract import extract_fields

# Loại container viết theo chuẩn ISO ngành: 20GP, 40HC, 40HQ, 20RF...
_CONTAINER_TYPE_RE = re.compile(
    r"\b(\d{1,2})\s*[x*]\s*(20|40|45)\s*(GP|DC|HC|HQ|RF|RH|OT|FR|NOR)\b", re.IGNORECASE
)
_CONTAINER_TYPE_ONLY_RE = re.compile(
    r"\b(20|40|45)\s*(GP|DC|HC|HQ|RF|RH|OT|FR|NOR)\b", re.IGNORECASE
)

# Điều kiện Incoterms 2020. Không nằm trong schema trích xuất nên bắt bằng regex
# — chúng là từ khoá cố định, không cần tới LLM.
_INCOTERMS = (
    "EXW", "FCA", "FAS", "FOB", "CFR", "CIF", "CPT", "CIP", "DAP", "DPU", "DDP",
)
_INCOTERM_RE = re.compile(rf"\b({'|'.join(_INCOTERMS)})\b")


def find_container_type(text: str) -> tuple[str | None, int | None]:
    """Trả `(loại cont, số lượng)`, ví dụ "1 x 40HC" -> ("40HC", 1)."""
    match = _CONTAINER_TYPE_RE.search(text)
    if match:
        qty, size, kind = match.groups()
        return f"{size}{kind.upper()}", int(qty)

    match = _CONTAINER_TYPE_ONLY_RE.search(text)
    if match:
        size, kind = match.groups()
        return f"{size}{kind.upper()}", None

    return None, None


def find_incoterm(text: str) -> str | None:
    match = _INCOTERM_RE.search(text.upper())
    return match.group(1) if match else None


def _decimal_or_none(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def build_draft_from_fields(fields: dict, text: str) -> dict:
    """Map kết quả trích xuất sang đúng các ô của form báo giá.

    Cố ý KHÔNG suy `cargo_ready_date` từ ETD: ngày hàng sẵn ở kho và ngày tàu
    chạy là hai mốc khác nhau, đoán bừa ở đây tạo ra một ngày trông như dữ
    liệu thật mà không ai kiểm.
    """
    route = fields.get("route") or {}
    cargo = fields.get("cargo") or {}

    container_type, container_qty = find_container_type(text)

    draft: dict = {
        "customer_name": fields.get("customer_name") or fields.get("shipper"),
        "pol": route.get("pol"),
        "pod": route.get("pod"),
        "commodity": cargo.get("description"),
        "container_type": container_type,
        "container_qty": container_qty,
        "gross_weight_kg": _decimal_or_none(cargo.get("gross_weight_kg")),
        "incoterm": find_incoterm(text),
        "payment_term": fields.get("payment_term"),
    }
    return {key: value for key, value in draft.items() if value not in (None, "")}


async def build_quote_draft_from_email(
    db: AsyncSession, email_id: UUID
) -> dict | None:
    """Bản nháp báo giá cho một email, kèm nguồn gốc.

    Trả `None` khi không có email — để route phân biệt được 404 với "đọc được
    email nhưng không rút ra trường nào", vốn là hai chuyện khác hẳn nhau.
    """
    result = await db.execute(
        select(Email).options(selectinload(Email.attachments)).where(Email.id == email_id)
    )
    email = result.scalar_one_or_none()
    if email is None:
        return None

    parts = [email.subject or "", email.body_text or ""]
    parts.extend(
        attachment.extracted_text
        for attachment in email.attachments
        if attachment.extracted_text
    )
    text = "\n".join(part for part in parts if part.strip())

    try:
        fields = extract_fields(email.subject or "", email.from_email or "", text)
    except Exception as exc:  # noqa: BLE001 — nhà cung cấp LLM lỗi không được
        # làm hỏng cả thao tác; Sales vẫn mở được form trống và gõ tay.
        return {
            "source_email_id": str(email.id),
            "source_subject": email.subject,
            "source_from": email.from_email,
            "fields": {},
            "fields_found": [],
            "extraction_error": str(exc),
        }

    draft = build_draft_from_fields(fields, text)

    return {
        "source_email_id": str(email.id),
        "source_subject": email.subject,
        "source_from": email.from_email,
        "fields": draft,
        "fields_found": sorted(draft.keys()),
        "extraction_error": None,
    }
