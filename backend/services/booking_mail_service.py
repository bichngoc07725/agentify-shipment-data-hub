"""Soạn thư đặt chỗ gửi hãng tàu (Bước 2).

Khác thư hỏi cước ở Bước 1: lúc đó ta còn đang so giá, giờ đã chốt giá với
khách và đi đặt chỗ thật. Nên thư này CHỐT chỗ chứ không hỏi giá, và phải nêu
đủ thứ hãng tàu cần để cấp booking: tuyến, thiết bị, ngày hàng sẵn, và mức
cước đã thoả thuận nếu có.

Agentify không gửi hộ — cùng lý do với mọi thư khác: quyền Gmail là chỉ-đọc.
"""

from __future__ import annotations

from db.models import Booking

_MISSING = "(chưa có)"


def _or_missing(value: object) -> str:
    text = str(value).strip() if value is not None else ""
    return text or _MISSING


def _equipment(booking: Booking) -> str:
    if booking.container_type and booking.container_qty:
        return f"{booking.container_qty} x {booking.container_type}"
    return _or_missing(booking.container_type)


def build_booking_request_mail(booking: Booking) -> dict[str, str]:
    """Thư đặt chỗ chính thức gửi hãng tàu."""
    quote = booking.quote

    lines = [
        f"Dear {_or_missing(booking.carrier)} Booking Team,",
        "",
        "Following your rate confirmation, we would like to place a firm booking "
        "for the shipment below.",
        "",
        f"- Port of loading  : {_or_missing(booking.pol)}",
        f"- Port of discharge: {_or_missing(booking.pod)}",
        f"- Equipment        : {_equipment(booking)}",
    ]

    if quote is not None:
        lines.append(f"- Commodity        : {_or_missing(quote.commodity)}")
        lines.append(f"- Shipper          : {_or_missing(quote.customer_name)}")
        if quote.incoterm:
            lines.append(f"- Incoterm         : {quote.incoterm}")
        if quote.gross_weight_kg:
            lines.append(f"- Gross weight     : {quote.gross_weight_kg} KGS")

    if booking.etd:
        lines.append(f"- Requested ETD    : {booking.etd.isoformat()}")
    if booking.vessel or booking.voyage:
        lines.append(
            f"- Preferred vessel : {' '.join(filter(None, [booking.vessel, booking.voyage]))}"
        )
    if booking.freight_rate:
        # Nhắc lại mức cước đã chốt ngay trong thư đặt chỗ: đây là chỗ tranh
        # chấp hay xảy ra nhất khi debit note về ở Bước 6 không khớp giá chào.
        lines.append(
            f"- Agreed rate      : {booking.freight_rate} {booking.currency} "
            "(as per your quotation)"
        )

    lines += [
        "",
        "Please confirm and advise:",
        "  1. Booking number",
        "  2. Vessel / voyage and ETD-ETA",
        "  3. SI cut-off, VGM cut-off and gate-in cut-off",
        "  4. Empty pick-up depot",
        "",
    ]

    if booking.note:
        lines += [f"Remarks: {booking.note}", ""]

    lines += [
        "Thank you and best regards,",
        "Agentify Forwarding — Operations",
    ]

    reference = booking.booking_no or (quote.quote_no if quote else None)
    subject = (
        f"Booking request {_or_missing(booking.pol)} - {_or_missing(booking.pod)} / "
        f"{_equipment(booking)}"
        + (f" / ref {reference}" if reference else "")
    )
    return {"subject": subject, "body": "\n".join(lines)}
