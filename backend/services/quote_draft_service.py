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
from datetime import date
from decimal import Decimal, InvalidOperation
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models import Email
from gmail_service.field_extract import extract_fields, run_extraction_in_thread

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

# Chuỗi ứng viên cho tên cảng: chỉ chữ và khoảng trắng, tối đa 6 từ. Cấm chữ số
# để không nuốt "2 x 40HC", cấm dấu câu để dừng ở dấu phẩy. Việc cắt đúng chỗ
# tên cảng bắt đầu và kết thúc do `_clean_port` làm, không do regex: dải Unicode
# `À-Ỹ` có lẫn cả chữ thường nên không viết được lớp "chữ hoa" đáng tin.
_PORT = r"[A-Za-zÀ-ỹ]+(?:[ \t]+[A-Za-zÀ-ỹ]+){0,5}"

# Mail hỏi giá viết tuyến bằng câu tiếng Việt, không có nhãn "POL:" nào để
# `deterministic_extract` bám vào. Không bắt được ba câu dưới đây thì cả Bước 1
# lẫn nút "Điền từ báo giá đã chốt" ở Bước 2 đều ra rỗng khi không có LLM.
# Cờ IGNORECASE chỉ đặt quanh từ khoá `(?i:…)`, KHÔNG phủ lên `_PORT` — phủ lên
# thì mất luôn điều kiện viết hoa vốn là thứ cắt đúng chỗ tên cảng kết thúc.
_ROUTE_PHRASE_RES = (
    # "Lấy hàng tại Hai Phong, giao Yokohama"
    re.compile(
        rf"(?i:l[ấa]y[ \t]+h[àa]ng[ \t]+(?:t[ạa]i|[ởo]))[ \t]+({_PORT})"
        rf"[^\n]{{0,20}}?(?i:\bgiao(?:[ \t]+t[ạa]i|[ \t]+[ởo])?)[ \t]+({_PORT})"
    ),
    # "từ Hai Phong đi/đến/về Yokohama"
    re.compile(
        rf"(?i:t[ừu])[ \t]+({_PORT})[ \t]+(?i:đi|đến|về|tới)[ \t]+({_PORT})"
    ),
    # "Hai Phong - Yokohama" / "Hai Phong → Yokohama", thường nằm ở tiêu đề.
    re.compile(rf"({_PORT})[ \t]*[-–—→>]+[ \t]*({_PORT})"),
)

# "Hàng sẵn kho ngày 2026-08-20" — người viết nói thẳng ngày hàng sẵn, khác hẳn
# việc suy từ ETD (xem docstring `build_draft_from_fields`).
_CARGO_READY_RE = re.compile(
    r"h[àa]ng[ \t]+s[ẵa]n[^\n]{0,20}?ng[àa]y[ \t]*"
    r"(\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{4})",
    re.IGNORECASE,
)

# "Hàng: Áo sơ mi cotton, đóng 2 x 40HC."
_COMMODITY_RE = re.compile(
    r"^[ \t]*(?:h[àa]ng|m[ặa]t[ \t]+h[àa]ng|t[êe]n[ \t]+h[àa]ng)[ \t]*[:：][ \t]*"
    r"([^\n,.;]{2,80})",
    re.IGNORECASE | re.MULTILINE,
)

# Dòng ký tên cuối thư hỏi giá — nguồn duy nhất cho tên khách khi không có LLM.
_COMPANY_LINE_RE = re.compile(
    r"^[ \t]*((?:C[ôo]ng[ \t]+ty|C[ÔO]NG[ \t]+TY|CTCP|CTY|Cty|Cong[ \t]+ty)"
    r"[^\n]{3,90})$",
    re.MULTILINE,
)


def _clean_port(value: str, *, from_end: bool) -> str | None:
    """Giữ lại đúng phần tên riêng trong một khúc câu.

    Tên cảng viết hoa đầu từ, phần câu chạy tiếp thì không — đó là thứ duy nhất
    tách được "Yokohama" khỏi "Yokohama cho lô áo".

    `from_end` chọn đọc từ đầu hay từ cuối khúc câu, và phải khác nhau ở hai
    vế: cảng đi nằm sát dấu nối nên lấy cụm hoa CUỐI ("Cần báo giá Hai Phong"
    → `Hai Phong`, không phải `Cần`), cảng đến nằm ngay sau dấu nối nên lấy cụm
    hoa ĐẦU.
    """
    words = value.strip(" \t-–—>→").split()
    if from_end:
        words = list(reversed(words))

    kept: list[str] = []
    for word in words:
        if word[0].isupper():
            kept.append(word)
        elif kept:
            break

    kept = kept[:4]
    if from_end:
        kept.reverse()
    port = " ".join(kept)
    return port if len(port) >= 2 else None


def find_route(text: str) -> tuple[str | None, str | None]:
    """Trả `(POL, POD)` đọc từ câu văn xuôi của mail hỏi giá."""
    for pattern in _ROUTE_PHRASE_RES:
        match = pattern.search(text)
        if not match:
            continue
        pol = _clean_port(match.group(1), from_end=True)
        pod = _clean_port(match.group(2), from_end=False)
        # Một vế hỏng thì bỏ cả cặp: nửa tuyến còn nguy hiểm hơn không có
        # tuyến, vì nó trông như đã kiểm.
        if pol and pod and pol.lower() != pod.lower():
            return pol, pod
    return None, None


def find_cargo_ready_date(text: str) -> str | None:
    """Ngày hàng sẵn kho, chuẩn hoá về ISO. `05/07/2026` là 5 tháng 7."""
    match = _CARGO_READY_RE.search(text)
    if not match:
        return None
    raw = match.group(1)
    if "-" in raw and len(raw.split("-")[0]) == 4:
        return raw
    day, month, year = re.split(r"[/-]", raw)
    try:
        return date(int(year), int(month), int(day)).isoformat()
    except ValueError:
        return None


def find_customer_name(text: str) -> str | None:
    match = _COMPANY_LINE_RE.search(text)
    return match.group(1).strip() if match else None


def find_commodity(text: str) -> str | None:
    match = _COMMODITY_RE.search(text)
    return match.group(1).strip() if match else None


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
    liệu thật mà không ai kiểm. Chỉ nhận khi mail nói thẳng "hàng sẵn ngày…".

    Regex chỉ chạy khi trích xuất không trả về trường đó, không đè lên: mail
    hỏi giá viết tuyến bằng câu tiếng Việt nên `deterministic_extract` (vốn cần
    nhãn `POL:`) trả rỗng, nhưng khi có LLM thì bản đọc của nó vẫn tốt hơn.
    """
    route = fields.get("route") or {}
    cargo = fields.get("cargo") or {}
    shipper = fields.get("shipper") or {}

    container_type, container_qty = find_container_type(text)
    fallback_pol, fallback_pod = find_route(text)

    draft: dict = {
        "customer_name": (
            fields.get("customer_name")
            or (shipper.get("name") if isinstance(shipper, dict) else shipper)
            or find_customer_name(text)
        ),
        "pol": route.get("pol") or fallback_pol,
        "pod": route.get("pod") or fallback_pod,
        "commodity": cargo.get("description") or find_commodity(text),
        "container_type": container_type,
        "container_qty": container_qty,
        "gross_weight_kg": _decimal_or_none(cargo.get("gross_weight_kg")),
        "cargo_ready_date": find_cargo_ready_date(text),
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
        fields = await run_extraction_in_thread(
            extract_fields, email.subject or "", email.from_email or "", text
        )
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
