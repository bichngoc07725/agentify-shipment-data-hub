"""Soạn sẵn nội dung mail cho vòng hỏi giá (Bước 1).

Agentify KHÔNG gửi mail: scope Gmail là `gmail.readonly`, và việc gửi dưới danh
nghĩa nhân viên là một quyết định sản phẩm chưa được chốt. Module này chỉ dựng
sẵn tiêu đề + nội dung từ dữ liệu đã có, nhân viên bấm gửi trong hộp thư của
chính họ. Nhờ vậy vẫn bỏ được việc gõ tay mà không phải xin thêm quyền nào.

Hai chiều thư:
- gửi HÃNG TÀU để hỏi cước — viết tiếng Anh, đúng thói quen làm việc với hãng;
- gửi KHÁCH để báo giá — viết tiếng Việt, kèm bảng phí và hạn hiệu lực.
"""

from __future__ import annotations

from decimal import Decimal

from db.models import ChargeGroup, Quote

GROUP_LABELS: dict[ChargeGroup, str] = {
    ChargeGroup.OCEAN_FREIGHT: "Cước biển",
    ChargeGroup.SURCHARGE: "Phụ phí",
    ChargeGroup.LOCAL: "Phí local",
}

_MISSING = "(chưa có)"


def _qty(quantity: Decimal) -> str:
    """Số lượng cho thư gửi khách: `2` chứ không phải `2.00`.

    Cột lưu `Numeric` nên đọc ra luôn có phần thập phân. "2.00 container" trong
    thư gửi khách đọc như máy in ra; giữ phần lẻ chỉ khi nó thật sự khác 0
    (một số phí tính theo tấn hay CBM có số lẻ thật).
    """
    if quantity == quantity.to_integral_value():
        return str(quantity.to_integral_value())
    return str(quantity.normalize())


def _or_missing(value: object) -> str:
    """Thiếu thì nói là thiếu. Một ô trống giữa thân thư khiến người đọc tưởng
    thông tin không quan trọng, trong khi thực ra là ta chưa biết."""
    text = str(value).strip() if value is not None else ""
    return text or _MISSING


def _equipment(quote: Quote) -> str:
    if quote.container_type and quote.container_qty:
        return f"{quote.container_qty} x {quote.container_type}"
    return _or_missing(quote.container_type)


def build_rate_request_mail(quote: Quote) -> dict[str, str]:
    """Thư hỏi cước gửi hãng tàu / đại lý."""
    lines = [
        "Dear Sirs,",
        "",
        "We would like to request an ocean freight quotation for the shipment below.",
        "",
        f"- Port of loading : {_or_missing(quote.pol)}",
        f"- Port of discharge: {_or_missing(quote.pod)}",
        f"- Commodity       : {_or_missing(quote.commodity)}",
        f"- Equipment       : {_equipment(quote)}",
    ]
    if quote.gross_weight_kg:
        lines.append(f"- Gross weight    : {quote.gross_weight_kg} KGS")
    if quote.cargo_ready_date:
        lines.append(f"- Cargo ready date: {quote.cargo_ready_date.isoformat()}")
    if quote.incoterm:
        lines.append(f"- Incoterm        : {quote.incoterm}")
    if quote.is_dangerous:
        lines.append("- Dangerous goods : YES — please advise DG surcharge and IMO class.")
    if quote.is_reefer:
        lines.append("- Reefer cargo    : YES — please advise required temperature setting.")

    lines += [
        "",
        "Please quote all-in, breaking down ocean freight, surcharges and local charges "
        "separately, and advise:",
        "  1. Free time at destination",
        "  2. Transit time and routing",
        "  3. Rate validity",
        "",
        f"Our reference: {quote.quote_no}",
        "",
        "Thank you and best regards,",
        "Agentify Forwarding",
    ]

    subject = (
        f"Rate request {_or_missing(quote.pol)} - {_or_missing(quote.pod)} / "
        f"{_equipment(quote)} / ref {quote.quote_no}"
    )
    return {"subject": subject, "body": "\n".join(lines)}


def build_customer_quote_mail(quote: Quote) -> dict[str, str]:
    """Thư báo giá gửi khách, kèm bảng phí theo 3 khối."""
    lines = [
        f"Kính gửi {_or_missing(quote.customer_name)},",
        "",
        "Agentify xin gửi Quý khách báo giá cho lô hàng như sau:",
        "",
        f"- Tuyến      : {_or_missing(quote.pol)} → {_or_missing(quote.pod)}",
        f"- Mặt hàng   : {_or_missing(quote.commodity)}",
        f"- Thiết bị   : {_equipment(quote)}",
    ]
    if quote.incoterm:
        lines.append(f"- Điều kiện  : {quote.incoterm}")
    if quote.transit_time:
        lines.append(f"- Thời gian vận chuyển: {quote.transit_time}")

    lines += ["", "CHI TIẾT PHÍ", ""]

    total = Decimal("0")
    for group in (ChargeGroup.OCEAN_FREIGHT, ChargeGroup.SURCHARGE, ChargeGroup.LOCAL):
        charges = [c for c in quote.charges if c.charge_group == group]
        if not charges:
            continue
        lines.append(f"{GROUP_LABELS[group]}:")
        for charge in charges:
            label = charge.description or charge.charge_code
            lines.append(
                f"  - {label}: {charge.amount} {charge.currency}"
                + (
                    f" (x{_qty(charge.quantity)})"
                    if charge.quantity and charge.quantity != 1
                    else ""
                )
            )
            total += charge.amount or Decimal("0")
        lines.append("")

    if not quote.charges:
        # Gửi một báo giá chưa có dòng phí nào là gửi một tờ giấy trắng — nói
        # thẳng ra thay vì để bảng rỗng trông như đã điền xong.
        lines.append("(Báo giá chưa có dòng phí nào — vui lòng bổ sung trước khi gửi.)")
        lines.append("")
    else:
        lines.append(f"TỔNG CỘNG: {total} {quote.currency}")
        lines.append("")

    if quote.valid_until:
        lines.append(f"Báo giá có hiệu lực đến ngày {quote.valid_until.isoformat()}.")
    if quote.payment_term:
        lines.append(f"Điều khoản thanh toán: {quote.payment_term}.")

    lines += [
        "",
        "Rất mong nhận được phản hồi của Quý khách.",
        "",
        "Trân trọng,",
        "Agentify Forwarding — Bộ phận Kinh doanh",
    ]

    subject = (
        f"Báo giá {quote.quote_no}: {_or_missing(quote.pol)} đi {_or_missing(quote.pod)}"
    )
    return {"subject": subject, "body": "\n".join(lines)}
