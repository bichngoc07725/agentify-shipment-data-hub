"""Đối chiếu chéo giữa các chứng từ của cùng một lô (Bước 3).

Rủi ro gốc của Bước 3: "Invoice/Packing List sai lệch không phát hiện sớm →
lỗi kéo dài đến khâu hải quan". Hệ thống vẫn đọc được cả hai chứng từ, nhưng
trước đây lưu song song rồi im lặng — Invoice ghi 940 kiện, Packing List ghi
904 kiện thì cả hai cùng nằm đó và sai lệch đi thẳng tới lúc khai hải quan.

Module này so từng trường giữa các loại chứng từ và chỉ ra chỗ vênh. Nó KHÔNG
tự chọn bên nào đúng: cả hai đều là chứng từ do đối tác phát hành, máy không có
căn cứ nào để phân xử. Việc của nó là bắt người đọc phải nhìn thấy chỗ vênh.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

# Chứng từ nào được coi là nguồn khai báo số liệu lô hàng. B/L cũng nằm đây vì
# số kiện trên vận đơn lệch với Packing List là lỗi hay gặp và tốn kém.
COMPARED_DOCUMENT_TYPES = ("invoice", "packing_list", "bill_of_lading")

DOCUMENT_LABELS = {
    "invoice": "Invoice",
    "packing_list": "Packing List",
    "bill_of_lading": "Vận đơn",
}

# Trường nào đáng so: nhãn tiếng Việt + so theo số hay theo chữ.
#
# Phân biệt này bắt buộc. Số hiệu chứng từ như "INV-TL-0815" mà đem so kiểu số
# thì bộ tách số đọc ra "-815" và hai bản ghi giống hệt nhau bị báo là vênh.
COMPARED_FIELDS: dict[str, tuple[str, bool]] = {
    "packages": ("Số kiện", True),
    "gross_weight_kg": ("Trọng lượng gộp", True),
    "volume_cbm": ("Số khối", True),
    "invoice_no": ("Số hoá đơn", False),
    "po_no": ("Số PO", False),
}

# Sai số cho phép với trường số. Chứng từ hay làm tròn khác nhau — 18500 với
# 18500.4 không phải lỗi, nhưng 940 với 904 thì có.
NUMERIC_TOLERANCE_PCT = Decimal("0.005")

_NUMBER_RE = re.compile(r"-?\d+(?:[.,]\d+)?")


@dataclass(frozen=True)
class DocumentMismatch:
    field_name: str
    field_label: str
    # {tên chứng từ: giá trị} — giữ nguyên chuỗi gốc để người đọc thấy đúng thứ
    # ghi trên giấy, không phải bản đã chuẩn hoá của máy.
    values_by_document: dict[str, str]

    def describe(self) -> str:
        parts = [
            f"{DOCUMENT_LABELS.get(doc, doc)}: {value}"
            for doc, value in sorted(self.values_by_document.items())
        ]
        return f"{self.field_label} — {' ≠ '.join(parts)}"


def parse_number(value: str) -> Decimal | None:
    """Số đầu tiên trong chuỗi, bỏ dấu phân cách nghìn.

    Chứng từ ghi số kiện đủ kiểu: "940", "940 CTNS", "940 cartons", "1,020".
    So chuỗi thô sẽ báo lệch giả ở mọi cặp, nên phải rút số ra trước.
    """
    if value is None:
        return None
    match = _NUMBER_RE.search(str(value).replace(",", ""))
    if match is None:
        return None
    try:
        return Decimal(match.group(0))
    except InvalidOperation:
        return None


def values_differ(left: str, right: str, numeric: bool = True) -> bool:
    """Hai giá trị có thực sự vênh nhau không.

    `numeric=False` cho trường định danh, so như chữ sau khi bỏ dấu ngăn cách.
    Trả về False khi không chắc — báo lệch giả nhiều lần thì người dùng tắt luôn
    cảnh báo, và lúc đó lệch thật cũng trôi qua.
    """
    if numeric:
        left_num, right_num = parse_number(left), parse_number(right)
        if left_num is not None and right_num is not None:
            if left_num == right_num:
                return False
            larger = max(abs(left_num), abs(right_num))
            if larger == 0:
                return False
            return abs(left_num - right_num) / larger > NUMERIC_TOLERANCE_PCT

    return _normalize_text(left) != _normalize_text(right)


def _normalize_text(value: str) -> str:
    return re.sub(r"[\s\-_/]+", "", str(value)).upper()


def find_mismatches(
    facts_by_field: dict[str, dict[str, str]],
) -> list[DocumentMismatch]:
    """Nhận `{field_name: {document_type: value}}`, trả các trường bị vênh."""
    mismatches: list[DocumentMismatch] = []

    for field_name, (label, numeric) in COMPARED_FIELDS.items():
        by_document = {
            doc: value
            for doc, value in (facts_by_field.get(field_name) or {}).items()
            if doc in COMPARED_DOCUMENT_TYPES and value
        }
        # Một chứng từ thì không có gì để đối chiếu — im lặng, không phải lỗi.
        if len(by_document) < 2:
            continue

        documents = sorted(by_document)
        if any(
            values_differ(by_document[a], by_document[b], numeric=numeric)
            for i, a in enumerate(documents)
            for b in documents[i + 1 :]
        ):
            mismatches.append(
                DocumentMismatch(
                    field_name=field_name,
                    field_label=label,
                    values_by_document=by_document,
                )
            )

    return mismatches
