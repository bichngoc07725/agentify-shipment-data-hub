"""Đọc các dòng phí trong mail báo giá của hãng tàu, xếp vào 3 khối của báo giá.

Schema trích xuất trả về `charges` phẳng (mô tả, số lượng, tiền tệ, số tiền)
nhưng KHÔNG có nhóm phí — mà báo giá của Agentify lại chia theo cước biển /
phụ phí / phí local (BA Spec Bước 1 Luồng C). Phân loại ở đây bằng từ khoá:
tên các khoản phí trong ngành là từ viết tắt cố định, không cần tới LLM và
cũng không nên phụ thuộc vào nó cho một phép xếp nhóm phải tái lập được.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models import ChargeGroup, Email
from gmail_service.field_extract import extract_fields, run_extraction_in_thread

# Mã phí chuẩn hoá theo từ khoá xuất hiện trong mô tả. Xếp theo thứ tự kiểm
# tra: cụm dài và đặc thù đứng trước để không bị cụm ngắn nuốt mất.
_CHARGE_CODES: tuple[tuple[str, tuple[str, ...], ChargeGroup], ...] = (
    ("OF", ("ocean freight", "sea freight", "basic freight", "cước biển"), ChargeGroup.OCEAN_FREIGHT),
    ("AF", ("air freight",), ChargeGroup.OCEAN_FREIGHT),
    ("THC", ("terminal handling", "thc"), ChargeGroup.LOCAL),
    ("CIC", ("container imbalance", "cic"), ChargeGroup.SURCHARGE),
    ("BAF", ("bunker adjustment", "baf"), ChargeGroup.SURCHARGE),
    ("EBS", ("emergency bunker", "ebs"), ChargeGroup.SURCHARGE),
    ("LSS", ("low sulphur", "low sulfur", "lss"), ChargeGroup.SURCHARGE),
    ("PSS", ("peak season", "pss"), ChargeGroup.SURCHARGE),
    ("FSC", ("fuel surcharge", "fsc"), ChargeGroup.SURCHARGE),
    ("WRS", ("war risk", "wrs"), ChargeGroup.SURCHARGE),
    ("AMS", ("ams", "advance manifest"), ChargeGroup.SURCHARGE),
    ("ENS", ("ens", "entry summary"), ChargeGroup.SURCHARGE),
    ("DG", ("dangerous goods", "imo surcharge"), ChargeGroup.SURCHARGE),
    ("DOC", ("documentation", "doc fee", "b/l fee", "bill fee"), ChargeGroup.LOCAL),
    ("DO", ("delivery order", "d/o fee", "do fee"), ChargeGroup.LOCAL),
    ("SEAL", ("seal fee", "phí seal", "niêm phong"), ChargeGroup.LOCAL),
    ("TELEX", ("telex release", "telex"), ChargeGroup.LOCAL),
    ("CFS", ("cfs",), ChargeGroup.LOCAL),
    ("LOLO", ("lift on", "lift off", "lolo", "nâng hạ"), ChargeGroup.LOCAL),
    ("CLEAN", ("cleaning", "vệ sinh container"), ChargeGroup.LOCAL),
)

# Không đoán được thì xếp vào phụ phí và để người dùng sửa: đặt nhầm vào cước
# biển sẽ làm hỏng phép đối soát ở Bước 6, vì cước biển là khoản đối chiếu
# chính giữa báo giá và debit note.
_DEFAULT_GROUP = ChargeGroup.SURCHARGE
_DEFAULT_CODE = "OTHER"


def classify_charge(description: str | None) -> tuple[str, ChargeGroup]:
    """Trả `(mã phí, nhóm)` suy từ mô tả."""
    text = (description or "").lower()
    for code, keywords, group in _CHARGE_CODES:
        if any(keyword in text for keyword in keywords):
            return code, group
    return _DEFAULT_CODE, _DEFAULT_GROUP


def _decimal_or_none(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def build_charge_lines(charges: list[dict]) -> list[dict]:
    """Map `charges` trích xuất được sang hình dạng dòng phí của báo giá.

    Bỏ qua dòng không có số tiền: một khoản phí không có giá trị thì không
    dùng được vào việc gì, và để lại nó với đơn giá 0 sẽ âm thầm kéo tổng báo
    giá xuống thấp hơn thực tế.
    """
    lines: list[dict] = []
    for charge in charges or []:
        amount = _decimal_or_none(charge.get("amount"))
        if amount is None:
            continue

        quantity = _decimal_or_none(charge.get("quantity")) or Decimal("1")
        if quantity <= 0:
            quantity = Decimal("1")

        code, group = classify_charge(charge.get("description"))
        lines.append(
            {
                "charge_group": group.value,
                "charge_code": code,
                "description": charge.get("description") or "",
                # Số tiền trích ra là THÀNH TIỀN của dòng; đơn giá suy ngược từ
                # số lượng để tổng không bị nhân lên hai lần khi lưu.
                "unit_price": str(amount / quantity),
                "currency": charge.get("currency") or "USD",
                "quantity": str(quantity),
            }
        )
    return lines


async def build_charge_draft_from_email(
    db: AsyncSession, email_id: UUID
) -> dict | None:
    """Các dòng phí đọc được từ một mail báo giá của hãng tàu."""
    result = await db.execute(
        select(Email).options(selectinload(Email.attachments)).where(Email.id == email_id)
    )
    email = result.scalar_one_or_none()
    if email is None:
        return None

    parts = [email.subject or "", email.body_text or ""]
    parts.extend(a.extracted_text for a in email.attachments if a.extracted_text)
    text = "\n".join(part for part in parts if part.strip())

    try:
        fields = await run_extraction_in_thread(
            extract_fields, email.subject or "", email.from_email or "", text
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "source_email_id": str(email.id),
            "source_subject": email.subject,
            "source_from": email.from_email,
            "charges": [],
            "extraction_error": str(exc),
        }

    return {
        "source_email_id": str(email.id),
        "source_subject": email.subject,
        "source_from": email.from_email,
        "charges": build_charge_lines(fields.get("charges") or []),
        "extraction_error": None,
    }
