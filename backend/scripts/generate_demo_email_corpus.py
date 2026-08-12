from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from email.utils import format_datetime, make_msgid
from pathlib import Path
import re
import shutil


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "demo_email"
# Hộp thư nhân viên Agentify dùng để test: mail đến gửi VÀO đây, mail đi gửi TỪ đây.
TARGET_TO = "nguyendinhtung20072000@gmail.com"
AGENTIFY_SELF = TARGET_TO

INBOUND = "inbound"
OUTBOUND = "outbound"

# Nhãn gắn đầu tiêu đề của kịch bản vòng khép kín. Đặt `GMAIL_QUERY` là
# `subject:AGENTIFY-DEMO newer_than:7d` để kéo đúng bộ này về, kể cả các thư
# không đính kèm — query mặc định có `has:attachment` sẽ bỏ sót chúng.
DEMO_TAG = "[AGENTIFY-DEMO]"


@dataclass(frozen=True)
class ContainerProfile:
    key: str
    container_no: str
    booking_no: str
    hbl_no: str
    mbl_no: str
    po_no: str
    commodity: str
    quantity: str
    pol: str
    pod: str
    vessel_voyage: str
    etd: str
    eta: str
    carrier: str
    shipper: str
    consignee: str
    status_bucket: str
    # Địa chỉ đối tác cho từng vai trò trong luồng thư. Chỉ các hồ sơ sinh theo
    # kịch bản (thread) mới cần, nên để mặc định rỗng cho 6 hồ sơ viết tay ban đầu.
    carrier_email: str = ""
    customer_email: str = ""
    agent_email: str = ""
    trucker_email: str = ""
    customs_email: str = ""


@dataclass(frozen=True)
class EmailRecord:
    seq: int
    slug: str
    container_key: str
    title: str
    body: str
    from_email: str
    sent_at: str
    pdf_name: str
    pdf_lines: tuple[str, ...]
    # Mail đến (đối tác -> Agentify) hay mail đi (Agentify -> đối tác). Mail đi
    # vẫn được gửi vào cùng hộp thư test, nên direction phải nằm trong header
    # chứ không suy ra được từ To.
    direction: str = INBOUND
    to_email: str = TARGET_TO
    # Slug của thư được trả lời, để nối In-Reply-To/References thành một thread.
    reply_to_slug: str | None = None


PROFILES: dict[str, ContainerProfile] = {
    "completed": ContainerProfile(
        key="completed",
        container_no="OOLU7215245",
        booking_no="OOL-BKG-260601",
        hbl_no="HBL-SGNHAM-7215",
        mbl_no="ONEYSGN260601",
        po_no="PO-HA-240601",
        commodity="Furniture fittings",
        quantity="1 x 40HC / 812 cartons",
        pol="Hai Phong",
        pod="Hamburg",
        vessel_voyage="ONE RESILIENCE 018W",
        etd="2026-06-01",
        eta="2026-06-24",
        carrier="Ocean Network Express",
        shipper="Viet Home Export Co., Ltd.",
        consignee="Nordic Habitat GmbH",
        status_bucket="Đã hoàn tất",
    ),
    "transit": ContainerProfile(
        key="transit",
        container_no="TGHU4982331",
        booking_no="MSK-BKG-260603",
        hbl_no="HBL-SGNLAX-4982",
        mbl_no="MAEUHCM260603",
        po_no="PO-US-51022",
        commodity="Plastic household goods",
        quantity="1 x 40HQ / 1,020 cartons",
        pol="Cat Lai",
        pod="Long Beach",
        vessel_voyage="MAERSK HANOI 126E",
        etd="2026-06-03",
        eta="2026-06-29",
        carrier="Maersk",
        shipper="Thanh Cong Plastics JSC",
        consignee="Pacific Home Supply Inc.",
        status_bucket="Đang vận chuyển",
    ),
    "waiting_export": ContainerProfile(
        key="waiting_export",
        container_no="SEKU6678912",
        booking_no="YML-BKG-260610",
        hbl_no="HBL-SGNMNL-6678",
        mbl_no="YMLSGN260610",
        po_no="PO-PH-33210",
        commodity="Printed packaging",
        quantity="1 x 20GP / 386 rolls",
        pol="Cat Lai",
        pod="Manila",
        vessel_voyage="YM WISDOM 072S",
        etd="2026-06-13",
        eta="2026-06-17",
        carrier="Yang Ming",
        shipper="Bao Tin Packaging Co., Ltd.",
        consignee="Luzon Retail Solutions Corp.",
        status_bucket="Chờ xuất cảng",
    ),
    "waiting_customs": ContainerProfile(
        key="waiting_customs",
        container_no="FSCU3301847",
        booking_no="CMA-BKG-260528",
        hbl_no="HBL-SGNJKT-3301",
        mbl_no="CMDUSGN260528",
        po_no="PO-ID-77104",
        commodity="Frozen seafood",
        quantity="1 x 40RF / 2,180 cartons",
        pol="Cat Lai",
        pod="Jakarta",
        vessel_voyage="CMA CGM ELBE 209N",
        etd="2026-05-28",
        eta="2026-06-09",
        carrier="CMA CGM",
        shipper="Blue Delta Seafood Ltd.",
        consignee="Java Cold Chain PT",
        status_bucket="Chờ thông quan",
    ),
    "waiting_docs": ContainerProfile(
        key="waiting_docs",
        container_no="CMAU1182456",
        booking_no="EMC-BKG-260607",
        hbl_no="HBL-SGNBKK-1182",
        mbl_no="EGLVSGN260607",
        po_no="PO-TH-88118",
        commodity="Garment accessories",
        quantity="1 x 20GP / 540 cartons",
        pol="Cat Lai",
        pod="Bangkok",
        vessel_voyage="EVER LUCENT 052N",
        etd="2026-06-07",
        eta="2026-06-11",
        carrier="Evergreen",
        shipper="May Sao Viet Accessories Co., Ltd.",
        consignee="Bangkok Sourcing Hub Co., Ltd.",
        status_bucket="Chờ chứng từ",
    ),
    "missing_data": ContainerProfile(
        key="missing_data",
        container_no="TEMU5522441",
        booking_no="OOL-BKG-260609",
        hbl_no="",
        mbl_no="OOLU-SGN260609",
        po_no="PO-MY-45091",
        commodity="LED driver modules",
        quantity="1 x 20GP / 265 cartons",
        pol="Hai Phong",
        pod="Port Klang",
        vessel_voyage="OOCL BRUSSELS 091S",
        etd="2026-06-09",
        eta="2026-06-16",
        carrier="OOCL",
        shipper="Phu Minh Lighting Components",
        consignee="Selangor Tech Distribution Sdn. Bhd.",
        status_bucket="Thiếu dữ liệu",
    ),
}


# ---------------------------------------------------------------------------
# Hồ sơ chạy theo kịch bản (thread)
#
# 6 hồ sơ ở trên được viết tay từng thư. 10 hồ sơ dưới đây đi theo KỊCH BẢN 5
# bước, có cả mail đến lẫn mail đi, vì một hộp thư giao nhận thật không bao giờ
# chỉ toàn thư hãng tàu gửi tới — nửa số chứng từ đi ra từ chính công ty.
# ---------------------------------------------------------------------------
THREAD_PROFILES: dict[str, ContainerProfile] = {
    "export_yokohama": ContainerProfile(
        key="export_yokohama",
        container_no="MSKU4120885",
        booking_no="MSK-BKG-260615",
        hbl_no="HBL-SGNYOK-4120",
        mbl_no="MAEUHCM260615",
        po_no="PO-JP-60215",
        commodity="Rattan furniture",
        quantity="1 x 40HC / 640 cartons",
        pol="Cat Lai",
        pod="Yokohama",
        vessel_voyage="MAERSK SAIGON 214N",
        etd="2026-06-18",
        eta="2026-06-27",
        carrier="Maersk",
        shipper="An Phat Rattan Co., Ltd.",
        consignee="Kanto Living Trading K.K.",
        status_bucket="Chờ xuất cảng",
        carrier_email="booking.vn@maersk-demo.com",
        customer_email="export@anphatrattan.vn",
    ),
    "export_busan": ContainerProfile(
        key="export_busan",
        container_no="HLXU8305142",
        booking_no="HLC-BKG-260616",
        hbl_no="HBL-HPHPUS-8305",
        mbl_no="HLCUHPH260616",
        po_no="PO-KR-71408",
        commodity="Electronic components",
        quantity="1 x 20GP / 410 cartons",
        pol="Hai Phong",
        pod="Busan",
        vessel_voyage="HANSA MERIDIAN 133E",
        etd="2026-06-19",
        eta="2026-06-25",
        carrier="Hapag-Lloyd",
        shipper="Tien Phong Electronics JSC",
        consignee="Daehan Components Co., Ltd.",
        status_bucket="Chờ xuất cảng",
        carrier_email="vn.booking@hapag-demo.com",
        customer_email="logistics@tienphongelec.vn",
    ),
    "import_shanghai": ContainerProfile(
        key="import_shanghai",
        container_no="ZIMU2776311",
        booking_no="ZIM-BKG-260602",
        hbl_no="HBL-SHACLI-2776",
        mbl_no="ZIMUSHA260602",
        po_no="PO-VN-90233",
        commodity="Textile machinery parts",
        quantity="1 x 40GP / 92 crates",
        pol="Shanghai",
        pod="Cat Lai",
        vessel_voyage="ZIM QINGDAO 042S",
        etd="2026-06-02",
        eta="2026-06-12",
        carrier="ZIM",
        shipper="Huadong Machinery Co., Ltd.",
        consignee="Dong Tien Textile JSC",
        status_bucket="Chờ thông quan",
        carrier_email="import.vn@zim-demo.com",
        customer_email="xnk@dongtientextile.vn",
        agent_email="prealert@sha-agent-demo.cn",
        customs_email="thongbao@haiquan-demo.gov.vn",
    ),
    "import_busan": ContainerProfile(
        key="import_busan",
        container_no="KMTU5901421",
        booking_no="KMT-BKG-260604",
        hbl_no="HBL-PUSHPH-5901",
        mbl_no="KMTCPUS260604",
        po_no="PO-VN-90417",
        commodity="Stainless steel coils",
        quantity="1 x 20GP / 18 coils",
        pol="Busan",
        pod="Hai Phong",
        vessel_voyage="KMTC NAGOYA 2612S",
        etd="2026-06-04",
        eta="2026-06-11",
        carrier="KMTC",
        shipper="Hanil Steel Corp.",
        consignee="Thep Viet Nam Trading Co., Ltd.",
        status_bucket="Chờ thông quan",
        carrier_email="import@kmtc-demo.com",
        customer_email="muahang@thepvietnam.vn",
        agent_email="docs@pus-agent-demo.kr",
        customs_email="thongbao@haiquan-demo.gov.vn",
    ),
    "quote_singapore": ContainerProfile(
        key="quote_singapore",
        container_no="WHLU6612093",
        booking_no="WHL-BKG-260620",
        hbl_no="HBL-DADSIN-6612",
        mbl_no="WHLCDAD260620",
        po_no="PO-SG-22087",
        commodity="Coffee beans",
        quantity="1 x 20GP / 320 bags",
        pol="Da Nang",
        pod="Singapore",
        vessel_voyage="WAN HAI 215 026S",
        etd="2026-06-23",
        eta="2026-06-28",
        carrier="Wan Hai Lines",
        shipper="Tay Nguyen Coffee Export Co., Ltd.",
        consignee="Lion City Commodities Pte. Ltd.",
        status_bucket="Chờ chứng từ",
        carrier_email="booking@wanhai-demo.com",
        customer_email="sales@taynguyencoffee.vn",
    ),
    "quote_chennai": ContainerProfile(
        key="quote_chennai",
        container_no="SUDU3347800",
        booking_no="SUD-BKG-260621",
        hbl_no="HBL-SGNMAA-3347",
        mbl_no="SUDUHCM260621",
        po_no="PO-IN-55190",
        commodity="Cashew kernels",
        quantity="1 x 20GP / 700 cartons",
        pol="Cat Lai",
        pod="Chennai",
        vessel_voyage="SEALAND MADRAS 118W",
        etd="2026-06-25",
        eta="2026-07-06",
        carrier="Sealand",
        shipper="Binh Phuoc Cashew JSC",
        consignee="Coromandel Foods Pvt. Ltd.",
        status_bucket="Chờ chứng từ",
        carrier_email="vn.sales@sealand-demo.com",
        customer_email="kinhdoanh@binhphuoccashew.vn",
    ),
    "delivery_binhduong": ContainerProfile(
        key="delivery_binhduong",
        container_no="PONU7150630",
        booking_no="PON-BKG-260527",
        hbl_no="HBL-KHHCLI-7150",
        mbl_no="PONUKHH260527",
        po_no="PO-VN-31022",
        commodity="PP resin",
        quantity="1 x 20GP / 20 tons",
        pol="Kaohsiung",
        pod="Cat Lai",
        vessel_voyage="PANCON SUNRISE 205S",
        etd="2026-05-27",
        eta="2026-06-05",
        carrier="Pan Continental",
        shipper="Formosa Polymer Co., Ltd.",
        consignee="Nhua Binh Duong Co., Ltd.",
        status_bucket="Đã hoàn tất",
        carrier_email="do.vn@pancon-demo.com",
        customer_email="kho@nhuabinhduong.vn",
        trucker_email="dieuxe@vantaidongnam.vn",
    ),
    "delivery_bacninh": ContainerProfile(
        key="delivery_bacninh",
        container_no="TLLU2089457",
        booking_no="TSL-BKG-260529",
        hbl_no="HBL-PUSHPH-2089",
        mbl_no="TSLUPUS260529",
        po_no="PO-VN-31148",
        commodity="Display panels",
        quantity="1 x 40HC / 288 cartons",
        pol="Busan",
        pod="Hai Phong",
        vessel_voyage="TS TOKYO 2611N",
        etd="2026-05-29",
        eta="2026-06-06",
        carrier="TS Lines",
        shipper="Sejong Display Co., Ltd.",
        consignee="Bac Ninh Electronics Assembly Co., Ltd.",
        status_bucket="Đã hoàn tất",
        carrier_email="do@tslines-demo.com",
        customer_email="nhanhang@bacninhassembly.vn",
        trucker_email="dispatch@vantaiphuongbac.vn",
    ),
    "finance_rotterdam": ContainerProfile(
        key="finance_rotterdam",
        container_no="APZU8741204",
        booking_no="CMA-BKG-260512",
        hbl_no="HBL-SGNRTM-8741",
        mbl_no="CMDUSGN260512",
        po_no="PO-NL-40761",
        commodity="Bamboo homeware",
        quantity="1 x 40HC / 905 cartons",
        pol="Cat Lai",
        pod="Rotterdam",
        vessel_voyage="CMA CGM SCANDOLA 318W",
        etd="2026-05-12",
        eta="2026-06-14",
        carrier="CMA CGM",
        shipper="Truong Thinh Bamboo Co., Ltd.",
        consignee="Lowlands Home BV",
        status_bucket="Đang vận chuyển",
        carrier_email="billing.vn@cma-demo.com",
        customer_email="ketoan@truongthinhbamboo.vn",
    ),
    "finance_osaka": ContainerProfile(
        key="finance_osaka",
        container_no="BEAU5033684",
        booking_no="ONE-BKG-260518",
        hbl_no="HBL-HPHOSA-5033",
        mbl_no="ONEYHPH260518",
        po_no="PO-JP-60480",
        commodity="Ceramic tableware",
        quantity="1 x 20GP / 480 cartons",
        pol="Hai Phong",
        pod="Osaka",
        vessel_voyage="ONE HARBOUR 077E",
        etd="2026-05-18",
        eta="2026-05-28",
        carrier="Ocean Network Express",
        shipper="Bat Trang Ceramics JSC",
        consignee="Naniwa Household Co., Ltd.",
        status_bucket="Đang vận chuyển",
        carrier_email="billing@one-demo.com",
        customer_email="ketoan@battrangceramics.vn",
    ),
    # Hồ sơ cho vòng hỏi giá khép kín. Số container ở đây là "sẽ có sau khi
    # đặt chỗ" — cả 4 thư của vòng này đều phát sinh TRƯỚC lúc có container,
    # nên không thư nào được nhắc tới nó.
    "roundtrip_rfq": ContainerProfile(
        key="roundtrip_rfq",
        container_no="MSKU6512347",
        booking_no="WHL-BKG-260710",
        hbl_no="",
        mbl_no="",
        po_no="PO-SG-77420",
        commodity="Hạt điều rang muối",
        quantity="1 x 20GP",
        pol="Cat Lai",
        pod="Singapore",
        vessel_voyage="WAN HAI 273 041S",
        etd="2026-07-10",
        eta="2026-07-15",
        carrier="Wan Hai Lines",
        shipper="Cong ty TNHH Hat Dieu Phuong Nam",
        consignee="Lion City Commodities Pte. Ltd.",
        status_bucket="Chờ chứng từ",
        carrier_email="booking@wanhai-demo.com",
        customer_email="xnk@hatdieuphuongnam.vn",
    ),
    # Vòng hỏi giá thứ hai: tuyến khác, hàng khác, và quan trọng hơn là bảng
    # phí có dòng SỐ LƯỢNG 2 — để kiểm đúng nhánh chia thành tiền cho số lượng
    # ra đơn giá, thứ mà vòng đầu (mọi dòng đều x1) không chạm tới.
    "roundtrip_rfq_hpn": ContainerProfile(
        key="roundtrip_rfq_hpn",
        container_no="ONEU7041287",
        booking_no="ONE-BKG-260805",
        hbl_no="",
        mbl_no="",
        po_no="PO-JP-88315",
        commodity="Áo sơ mi cotton",
        quantity="2 x 40HC",
        pol="Hai Phong",
        pod="Yokohama",
        vessel_voyage="ONE COMMITMENT 145E",
        etd="2026-08-20",
        eta="2026-08-29",
        carrier="Ocean Network Express",
        shipper="Cong ty CP Det May Thanh Long",
        consignee="Sakura Apparel Trading K.K.",
        status_bucket="Chờ chứng từ",
        carrier_email="booking.vn@one-demo.com",
        customer_email="xuatkhau@detmaythanhlong.vn",
    ),
}

PROFILES.update(THREAD_PROFILES)


def _escape_pdf_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _build_text_pdf_bytes(lines: list[str]) -> bytes:
    text_lines = [_escape_pdf_text(line) for line in lines if line.strip()]
    if not text_lines:
        text_lines = ["Agentify demo PDF"]

    content_lines = ["BT", "/F1 11 Tf", "50 780 Td", "14 TL"]
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


def _build_eml_bytes(
    record: EmailRecord,
    pdf_bytes: bytes | None,
    *,
    message_id: str,
    in_reply_to: str | None = None,
) -> bytes:
    sent_at = record.sent_at
    if re.search(r" [+-]\d{2}$", sent_at):
        sent_at = f"{sent_at}00"

    message = EmailMessage()
    message["Subject"] = record.title
    message["To"] = record.to_email
    message["From"] = record.from_email
    message["Date"] = format_datetime(datetime.strptime(sent_at, "%Y-%m-%d %H:%M %z"))
    message["Message-ID"] = message_id
    message["X-Agentify-Direction"] = record.direction
    if in_reply_to:
        message["In-Reply-To"] = in_reply_to
        message["References"] = in_reply_to
    message.set_content(record.body.strip())
    if pdf_bytes is not None and record.pdf_name:
        message.add_attachment(
            pdf_bytes,
            maintype="application",
            subtype="pdf",
            filename=record.pdf_name,
        )
    return message.as_bytes()


def _attachment_lines(
    profile: ContainerProfile,
    doc_type: str,
    extra_lines: list[str],
    *,
    omit_container: bool = False,
    omit_hbl: bool = False,
    omit_booking: bool = False,
    omit_mbl: bool = False,
    omit_vessel: bool = False,
) -> tuple[str, ...]:
    lines = [f"Document Type: {doc_type}"]
    if not omit_container:
        lines.append(f"Container No: {profile.container_no}")
    if not omit_booking:
        lines.append(f"Booking No: {profile.booking_no}")
    lines.append(f"PO No: {profile.po_no}")
    lines.extend(
        [
            f"POL: {profile.pol}",
            f"POD: {profile.pod}",
        ]
    )
    if not omit_vessel:
        lines.append(f"Vessel/Voyage: {profile.vessel_voyage}")
    lines.extend(
        [
            f"ETD: {profile.etd}",
            f"ETA: {profile.eta}",
            f"Shipper: {profile.shipper}",
            f"Consignee: {profile.consignee}",
            f"Commodity: {profile.commodity}",
            f"Quantity: {profile.quantity}",
        ]
    )
    if profile.hbl_no and not omit_hbl:
        lines.append(f"HBL No: {profile.hbl_no}")
    if profile.mbl_no and not omit_mbl:
        lines.append(f"MBL No: {profile.mbl_no}")
    lines.extend(extra_lines)
    return tuple(lines)


def _record(
    seq: int,
    profile: ContainerProfile,
    slug: str,
    title: str,
    body: str,
    from_email: str,
    sent_at: str,
    pdf_name: str,
    pdf_lines: tuple[str, ...],
    *,
    direction: str = INBOUND,
    to_email: str = TARGET_TO,
    reply_to_slug: str | None = None,
) -> EmailRecord:
    return EmailRecord(
        seq=seq,
        slug=slug,
        container_key=profile.key,
        title=title,
        body=body,
        from_email=from_email,
        sent_at=sent_at,
        pdf_name=pdf_name,
        pdf_lines=pdf_lines,
        direction=direction,
        to_email=to_email,
        reply_to_slug=reply_to_slug,
    )


@dataclass(frozen=True)
class ThreadStep:
    """Một bước trong kịch bản. Text dùng `{field}` theo tên field của ContainerProfile."""

    suffix: str
    direction: str
    partner: str  # carrier | customer | agent | trucker | customs
    subject: str
    body: str
    day_offset: int
    sent_time: str
    # doc_type rỗng nghĩa là thư không đính kèm — reply thuần text, rất phổ biến
    # trong thực tế và là đường trích xuất từ body chứ không từ PDF.
    doc_type: str = ""
    pdf_stem: str = ""
    extra_lines: tuple[str, ...] = ()
    omit_container: bool = False
    # Chứng từ phát hành TRƯỚC khi đặt chỗ (báo giá): chưa thể có container,
    # booking, vận đơn hay tên tàu. Nếu vẫn in ra thì corpus dạy sai luồng
    # nghiệp vụ và mọi phép đo trích xuất trên nó đều vô nghĩa.
    pre_booking: bool = False
    # Chặng hội thoại, ví dụ "KHÁCH>AGENTIFY". Khi cả 4 chặng cùng chạy vào MỘT
    # hộp thư test, From/To bị `send_demo_emails.py` ghi đè thành cùng một địa
    # chỉ — nhãn ở tiêu đề là thứ duy nhất còn phân biệt được ai gửi cho ai.
    leg: str = ""


@dataclass(frozen=True)
class ThreadPlan:
    profile_key: str
    scenario: str
    start_date: date


def _partner_email(profile: ContainerProfile, partner: str) -> str:
    mapping = {
        "carrier": profile.carrier_email,
        "customer": profile.customer_email,
        "agent": profile.agent_email,
        "trucker": profile.trucker_email,
        "customs": profile.customs_email,
    }
    email = mapping.get(partner, "")
    if not email:
        # Không im lặng rơi về địa chỉ rỗng: một From rỗng làm .eml hỏng theo
        # kiểu chỉ lộ ra khi gửi SMTP thật.
        raise ValueError(f"Profile {profile.key!r} thiếu email cho vai trò {partner!r}")
    return email


def _fill(text: str, profile: ContainerProfile) -> str:
    return text.format(
        container_no=profile.container_no,
        booking_no=profile.booking_no,
        hbl_no=profile.hbl_no,
        mbl_no=profile.mbl_no,
        po_no=profile.po_no,
        commodity=profile.commodity,
        quantity=profile.quantity,
        pol=profile.pol,
        pod=profile.pod,
        vessel_voyage=profile.vessel_voyage,
        etd=profile.etd,
        eta=profile.eta,
        carrier=profile.carrier,
        shipper=profile.shipper,
        consignee=profile.consignee,
    )


def _thread_records(
    start_seq: int,
    profile: ContainerProfile,
    steps: tuple[ThreadStep, ...],
    start_date: date,
) -> list[EmailRecord]:
    records: list[EmailRecord] = []
    previous_slug: str | None = None

    for index, step in enumerate(steps):
        slug = f"{profile.key.replace('_', '-')}-{step.suffix}"
        partner_email = _partner_email(profile, step.partner)
        outbound = step.direction == OUTBOUND
        sent_on = start_date + timedelta(days=step.day_offset)
        sent_at = f"{sent_on.isoformat()} {step.sent_time} +07"

        if step.doc_type:
            pdf_name = f"{step.pdf_stem}_{profile.container_no.lower()}.pdf"
            pdf_lines = _attachment_lines(
                profile,
                step.doc_type,
                [_fill(line, profile) for line in step.extra_lines],
                omit_container=step.omit_container or step.pre_booking,
                omit_booking=step.pre_booking,
                omit_hbl=step.pre_booking,
                omit_mbl=step.pre_booking,
                omit_vessel=step.pre_booking,
            )
        else:
            pdf_name = ""
            pdf_lines = ()

        subject = _fill(step.subject, profile)
        if step.leg:
            # `DEMO_TAG` đứng trước để lọc được cả vòng bằng một câu Gmail
            # query duy nhất; nhãn chặng đứng sau để đọc là biết ai gửi ai.
            subject = f"{DEMO_TAG}[{step.leg}] {subject}"

        records.append(
            _record(
                start_seq + index,
                profile,
                slug,
                subject,
                _fill(step.body, profile),
                AGENTIFY_SELF if outbound else partner_email,
                sent_at,
                pdf_name,
                pdf_lines,
                direction=step.direction,
                to_email=partner_email if outbound else TARGET_TO,
                reply_to_slug=previous_slug,
            )
        )
        previous_slug = slug

    return records


# Thư gửi hãng tàu / đại lý nước ngoài viết tiếng Anh, thư gửi khách hàng và
# nhà xe trong nước viết tiếng Việt — đúng thói quen của một forwarder Việt Nam,
# và cũng là phép thử xem trích xuất có phụ thuộc ngôn ngữ hay không.
SCENARIO_EXPORT_FCL: tuple[ThreadStep, ...] = (
    ThreadStep(
        suffix="booking-request",
        direction=OUTBOUND,
        partner="carrier",
        subject="Booking request {pol} - {pod} / PO {po_no}",
        body=(
            "Dear {carrier} Booking Team,\n\n"
            "Please arrange a booking for {quantity}, commodity {commodity}.\n"
            "POL {pol}, POD {pod}, target ETD {etd}.\n"
            "Shipper: {shipper}\n"
            "Consignee: {consignee}\n"
            "Our PO reference: {po_no}\n\n"
            "Kindly confirm space and cut-off times.\n\n"
            "Best regards,\nAgentify Forwarding - Export Desk"
        ),
        day_offset=0,
        sent_time="08:45",
    ),
    ThreadStep(
        suffix="booking-confirmation",
        direction=INBOUND,
        partner="carrier",
        subject="Booking confirmed {booking_no} / {container_no}",
        body=(
            "Dear Agentify,\n\n"
            "Booking {booking_no} is confirmed on {vessel_voyage}.\n"
            "Container {container_no} is allocated, ETD {etd} and ETA {eta}.\n\n"
            "Regards,\n{carrier} Customer Service"
        ),
        day_offset=1,
        sent_time="10:20",
        doc_type="Booking Confirmation",
        pdf_stem="booking_confirmation",
        extra_lines=("Status: Booking confirmed", "SI cut-off: {etd}", "VGM cut-off: {etd}"),
    ),
    ThreadStep(
        suffix="si-submission",
        direction=OUTBOUND,
        partner="carrier",
        subject="SI submission {booking_no} / {container_no}",
        body=(
            "Dear {carrier} Documentation Team,\n\n"
            "Please find attached our shipping instruction for booking {booking_no}, "
            "container {container_no}.\n"
            "House B/L number to be shown: {hbl_no}\n\n"
            "Please issue the draft B/L once processed.\n\n"
            "Best regards,\nAgentify Forwarding - Documentation"
        ),
        day_offset=2,
        sent_time="15:30",
        doc_type="Shipping Instruction",
        pdf_stem="shipping_instruction",
        extra_lines=("Freight Term: FOB {pol}", "Notify Party: Same as consignee"),
    ),
    ThreadStep(
        suffix="vgm-cutoff-reminder",
        direction=INBOUND,
        partner="carrier",
        subject="Reminder: VGM and gate-in cut-off for {container_no}",
        body=(
            "Dear Agentify,\n\n"
            "This is a reminder that VGM for container {container_no} under booking "
            "{booking_no} has not been received yet.\n"
            "Gate-in cut-off at {pol} closes one day before ETD {etd}.\n\n"
            "Regards,\n{carrier} Operations"
        ),
        day_offset=3,
        sent_time="09:05",
    ),
    ThreadStep(
        suffix="onboard-draft-bl",
        direction=INBOUND,
        partner="carrier",
        subject="On board {container_no} / draft B/L {mbl_no}",
        body=(
            "Dear Agentify,\n\n"
            "Container {container_no} is on board {vessel_voyage}. "
            "Draft bill of lading {mbl_no} is attached for your check.\n"
            "ETA {pod} is {eta}.\n\n"
            "Regards,\n{carrier} Documentation"
        ),
        day_offset=5,
        sent_time="18:40",
        doc_type="Draft Bill of Lading",
        pdf_stem="draft_bl",
        extra_lines=("Status: Vessel departed", "Draft only: Yes", "Number of originals: 3"),
    ),
)

SCENARIO_IMPORT_CUSTOMS: tuple[ThreadStep, ...] = (
    ThreadStep(
        suffix="prealert",
        direction=INBOUND,
        partner="agent",
        subject="Pre-alert {container_no} / {pol} to {pod}",
        body=(
            "Dear Agentify,\n\n"
            "Please find attached the pre-alert for container {container_no} shipped on "
            "{vessel_voyage}.\n"
            "House B/L {hbl_no}, master B/L {mbl_no}, ETA {pod} {eta}.\n\n"
            "Best regards,\nOverseas Agent"
        ),
        day_offset=0,
        sent_time="11:10",
        doc_type="Pre Alert",
        pdf_stem="prealert",
        extra_lines=("Status: In transit", "Original docs sent: Yes", "Telex release: Pending"),
    ),
    ThreadStep(
        suffix="docs-request",
        direction=OUTBOUND,
        partner="customer",
        subject="Đề nghị gửi bộ chứng từ lô {container_no} / {po_no}",
        body=(
            "Kính gửi Quý khách,\n\n"
            "Lô hàng container {container_no}, vận đơn {hbl_no} dự kiến cập cảng {pod} "
            "ngày {eta}.\n"
            "Để kịp mở tờ khai, nhờ Quý khách gửi giúp invoice, packing list và C/O "
            "trước ngày tàu đến.\n\n"
            "Trân trọng,\nAgentify - Bộ phận Chứng từ"
        ),
        day_offset=2,
        sent_time="09:30",
    ),
    ThreadStep(
        suffix="invoice-packing-list",
        direction=INBOUND,
        partner="customer",
        subject="Chứng từ lô {container_no} / invoice và packing list",
        body=(
            "Chào bạn,\n\n"
            "Bên mình gửi invoice và packing list cho lô {container_no}, "
            "PO {po_no}, hàng {commodity}.\n"
            "Nhờ bạn kiểm tra và báo lại nếu còn thiếu gì.\n\n"
            "Cảm ơn,\nPhòng Xuất nhập khẩu"
        ),
        day_offset=4,
        sent_time="16:15",
        doc_type="Commercial Invoice",
        pdf_stem="commercial_invoice",
        extra_lines=(
            "Invoice No: INV-{po_no}",
            "Invoice Amount: USD 48,250.00",
            "Payment Term: TT 30 days",
            "Incoterm: CIF {pod}",
        ),
    ),
    ThreadStep(
        suffix="customs-declaration",
        direction=OUTBOUND,
        partner="customer",
        subject="Tờ khai nhập khẩu lô {container_no} - nhờ xác nhận",
        body=(
            "Kính gửi Quý khách,\n\n"
            "Agentify đã lên tờ khai nhập khẩu cho lô {container_no} theo vận đơn {hbl_no}.\n"
            "Nhờ Quý khách kiểm tra mã HS và trị giá khai báo trong file đính kèm, "
            "xác nhận trước 16h hôm nay để bên mình truyền tờ khai.\n\n"
            "Trân trọng,\nAgentify - Bộ phận Hải quan"
        ),
        day_offset=6,
        sent_time="10:50",
        doc_type="Customs Declaration",
        pdf_stem="customs_declaration",
        extra_lines=(
            "Declaration No: 105892374610",
            "Declaration Type: A11 - Nhap kinh doanh tieu dung",
            "HS Code: 8448.59.00",
            "Taxable Value: VND 1,182,400,000",
        ),
    ),
    ThreadStep(
        suffix="channel-and-charges",
        direction=INBOUND,
        partner="customs",
        subject="Thông báo phân luồng tờ khai 105892374610 / {container_no}",
        body=(
            "Kính gửi doanh nghiệp,\n\n"
            "Tờ khai 105892374610 cho container {container_no} được phân luồng vàng, "
            "đề nghị xuất trình hồ sơ giấy tại chi cục.\n"
            "Container đang lưu bãi tại {pod}, thời hạn miễn phí lưu container còn 3 ngày.\n\n"
            "Trân trọng."
        ),
        day_offset=7,
        sent_time="08:20",
        doc_type="Customs Clearance Notice",
        pdf_stem="customs_notice",
        extra_lines=(
            "Declaration No: 105892374610",
            "Channel: Yellow",
            "Free time days: 3",
            "Status: Waiting customs clearance",
        ),
    ),
)

SCENARIO_QUOTE_TO_BOOKING: tuple[ThreadStep, ...] = (
    ThreadStep(
        suffix="rfq",
        direction=INBOUND,
        partner="customer",
        subject="Hỏi giá cước {pol} đi {pod} / {commodity}",
        body=(
            "Chào Agentify,\n\n"
            "Bên mình cần báo giá cước biển cho lô {commodity}, khoảng {quantity}, "
            "đi từ {pol} tới {pod}, hàng sẵn khoảng ngày {etd}.\n"
            "PO tham chiếu {po_no}. Nhờ bạn báo giá kèm phụ phí local và thời gian "
            "miễn phí lưu container.\n\n"
            "Cảm ơn,\nPhòng Kinh doanh"
        ),
        day_offset=0,
        sent_time="14:05",
    ),
    ThreadStep(
        suffix="quotation",
        direction=OUTBOUND,
        partner="customer",
        subject="Báo giá cước {pol} - {pod} / {po_no}",
        body=(
            "Kính gửi Quý khách,\n\n"
            "Agentify xin gửi báo giá cho lô {commodity} tuyến {pol} - {pod}, "
            "hãng tàu dự kiến {carrier}.\n"
            "Chi tiết cước và phụ phí trong file đính kèm, báo giá có hiệu lực 14 ngày.\n\n"
            "Trân trọng,\nAgentify - Bộ phận Kinh doanh"
        ),
        day_offset=1,
        sent_time="11:40",
        doc_type="Quotation",
        pdf_stem="quotation",
        extra_lines=(
            "Quotation No: QT-{po_no}",
            "Ocean Freight: USD 780 / 20GP",
            "THC: VND 3,300,000",
            "Free time days: 7",
            "Validity: 14 days",
        ),
        pre_booking=True,
    ),
    ThreadStep(
        suffix="quote-approval",
        direction=INBOUND,
        partner="customer",
        subject="Re: Báo giá cước {pol} - {pod} / duyệt giá",
        body=(
            "Chào bạn,\n\n"
            "Bên mình duyệt mức giá trong báo giá QT-{po_no}. "
            "Nhờ Agentify đặt chỗ với {carrier} cho ngày tàu chạy {etd}.\n\n"
            "Cảm ơn,\nPhòng Kinh doanh"
        ),
        day_offset=3,
        sent_time="09:15",
    ),
    ThreadStep(
        suffix="booking-to-customer",
        direction=OUTBOUND,
        partner="customer",
        subject="Xác nhận booking {booking_no} / container {container_no}",
        body=(
            "Kính gửi Quý khách,\n\n"
            "Agentify đã đặt chỗ thành công booking {booking_no} với {carrier}, "
            "container {container_no} trên tàu {vessel_voyage}.\n"
            "ETD {pol} ngày {etd}, ETA {pod} ngày {eta}.\n\n"
            "Trân trọng,\nAgentify - Bộ phận Kinh doanh"
        ),
        day_offset=4,
        sent_time="17:25",
        doc_type="Booking Confirmation",
        pdf_stem="booking_confirmation",
        extra_lines=("Status: Booking confirmed", "Quotation No: QT-{po_no}"),
    ),
    ThreadStep(
        suffix="empty-release",
        direction=INBOUND,
        partner="carrier",
        subject="Empty release order {booking_no} / {container_no}",
        body=(
            "Dear Agentify,\n\n"
            "Empty release order for booking {booking_no} is attached. "
            "Container {container_no} can be picked up at the depot from today.\n"
            "Please return the laden container before the gate-in cut-off.\n\n"
            "Regards,\n{carrier} Equipment Control"
        ),
        day_offset=5,
        sent_time="08:35",
        doc_type="Empty Release Order",
        pdf_stem="empty_release_order",
        extra_lines=("Status: Empty released", "Depot: {pol} inland depot"),
    ),
)

SCENARIO_DELIVERY_POD: tuple[ThreadStep, ...] = (
    ThreadStep(
        suffix="delivery-order",
        direction=INBOUND,
        partner="carrier",
        subject="Delivery order {container_no} / {mbl_no}",
        body=(
            "Dear Agentify,\n\n"
            "Delivery order for container {container_no} under B/L {mbl_no} is attached.\n"
            "The container is available at {pod} terminal. Free time expires in 5 days.\n\n"
            "Regards,\n{carrier} Import Desk"
        ),
        day_offset=0,
        sent_time="09:50",
        doc_type="Delivery Order",
        pdf_stem="delivery_order",
        extra_lines=("DO No: DO-{booking_no}", "Free time days: 5", "Status: Available for pickup"),
    ),
    ThreadStep(
        suffix="trucking-dispatch",
        direction=OUTBOUND,
        partner="trucker",
        subject="Lệnh điều xe lấy container {container_no} tại {pod}",
        body=(
            "Gửi bộ phận điều xe,\n\n"
            "Nhờ nhà xe bố trí đầu kéo lấy container {container_no} tại cảng {pod} "
            "theo lệnh giao hàng DO-{booking_no}.\n"
            "Hàng {commodity}, giao tại kho khách hàng {consignee}.\n"
            "Nhờ tài xế chụp ảnh phiếu EIR và biên bản giao hàng sau khi hạ hàng.\n\n"
            "Trân trọng,\nAgentify - Bộ phận Hiện trường"
        ),
        day_offset=1,
        sent_time="07:40",
        doc_type="Trucking Dispatch Order",
        pdf_stem="trucking_dispatch",
        extra_lines=("DO No: DO-{booking_no}", "Delivery address: Kho {consignee}"),
    ),
    ThreadStep(
        suffix="driver-pickup-note",
        direction=INBOUND,
        partner="trucker",
        subject="Re: Lệnh điều xe {container_no} / đã lấy hàng",
        body=(
            "Chào anh,\n\n"
            "Xe đã lấy container {container_no} ra khỏi cảng {pod} lúc 10h30 sáng nay, "
            "dự kiến hạ hàng tại kho khách chiều nay.\n"
            "Vỏ container sẽ trả depot sau khi rút hàng xong.\n\n"
            "Tài xế: Nguyễn Văn Bảy - xe 51C-234.56"
        ),
        day_offset=1,
        sent_time="10:45",
    ),
    ThreadStep(
        suffix="eir",
        direction=INBOUND,
        partner="trucker",
        subject="Phiếu EIR container {container_no}",
        body=(
            "Chào anh,\n\n"
            "Bên mình gửi phiếu giao nhận container {container_no} có xác nhận của cảng.\n"
            "Tình trạng vỏ bình thường, không ghi nhận hư hỏng.\n\n"
            "Trân trọng,\nBộ phận Điều vận"
        ),
        day_offset=1,
        sent_time="15:20",
        doc_type="Equipment Interchange Receipt",
        pdf_stem="eir",
        extra_lines=("Seal No: SL-8842190", "Container condition: Sound", "Status: Gate out"),
    ),
    ThreadStep(
        suffix="pod-to-customer",
        direction=OUTBOUND,
        partner="customer",
        subject="Biên bản giao hàng container {container_no} / {po_no}",
        body=(
            "Kính gửi Quý khách,\n\n"
            "Lô hàng {commodity} thuộc container {container_no} đã giao xong tại kho.\n"
            "Agentify gửi kèm biên bản giao hàng có ký nhận. Vỏ container đã trả depot, "
            "hồ sơ lô hàng khép lại.\n\n"
            "Trân trọng,\nAgentify - Bộ phận Hiện trường"
        ),
        day_offset=2,
        sent_time="09:10",
        doc_type="Proof of Delivery",
        pdf_stem="proof_of_delivery",
        extra_lines=("Status: Delivered", "Received by: Kho {consignee}", "Empty returned: Yes"),
    ),
)

SCENARIO_FINANCE_DEBIT: tuple[ThreadStep, ...] = (
    ThreadStep(
        suffix="debit-note",
        direction=OUTBOUND,
        partner="customer",
        subject="Debit note lô {container_no} / booking {booking_no}",
        body=(
            "Kính gửi Quý khách,\n\n"
            "Agentify gửi debit note cho lô hàng container {container_no}, "
            "tuyến {pol} - {pod} trên tàu {vessel_voyage}.\n"
            "Nhờ Quý khách đối chiếu và thanh toán theo thời hạn ghi trên chứng từ.\n\n"
            "Trân trọng,\nAgentify - Bộ phận Kế toán"
        ),
        day_offset=0,
        sent_time="14:30",
        doc_type="Debit Note",
        pdf_stem="debit_note",
        extra_lines=(
            "Debit Note No: DN-{booking_no}",
            "Total Amount: VND 62,480,000",
            "Payment Term: 15 days from issue date",
        ),
    ),
    ThreadStep(
        suffix="charge-query",
        direction=INBOUND,
        partner="customer",
        subject="Re: Debit note lô {container_no} / hỏi lại phí",
        body=(
            "Chào bạn,\n\n"
            "Bên mình xem debit note DN-{booking_no} thì thấy có khoản phí chứng từ và "
            "phí niêm phong cao hơn báo giá ban đầu.\n"
            "Nhờ Agentify giải thích giúp phần chênh lệch trước khi bên mình duyệt thanh toán.\n\n"
            "Cảm ơn,\nPhòng Kế toán"
        ),
        day_offset=2,
        sent_time="10:05",
    ),
    ThreadStep(
        suffix="charge-breakdown",
        direction=OUTBOUND,
        partner="customer",
        subject="Giải trình phí debit note DN-{booking_no} / {container_no}",
        body=(
            "Kính gửi Quý khách,\n\n"
            "Agentify gửi bảng kê chi tiết từng khoản phí của debit note DN-{booking_no} "
            "cho container {container_no}.\n"
            "Phần chênh lệch đến từ phụ phí mùa cao điểm của {carrier} áp dụng từ ngày {etd}.\n\n"
            "Trân trọng,\nAgentify - Bộ phận Kế toán"
        ),
        day_offset=3,
        sent_time="16:50",
        doc_type="Charge Breakdown",
        pdf_stem="charge_breakdown",
        extra_lines=(
            "Debit Note No: DN-{booking_no}",
            "Ocean Freight: VND 41,600,000",
            "Documentation Fee: VND 900,000",
            "Peak Season Surcharge: VND 8,300,000",
        ),
    ),
    ThreadStep(
        suffix="payment-confirmation",
        direction=INBOUND,
        partner="customer",
        subject="Re: Debit note DN-{booking_no} / đã chuyển khoản",
        body=(
            "Chào bạn,\n\n"
            "Bên mình đã duyệt và chuyển khoản đủ số tiền của debit note DN-{booking_no} "
            "cho lô {container_no} trong sáng nay.\n"
            "Nhờ Agentify gửi lại hóa đơn VAT.\n\n"
            "Cảm ơn,\nPhòng Kế toán"
        ),
        day_offset=6,
        sent_time="09:25",
    ),
    ThreadStep(
        suffix="demurrage-notice",
        direction=INBOUND,
        partner="carrier",
        subject="Demurrage notice {container_no} / {mbl_no}",
        body=(
            "Dear Agentify,\n\n"
            "Container {container_no} under B/L {mbl_no} has exceeded the agreed free time "
            "at {pod}.\n"
            "Demurrage is accruing from today. Please arrange return of the empty unit.\n\n"
            "Regards,\n{carrier} Equipment Control"
        ),
        day_offset=8,
        sent_time="11:55",
        doc_type="Demurrage Notice",
        pdf_stem="demurrage_notice",
        extra_lines=(
            "Free time days: 7",
            "Demurrage rate: USD 45 / day",
            "Status: Demurrage accruing",
        ),
    ),
)

# Vòng hỏi giá khép kín, chạy trọn trong MỘT hộp thư test.
#
# Bốn chặng: khách hỏi Agentify → Agentify hỏi hãng tàu → hãng tàu trả lời →
# Agentify báo giá khách. Cả bốn đều gửi vào cùng địa chỉ, nên nhãn `leg` ở
# tiêu đề là thứ duy nhất phân biệt được chặng nào là chặng nào.
#
# Thư của hãng tàu (chặng 3) cố ý mang bảng phí trong THÂN THƯ, không phải PDF:
# đó là dạng hãng tàu hay gửi nhất, và là đầu vào cho nút "Nạp phí từ thư hãng
# tàu trả lời" trên trang báo giá.
SCENARIO_RFQ_ROUND_TRIP: tuple[ThreadStep, ...] = (
    ThreadStep(
        suffix="01-khach-hoi-gia",
        leg="KHACH>AGENTIFY",
        direction=INBOUND,
        partner="customer",
        subject="Hỏi giá cước {pol} đi {pod} / {commodity}",
        body=(
            "Chào Agentify,\n\n"
            "Bên mình có lô {commodity} cần xuất đi {pod}, lấy hàng tại {pol}.\n"
            "Số lượng dự kiến {quantity}, hàng sẵn khoảng ngày {etd}.\n"
            "Điều kiện giao hàng FOB. PO tham chiếu {po_no}.\n\n"
            "Nhờ Agentify báo giá cước trọn gói, kèm thời gian miễn phí lưu container "
            "và thời gian vận chuyển.\n\n"
            "Cảm ơn,\nPhòng Xuất nhập khẩu - {shipper}"
        ),
        day_offset=0,
        sent_time="09:15",
    ),
    ThreadStep(
        suffix="02-agentify-hoi-hang-tau",
        leg="AGENTIFY>HANGTAU",
        direction=OUTBOUND,
        partner="carrier",
        subject="Rate request {pol} - {pod} / {quantity} / ref RFQ-{po_no}",
        body=(
            "Dear {carrier} Booking Team,\n\n"
            "We would like to request an ocean freight quotation for the shipment below.\n\n"
            "- Port of loading  : {pol}\n"
            "- Port of discharge: {pod}\n"
            "- Commodity        : {commodity}\n"
            "- Equipment        : {quantity}\n"
            "- Cargo ready date : {etd}\n"
            "- Incoterm         : FOB\n\n"
            "Please quote all-in, breaking down ocean freight, surcharges and local "
            "charges separately, and advise:\n"
            "  1. Free time at destination\n"
            "  2. Transit time and routing\n"
            "  3. Rate validity\n\n"
            "Our reference: RFQ-{po_no}\n\n"
            "Thank you and best regards,\nAgentify Forwarding"
        ),
        day_offset=0,
        sent_time="10:40",
    ),
    ThreadStep(
        suffix="03-hang-tau-bao-gia",
        leg="HANGTAU>AGENTIFY",
        direction=INBOUND,
        partner="carrier",
        subject="RE: Rate request {pol} - {pod} / ref RFQ-{po_no}",
        body=(
            "Dear Agentify,\n\n"
            "Thank you for your enquiry. Please find our quotation below.\n\n"
            "Ocean Freight 20GP         USD 690.00\n"
            "Bunker Adjustment Factor   USD  55.00\n"
            "Container Imbalance Charge USD  40.00\n"
            "Terminal Handling Charge   USD 125.00\n"
            "Documentation fee          USD  35.00\n"
            "Seal fee                   USD   9.00\n\n"
            "Free time at destination: 7 days\n"
            "Transit time: direct service on {vessel_voyage}\n"
            "ETD {pol} {etd} / ETA {pod} {eta}\n"
            "Rate validity: 14 days from today\n\n"
            "Best regards,\n{carrier} - Booking Desk"
        ),
        day_offset=1,
        sent_time="14:25",
    ),
    ThreadStep(
        suffix="04-agentify-bao-gia-khach",
        leg="AGENTIFY>KHACH",
        direction=OUTBOUND,
        partner="customer",
        subject="Báo giá cước {pol} đi {pod} / {po_no}",
        body=(
            "Kính gửi Quý khách,\n\n"
            "Agentify xin gửi báo giá cho lô {commodity} tuyến {pol} - {pod}, "
            "hãng tàu dự kiến {carrier}.\n\n"
            "CHI TIẾT PHÍ\n\n"
            "Cước biển:\n"
            "  - Ocean Freight 20GP: 690.00 USD\n\n"
            "Phụ phí:\n"
            "  - Bunker Adjustment Factor: 55.00 USD\n"
            "  - Container Imbalance Charge: 40.00 USD\n\n"
            "Phí local:\n"
            "  - Terminal Handling Charge: 125.00 USD\n"
            "  - Documentation fee: 35.00 USD\n"
            "  - Seal fee: 9.00 USD\n\n"
            "TỔNG CỘNG: 954.00 USD\n\n"
            "Thời gian miễn phí lưu container tại {pod}: 7 ngày.\n"
            "Báo giá có hiệu lực 14 ngày kể từ hôm nay.\n\n"
            "Rất mong nhận được phản hồi của Quý khách.\n\n"
            "Trân trọng,\nAgentify Forwarding — Bộ phận Kinh doanh"
        ),
        day_offset=1,
        sent_time="16:50",
    ),
)

# Vòng hỏi giá thứ hai. Khác vòng đầu ở hai chỗ có chủ đích: bảng phí của hãng
# tàu có dòng số lượng 2 (kiểm nhánh chia đơn giá), và có phụ phí LSS + phí
# telex release (kiểm bảng phân loại mã phí rộng hơn).
SCENARIO_RFQ_ROUND_TRIP_2: tuple[ThreadStep, ...] = (
    ThreadStep(
        suffix="01-khach-hoi-gia",
        leg="KHACH>AGENTIFY",
        direction=INBOUND,
        partner="customer",
        subject="Cần báo giá {pol} - {pod} cho lô {commodity}",
        body=(
            "Chào Agentify,\n\n"
            "Bên mình có đơn hàng đi Nhật cần báo giá cước.\n"
            "Hàng: {commodity}, đóng {quantity}.\n"
            "Lấy hàng tại {pol}, giao {pod}. Hàng sẵn kho ngày {etd}.\n"
            "Điều kiện FOB, PO {po_no}.\n\n"
            "Nhờ Agentify báo giá sớm giúp, khách Nhật đang giục chốt lịch tàu.\n\n"
            "Trân trọng,\n{shipper}"
        ),
        day_offset=0,
        sent_time="08:30",
    ),
    ThreadStep(
        suffix="02-agentify-hoi-hang-tau",
        leg="AGENTIFY>HANGTAU",
        direction=OUTBOUND,
        partner="carrier",
        subject="Rate request {pol} - {pod} / {quantity} / ref RFQ-{po_no}",
        body=(
            "Dear {carrier} Booking Team,\n\n"
            "We would like to request an ocean freight quotation for the shipment below.\n\n"
            "- Port of loading  : {pol}\n"
            "- Port of discharge: {pod}\n"
            "- Commodity        : {commodity}\n"
            "- Equipment        : {quantity}\n"
            "- Cargo ready date : {etd}\n"
            "- Incoterm         : FOB\n\n"
            "Please quote all-in, breaking down ocean freight, surcharges and local "
            "charges separately, and advise:\n"
            "  1. Free time at destination\n"
            "  2. Transit time and routing\n"
            "  3. Rate validity\n\n"
            "Our reference: RFQ-{po_no}\n\n"
            "Thank you and best regards,\nAgentify Forwarding"
        ),
        day_offset=0,
        sent_time="11:05",
    ),
    ThreadStep(
        suffix="03-hang-tau-bao-gia",
        leg="HANGTAU>AGENTIFY",
        direction=INBOUND,
        partner="carrier",
        subject="RE: Rate request {pol} - {pod} / ref RFQ-{po_no}",
        body=(
            "Dear Agentify,\n\n"
            "Please find our quotation for 2 x 40HC below.\n\n"
            "Ocean Freight 40HC     x2   USD 2,480.00\n"
            "Bunker Adjustment Factor    USD   130.00\n"
            "Low Sulphur Surcharge       USD    88.00\n"
            "Terminal Handling Charge x2 USD   340.00\n"
            "Documentation fee           USD    35.00\n"
            "Telex release fee           USD    30.00\n\n"
            "Free time at destination: 10 days\n"
            "Transit time: direct service on {vessel_voyage}\n"
            "ETD {pol} {etd} / ETA {pod} {eta}\n"
            "Rate validity: 21 days from today\n\n"
            "Best regards,\n{carrier} - Vietnam Booking Desk"
        ),
        day_offset=1,
        sent_time="15:40",
    ),
    ThreadStep(
        suffix="04-agentify-bao-gia-khach",
        leg="AGENTIFY>KHACH",
        direction=OUTBOUND,
        partner="customer",
        subject="Báo giá cước {pol} đi {pod} / {po_no}",
        body=(
            "Kính gửi Quý khách,\n\n"
            "Agentify xin gửi báo giá cho lô {commodity} tuyến {pol} - {pod}, "
            "hãng tàu {carrier}.\n\n"
            "CHI TIẾT PHÍ\n\n"
            "Cước biển:\n"
            "  - Ocean Freight 40HC: 2480.00 USD (x2)\n\n"
            "Phụ phí:\n"
            "  - Bunker Adjustment Factor: 130.00 USD\n"
            "  - Low Sulphur Surcharge: 88.00 USD\n\n"
            "Phí local:\n"
            "  - Terminal Handling Charge: 340.00 USD (x2)\n"
            "  - Documentation fee: 35.00 USD\n"
            "  - Telex release fee: 30.00 USD\n\n"
            "TỔNG CỘNG: 3103.00 USD\n\n"
            "Thời gian miễn phí lưu container tại {pod}: 10 ngày.\n"
            "Báo giá có hiệu lực 21 ngày kể từ hôm nay.\n\n"
            "Trân trọng,\nAgentify Forwarding — Bộ phận Kinh doanh"
        ),
        day_offset=1,
        sent_time="17:20",
    ),
)

SCENARIOS: dict[str, tuple[ThreadStep, ...]] = {
    "export_fcl": SCENARIO_EXPORT_FCL,
    "import_customs": SCENARIO_IMPORT_CUSTOMS,
    "quote_to_booking": SCENARIO_QUOTE_TO_BOOKING,
    "delivery_pod": SCENARIO_DELIVERY_POD,
    "finance_debit": SCENARIO_FINANCE_DEBIT,
    "rfq_round_trip": SCENARIO_RFQ_ROUND_TRIP,
    "rfq_round_trip_2": SCENARIO_RFQ_ROUND_TRIP_2,
}

THREAD_PLANS: tuple[ThreadPlan, ...] = (
    ThreadPlan("export_yokohama", "export_fcl", date(2026, 6, 13)),
    ThreadPlan("export_busan", "export_fcl", date(2026, 6, 14)),
    ThreadPlan("import_shanghai", "import_customs", date(2026, 6, 3)),
    ThreadPlan("import_busan", "import_customs", date(2026, 6, 5)),
    ThreadPlan("quote_singapore", "quote_to_booking", date(2026, 6, 15)),
    ThreadPlan("quote_chennai", "quote_to_booking", date(2026, 6, 17)),
    ThreadPlan("delivery_binhduong", "delivery_pod", date(2026, 6, 5)),
    ThreadPlan("delivery_bacninh", "delivery_pod", date(2026, 6, 6)),
    ThreadPlan("finance_rotterdam", "finance_debit", date(2026, 6, 1)),
    ThreadPlan("finance_osaka", "finance_debit", date(2026, 5, 29)),
    ThreadPlan("roundtrip_rfq", "rfq_round_trip", date(2026, 7, 2)),
    ThreadPlan("roundtrip_rfq_hpn", "rfq_round_trip_2", date(2026, 8, 3)),
)


def build_thread_records(start_seq: int) -> list[EmailRecord]:
    """Sinh các thư theo kịch bản, đánh số nối tiếp phần viết tay."""
    records: list[EmailRecord] = []
    seq = start_seq
    for plan in THREAD_PLANS:
        profile = THREAD_PROFILES[plan.profile_key]
        steps = SCENARIOS[plan.scenario]
        records.extend(_thread_records(seq, profile, steps, plan.start_date))
        seq += len(steps)
    return records


def build_records() -> list[EmailRecord]:
    p = PROFILES
    records = [
        _record(
            1,
            p["completed"],
            "completed-booking-confirmation",
            "Booking confirmation OOLU7215245 / OOL-BKG-260601",
            "Dear Minh,\n\nPlease find attached booking confirmation for container OOLU7215245. ETD Hai Phong is 2026-06-01 on ONE RESILIENCE 018W.\n\nRegards,\nCustomer Service",
            "cs.export@one-demo.com",
            "2026-05-27 09:10 +07",
            "booking_confirmation_oolu7215245.pdf",
            _attachment_lines(p["completed"], "Booking Confirmation", ["Status: Booking confirmed"]),
        ),
        _record(
            2,
            p["completed"],
            "completed-si-submission",
            "SI submitted for OOLU7215245 / HBL-SGNHAM-7215",
            "Dear Minh,\n\nShipping instruction for OOLU7215245 has been submitted. Please check consignee and notify party details in the attached SI sheet.\n\nThanks,\nDocs Team",
            "docs@viethomeexport.vn",
            "2026-05-28 14:05 +07",
            "shipping_instruction_oolu7215245.pdf",
            _attachment_lines(p["completed"], "Shipping Instruction", ["Notify Party: Same as consignee", "Freight Term: FOB Hai Phong"]),
        ),
        _record(
            3,
            p["completed"],
            "completed-onboard-update",
            "On-board confirmation OOLU7215245 / ONE RESILIENCE 018W",
            "Dear Minh,\n\nContainer OOLU7215245 is on board ONE RESILIENCE 018W. Kindly update customer that shipment has departed as planned.\n\nBest regards,\nCarrier Team",
            "export.notice@one-demo.com",
            "2026-06-01 19:25 +07",
            "onboard_notice_oolu7215245.pdf",
            _attachment_lines(p["completed"], "On Board Notice", ["Status: Vessel departed", "Actual ETD: 2026-06-01 18:40"]),
        ),
        _record(
            4,
            p["completed"],
            "completed-arrival-notice",
            "Arrival notice OOLU7215245 / Hamburg terminal",
            "Dear Minh,\n\nAttached arrival notice for OOLU7215245. Vessel arrived Hamburg and container is available for discharge planning.\n\nRegards,\nDestination Agent",
            "arrival@de-agent-demo.com",
            "2026-06-24 16:40 +07",
            "arrival_notice_oolu7215245.pdf",
            _attachment_lines(p["completed"], "Arrival Notice", ["Status: Arrived at POD", "Terminal: CTA Hamburg", "Free time until: 2026-06-28"]),
        ),
        _record(
            5,
            p["completed"],
            "completed-delivery-order",
            "Delivery order released for OOLU7215245",
            "Dear Minh,\n\nDelivery order has been released for OOLU7215245 after local charge settlement. Please coordinate trucking for final delivery.\n\nThanks,\nDestination Docs",
            "do.release@de-agent-demo.com",
            "2026-06-25 10:00 +07",
            "delivery_order_oolu7215245.pdf",
            _attachment_lines(p["completed"], "Delivery Order", ["Status: Delivery order released", "Pickup location: CTA Hamburg Yard"]),
        ),
        _record(
            6,
            p["completed"],
            "completed-final-delivery",
            "Final delivery completed OOLU7215245 / proof attached",
            "Dear Minh,\n\nConsignee confirmed final delivery of OOLU7215245 on 2026-06-27. This shipment can be marked completed.\n\nRegards,\nAccount Service",
            "account@de-agent-demo.com",
            "2026-06-27 17:45 +07",
            "proof_of_delivery_oolu7215245.pdf",
            _attachment_lines(p["completed"], "Proof of Delivery", ["Status: Delivered", "Delivered on: 2026-06-27", "Signed by: Markus Klein"]),
        ),
        _record(
            7,
            p["transit"],
            "transit-booking-confirmation",
            "Booking confirmation TGHU4982331 / MSK-BKG-260603",
            "Dear Minh,\n\nBooking for container TGHU4982331 is confirmed under MSK-BKG-260603. Please find booking note attached.\n\nRegards,\nMaersk Booking",
            "booking@maersk-demo.com",
            "2026-05-29 11:30 +07",
            "booking_confirmation_tghu4982331.pdf",
            _attachment_lines(p["transit"], "Booking Confirmation", ["Status: Booking confirmed"]),
        ),
        _record(
            8,
            p["transit"],
            "transit-commercial-invoice",
            "Commercial invoice for TGHU4982331 / PO-US-51022",
            "Dear Minh,\n\nAttached commercial invoice for shipment TGHU4982331. Please keep for customs file and customer reference.\n\nBest,\nShipper Finance",
            "billing@thanhcongplastics.vn",
            "2026-05-31 08:45 +07",
            "commercial_invoice_tghu4982331.pdf",
            _attachment_lines(p["transit"], "Commercial Invoice", ["Invoice No: INV-TCP-260531", "Invoice Value: USD 48,720.00"]),
        ),
        _record(
            9,
            p["transit"],
            "transit-packing-list",
            "Packing list TGHU4982331 / 1,020 cartons",
            "Dear Minh,\n\nPacking list for TGHU4982331 is attached. Gross weight and carton count were reconfirmed this morning.\n\nRegards,\nWarehouse",
            "warehouse@thanhcongplastics.vn",
            "2026-06-01 13:20 +07",
            "packing_list_tghu4982331.pdf",
            _attachment_lines(p["transit"], "Packing List", ["Gross Weight: 12,860 KGS", "Net Weight: 11,940 KGS"]),
        ),
        _record(
            10,
            p["transit"],
            "transit-onboard-confirmation",
            "On-board confirmation TGHU4982331 / MAERSK HANOI 126E",
            "Dear Minh,\n\nContainer TGHU4982331 loaded on vessel MAERSK HANOI 126E. Estimated arrival Long Beach remains 2026-06-29.\n\nBest regards,\nCarrier Export Desk",
            "export.update@maersk-demo.com",
            "2026-06-03 21:00 +07",
            "onboard_notice_tghu4982331.pdf",
            _attachment_lines(p["transit"], "On Board Notice", ["Status: In transit", "Actual ETD: 2026-06-03 20:10"]),
        ),
        _record(
            11,
            p["transit"],
            "transit-route-update",
            "Transit update TGHU4982331 / ETA Long Beach revised",
            "Dear Minh,\n\nPlease update customer that TGHU4982331 remains in transit. ETA Long Beach is revised to 2026-06-30 due to port congestion.\n\nRegards,\nCarrier Tracking",
            "tracking@maersk-demo.com",
            "2026-06-16 09:05 +07",
            "transit_update_tghu4982331.pdf",
            _attachment_lines(p["transit"], "Transit Update", ["Status: In transit", "Current milestone: Passed Yokohama", "Revised ETA: 2026-06-30"]),
        ),
        _record(
            12,
            p["transit"],
            "transit-prearrival",
            "Pre-arrival notice TGHU4982331 / Long Beach",
            "Dear Minh,\n\nPre-arrival notice for TGHU4982331 is attached. Shipment is still on water and local team is preparing import file.\n\nThanks,\nUS Agent",
            "prealert@us-agent-demo.com",
            "2026-06-22 07:55 +07",
            "pre_arrival_notice_tghu4982331.pdf",
            _attachment_lines(p["transit"], "Pre Arrival Notice", ["Status: In transit", "Manifest filed: Yes", "Customs hold: No"]),
        ),
        _record(
            13,
            p["waiting_export"],
            "waiting-export-booking-confirmation",
            "Booking note SEKU6678912 / YML-BKG-260610",
            "Dear Minh,\n\nBooking note for SEKU6678912 is attached. Cargo is planned to load on YM WISDOM 072S.\n\nRegards,\nCarrier Booking",
            "booking@yangming-demo.com",
            "2026-06-08 10:15 +07",
            "booking_note_seku6678912.pdf",
            _attachment_lines(p["waiting_export"], "Booking Note", ["Status: Waiting export", "CY closing: 2026-06-12 17:00"]),
        ),
        _record(
            14,
            p["waiting_export"],
            "waiting-export-vgm-request",
            "Need VGM confirmation for SEKU6678912 before gate-in",
            "Dear Minh,\n\nPlease send VGM for SEKU6678912 before terminal cut-off. Attached checklist includes gate-in and SI deadlines.\n\nThanks,\nExport Ops",
            "ops@baotinpack.vn",
            "2026-06-09 15:50 +07",
            "vgm_checklist_seku6678912.pdf",
            _attachment_lines(p["waiting_export"], "VGM Checklist", ["Status: Waiting export", "VGM pending: Yes", "SI cut-off: 2026-06-11 12:00"]),
        ),
        _record(
            15,
            p["waiting_export"],
            "waiting-export-si-draft",
            "Draft SI for SEKU6678912 / please review consignee",
            "Dear Minh,\n\nAttached draft SI for SEKU6678912. Please verify consignee address and HS code before we transmit to carrier.\n\nBest,\nDocumentation",
            "docs@baotinpack.vn",
            "2026-06-10 08:20 +07",
            "draft_si_seku6678912.pdf",
            _attachment_lines(p["waiting_export"], "Draft Shipping Instruction", ["Status: Waiting export", "HS Code: 48195000", "Remark: Pending final carton marks"]),
        ),
        _record(
            16,
            p["waiting_export"],
            "waiting-export-terminal-cutoff",
            "Terminal cut-off reminder SEKU6678912 / Cat Lai",
            "Dear Minh,\n\nThis is a reminder that container SEKU6678912 has not yet gated in. Please coordinate trucking before CY closing.\n\nRegards,\nForwarding Team",
            "truck@agentify-forwarding.vn",
            "2026-06-11 17:30 +07",
            "terminal_cutoff_reminder_seku6678912.pdf",
            _attachment_lines(p["waiting_export"], "Terminal Cut-off Reminder", ["Status: Waiting export", "Gate-in status: Pending", "CY closing: 2026-06-12 17:00"]),
        ),
        _record(
            17,
            p["waiting_export"],
            "waiting-export-stuffing-report",
            "Stuffing report ready for SEKU6678912",
            "Dear Minh,\n\nStuffing for SEKU6678912 completed at warehouse, but container is still waiting for handover to terminal. Attached report for record.\n\nThanks,\nWarehouse Ops",
            "warehouse@baotinpack.vn",
            "2026-06-12 09:40 +07",
            "stuffing_report_seku6678912.pdf",
            _attachment_lines(p["waiting_export"], "Stuffing Report", ["Status: Waiting export", "Stuffing completed: 2026-06-12 08:30", "Seal No: BTX998712"]),
        ),
        _record(
            18,
            p["waiting_export"],
            "waiting-export-load-plan",
            "Load plan pending vessel connection for SEKU6678912",
            "Dear Minh,\n\nAttached latest load plan for SEKU6678912. Shipment remains under waiting export until terminal confirms loading list.\n\nRegards,\nCarrier Ops",
            "ops.update@yangming-demo.com",
            "2026-06-12 18:05 +07",
            "load_plan_seku6678912.pdf",
            _attachment_lines(p["waiting_export"], "Load Plan", ["Status: Waiting export", "Load list status: Pending carrier confirmation"]),
        ),
        _record(
            19,
            p["waiting_customs"],
            "waiting-customs-booking-confirmation",
            "Booking confirmation FSCU3301847 / CMA-BKG-260528",
            "Dear Minh,\n\nBooking confirmation for reefer container FSCU3301847 is attached. Shipment departed earlier and is now at import clearance stage.\n\nRegards,\nCarrier Booking",
            "booking@cmacgm-demo.com",
            "2026-05-20 16:00 +07",
            "booking_confirmation_fscu3301847.pdf",
            _attachment_lines(p["waiting_customs"], "Booking Confirmation", ["Status: Historical booking file"]),
        ),
        _record(
            20,
            p["waiting_customs"],
            "waiting-customs-health-cert",
            "Health certificate packet FSCU3301847 / customs review",
            "Dear Minh,\n\nAttached health certificate packet for FSCU3301847. Destination customs asked for supporting file before release.\n\nThanks,\nDocs Export",
            "docs@bluedeltaseafood.vn",
            "2026-06-08 11:05 +07",
            "health_certificate_fscu3301847.pdf",
            _attachment_lines(p["waiting_customs"], "Health Certificate Packet", ["Status: Waiting customs", "Certificate No: HC-260608-18"]),
        ),
        _record(
            21,
            p["waiting_customs"],
            "waiting-customs-arrival-notice",
            "Arrival notice FSCU3301847 / Jakarta port",
            "Dear Minh,\n\nContainer FSCU3301847 has arrived Jakarta. Customs inspection is scheduled and cargo is not yet released.\n\nRegards,\nDestination Agent",
            "arrival@id-agent-demo.com",
            "2026-06-09 14:10 +07",
            "arrival_notice_fscu3301847.pdf",
            _attachment_lines(p["waiting_customs"], "Arrival Notice", ["Status: Waiting customs", "Inspection lane: Red lane"]),
        ),
        _record(
            22,
            p["waiting_customs"],
            "waiting-customs-inspection-request",
            "Customs inspection request FSCU3301847 / reefer hold",
            "Dear Minh,\n\nPlease note FSCU3301847 is under customs inspection hold. Attached notice lists documents required by Jakarta customs.\n\nBest,\nImport Clearance Team",
            "clearance@id-agent-demo.com",
            "2026-06-10 08:35 +07",
            "customs_inspection_notice_fscu3301847.pdf",
            _attachment_lines(p["waiting_customs"], "Customs Inspection Notice", ["Status: Waiting customs", "Hold reason: Product classification review", "Required: invoice, packing list, health cert"]),
        ),
        _record(
            23,
            p["waiting_customs"],
            "waiting-customs-duty-estimate",
            "Duty estimate FSCU3301847 / pending customs release",
            "Dear Minh,\n\nDuty estimate for FSCU3301847 is attached. Shipment remains pending customs release until importer settles tax and inspection result.\n\nRegards,\nBroker",
            "broker@jakarta-demo.co.id",
            "2026-06-10 16:25 +07",
            "duty_estimate_fscu3301847.pdf",
            _attachment_lines(p["waiting_customs"], "Duty Estimate", ["Status: Waiting customs", "Estimated duty and tax: USD 6,420.00"]),
        ),
        _record(
            24,
            p["waiting_customs"],
            "waiting-customs-followup",
            "Follow-up FSCU3301847 / customs still pending",
            "Dear Minh,\n\nLatest follow-up attached. FSCU3301847 has not been released by customs as of this afternoon.\n\nThanks,\nDestination Ops",
            "ops@id-agent-demo.com",
            "2026-06-11 15:15 +07",
            "customs_followup_fscu3301847.pdf",
            _attachment_lines(p["waiting_customs"], "Customs Follow-up", ["Status: Waiting customs", "Release status: Pending customs approval"]),
        ),
        _record(
            25,
            p["waiting_docs"],
            "waiting-docs-booking-confirmation",
            "Booking confirmation CMAU1182456 / EMC-BKG-260607",
            "Dear Minh,\n\nBooking confirmation for CMAU1182456 is attached. Please proceed with shipper docs collection.\n\nRegards,\nCarrier Booking",
            "booking@evergreen-demo.com",
            "2026-06-04 09:25 +07",
            "booking_confirmation_cmau1182456.pdf",
            _attachment_lines(p["waiting_docs"], "Booking Confirmation", ["Status: Waiting documents"]),
        ),
        _record(
            26,
            p["waiting_docs"],
            "waiting-docs-si-request",
            "Urgent: submit SI for CMAU1182456 before manifest cut-off",
            "Dear Minh,\n\nAttached SI request form for CMAU1182456. We still miss final consignee phone and package marks.\n\nThanks,\nCarrier Documentation",
            "si.request@evergreen-demo.com",
            "2026-06-05 13:10 +07",
            "si_request_cmau1182456.pdf",
            _attachment_lines(p["waiting_docs"], "SI Request", ["Status: Waiting documents", "Missing item: final package marks", "Missing item: consignee phone"]),
        ),
        _record(
            27,
            p["waiting_docs"],
            "waiting-docs-packing-list-missing",
            "Missing packing list for CMAU1182456 / please provide today",
            "Dear Minh,\n\nPlease find attached shortage note. Packing list for CMAU1182456 has not been received, so draft HBL cannot be issued yet.\n\nBest,\nDocumentation",
            "docs@agentify-forwarding.vn",
            "2026-06-06 10:55 +07",
            "missing_docs_notice_cmau1182456.pdf",
            _attachment_lines(p["waiting_docs"], "Missing Documents Notice", ["Status: Waiting documents", "Missing document: Packing list", "Missing document: Commercial invoice"]),
        ),
        _record(
            28,
            p["waiting_docs"],
            "waiting-docs-draft-hbl",
            "Draft HBL CMAU1182456 / hold for invoice details",
            "Dear Minh,\n\nAttached draft HBL for CMAU1182456. HBL can only be finalized after invoice amount is confirmed by shipper.\n\nRegards,\nDocs Team",
            "draftbl@agentify-forwarding.vn",
            "2026-06-07 18:20 +07",
            "draft_hbl_cmau1182456.pdf",
            _attachment_lines(p["waiting_docs"], "Draft HBL", ["Status: Waiting documents", "Draft only: Yes", "Pending field: Invoice amount"]),
        ),
        _record(
            29,
            p["waiting_docs"],
            "waiting-docs-arrival-prealert",
            "Pre-alert CMAU1182456 / original docs still pending",
            "Dear Minh,\n\nBangkok agent sent pre-alert for CMAU1182456, but original shipping documents are still incomplete. Please follow up urgently.\n\nThanks,\nImport Desk",
            "prealert@th-agent-demo.co.th",
            "2026-06-09 08:35 +07",
            "prealert_cmau1182456.pdf",
            _attachment_lines(p["waiting_docs"], "Pre Alert", ["Status: Waiting documents", "Original docs received: No", "Telex release: Pending"]),
        ),
        _record(
            30,
            p["waiting_docs"],
            "waiting-docs-followup",
            "Follow-up on missing docs CMAU1182456 / shipment on hold",
            "Dear Minh,\n\nLatest follow-up attached. Shipment CMAU1182456 stays in waiting documents because invoice and packing list are still missing.\n\nRegards,\nCustomer Service",
            "cs@agentify-forwarding.vn",
            "2026-06-10 17:05 +07",
            "docs_followup_cmau1182456.pdf",
            _attachment_lines(p["waiting_docs"], "Documents Follow-up", ["Status: Waiting documents", "Shipment hold reason: Invoice and packing list pending"]),
        ),
        _record(
            31,
            p["missing_data"],
            "missing-data-booking-note",
            "Booking note OOL-BKG-260609 / Port Klang shipment",
            "Dear Minh,\n\nAttached booking note for Port Klang shipment under booking OOL-BKG-260609. Warehouse asked us to proceed, but final shipment identifiers are still incomplete.\n\nRegards,\nCarrier Booking",
            "booking@oocl-demo.com",
            "2026-06-06 09:40 +07",
            "booking_note_temu5522441.pdf",
            _attachment_lines(p["missing_data"], "Booking Note", ["Status: Missing data", "Internal remark: final HBL not assigned yet"]),
        ),
        _record(
            32,
            p["missing_data"],
            "missing-data-commercial-invoice",
            "Invoice packet for booking OOL-BKG-260609 / PO-MY-45091",
            "Dear Minh,\n\nCommercial invoice packet attached for booking OOL-BKG-260609. The shipper email did not mention container number in the message.\n\nBest,\nFinance",
            "finance@phuminhlighting.vn",
            "2026-06-07 14:25 +07",
            "commercial_invoice_booking_260609.pdf",
            _attachment_lines(
                p["missing_data"],
                "Commercial Invoice",
                ["Status: Missing data", "Invoice No: INV-PM-260607", "Container No: NOT PROVIDED IN SOURCE"],
                omit_container=True,
                omit_hbl=True,
            ),
        ),
        _record(
            33,
            p["missing_data"],
            "missing-data-packing-list",
            "Packing list for PO-MY-45091 / booking OOL-BKG-260609",
            "Dear Minh,\n\nAttached packing list for the Malaysia shipment. Booking number is available, but HBL number and final marks are pending.\n\nRegards,\nWarehouse",
            "warehouse@phuminhlighting.vn",
            "2026-06-08 08:05 +07",
            "packing_list_booking_260609.pdf",
            _attachment_lines(
                p["missing_data"],
                "Packing List",
                ["Status: Missing data", "Marks: TBD by customer"],
                omit_container=True,
                omit_hbl=True,
            ),
        ),
        _record(
            34,
            p["missing_data"],
            "missing-data-draft-bl-request",
            "Need draft BL info for Port Klang shipment / no HBL yet",
            "Dear Minh,\n\nAttached draft BL request form. We still do not have final HBL number and consignee tax code for this shipment.\n\nThanks,\nDocs Team",
            "docs@agentify-forwarding.vn",
            "2026-06-09 11:15 +07",
            "draft_bl_request_booking_260609.pdf",
            _attachment_lines(
                p["missing_data"],
                "Draft BL Request",
                ["Status: Missing data", "Missing field: HBL No", "Missing field: Consignee tax code"],
                omit_hbl=True,
            ),
        ),
        _record(
            35,
            p["missing_data"],
            "missing-data-vessel-update",
            "Vessel update for TEMU5522441 / source mismatch on identifiers",
            "Dear Minh,\n\nCarrier update attached for TEMU5522441. Please note the forwarded customer email only quoted PO-MY-45091 and not the container number.\n\nRegards,\nCarrier Tracking",
            "tracking@oocl-demo.com",
            "2026-06-10 07:50 +07",
            "vessel_update_temu5522441.pdf",
            _attachment_lines(p["missing_data"], "Vessel Update", ["Status: Missing data", "Current milestone: On feeder connection", "Identifier mismatch: body vs attachment"]),
        ),
        _record(
            36,
            p["missing_data"],
            "missing-data-shortage-summary",
            "Missing data summary for booking OOL-BKG-260609",
            "Dear Minh,\n\nAttached shortage summary for the Port Klang shipment. Current file is still incomplete and should remain under missing data until HBL and invoice references are finalized.\n\nBest regards,\nOps Control",
            "ops.control@agentify.vn",
            "2026-06-10 18:40 +07",
            "missing_data_summary_booking_260609.pdf",
            _attachment_lines(
                p["missing_data"],
                "Missing Data Summary",
                ["Status: Missing data", "Outstanding: HBL No", "Outstanding: invoice reference in customer thread"],
                omit_hbl=True,
            ),
        ),
    ]
    records.extend(build_thread_records(len(records) + 1))
    return records


def write_corpus(records: list[EmailRecord], output_dir: Path = OUTPUT_DIR) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for child in output_dir.iterdir():
        if child.name.startswith("email_") and child.is_dir():
            shutil.rmtree(child)

    inbound = sum(1 for record in records if record.direction == INBOUND)
    outbound = len(records) - inbound
    without_attachment = sum(1 for record in records if not record.pdf_name)

    readme = [
        "# Demo Email Corpus",
        "",
        "Generated by `python3 backend/scripts/generate_demo_email_corpus.py`.",
        "",
        f"Total: {len(records)} emails — {inbound} mail đến, {outbound} mail đi, "
        f"{without_attachment} thư không đính kèm.",
        "",
        "Status coverage:",
        "- Đã hoàn tất: OOLU7215245",
        "- Đang vận chuyển: TGHU4982331",
        "- Chờ xuất cảng: SEKU6678912",
        "- Chờ thông quan: FSCU3301847",
        "- Chờ chứng từ: CMAU1182456",
        "- Thiếu dữ liệu: TEMU5522441",
        "",
        "Thread scenarios (mỗi hồ sơ 5 thư, xen kẽ mail đến và mail đi):",
        "- export_fcl: MSKU4120885, HLXU8305142",
        "- import_customs: ZIMU2776311, KMTU5901421",
        "- quote_to_booking: WHLU6612093, SUDU3347800",
        "- delivery_pod: PONU7150630, TLLU2089457",
        "- finance_debit: APZU8741204, BEAU5033684",
        "",
        "Vòng hỏi giá khép kín (rfq_round_trip) — 4 chặng chạy trọn trong MỘT hộp thư,",
        f"tiêu đề mang nhãn `{DEMO_TAG}[CHẶNG]` để biết ai gửi cho ai:",
        "  1. KHACH>AGENTIFY   — khách hỏi giá",
        "  2. AGENTIFY>HANGTAU — Agentify hỏi cước hãng tàu",
        "  3. HANGTAU>AGENTIFY — hãng tàu báo giá (bảng phí nằm trong thân thư)",
        "  4. AGENTIFY>KHACH   — Agentify báo giá khách",
        "",
        "Gửi riêng vòng này:",
        "  python -m scripts.send_demo_emails --only roundtrip",
        "Rồi đặt `GMAIL_QUERY=subject:AGENTIFY-DEMO newer_than:7d` để sync đúng bộ đó.",
        "",
        f"Test mailbox: `{TARGET_TO}`. Mail đến gửi VÀO hộp thư này; mail đi gửi TỪ",
        "hộp thư này tới đối tác. Hướng thư nằm ở header `X-Agentify-Direction`",
        "vì `send_demo_emails.py` ghi đè From/To để mọi thư đều rơi vào cùng hộp thư test.",
        "",
        "Each `email_*` folder contains:",
        "- `title.txt`",
        "- `body.txt`",
        "- `meta.txt`",
        "- `attachments/*.pdf` (không có nếu thư là reply thuần text)",
        "",
        "All PDFs are plain text PDFs intended for text extraction tests.",
        "",
        "Lưu ý khi sync Gmail: `GMAIL_QUERY` mặc định là `has:attachment newer_than:7d`,",
        "nên các thư không đính kèm sẽ bị bỏ qua. Bỏ `has:attachment` nếu muốn test",
        "đường trích xuất từ body.",
        "",
    ]
    (output_dir / "README.md").write_text("\n".join(readme), encoding="utf-8")

    # Message-ID sinh một lần cho cả lượt chạy rồi tra ngược lại khi nối
    # In-Reply-To. Vẫn để make_msgid random để chạy lại corpus không đụng
    # Message-ID cũ — nếu trùng, Gmail sẽ gộp/loại thư ở lần gửi thứ hai.
    message_ids = {
        record.slug: make_msgid(idstring=record.slug, domain="agentify.local")
        for record in records
    }

    for record in records:
        email_dir = output_dir / f"email_{record.seq:02d}_{record.slug}"
        email_dir.mkdir(parents=True, exist_ok=True)

        (email_dir / "title.txt").write_text(record.title + "\n", encoding="utf-8")
        (email_dir / "body.txt").write_text(record.body.strip() + "\n", encoding="utf-8")

        profile = PROFILES[record.container_key]
        meta_lines = [
            f"Direction: {record.direction}",
            f"To: {record.to_email}",
            f"From: {record.from_email}",
            f"Sent At: {record.sent_at}",
            f"Container No: {profile.container_no}",
            f"Booking No: {profile.booking_no}",
            f"Status Bucket: {profile.status_bucket}",
            f"Thread Key: {profile.key}",
            f"Attachment: {record.pdf_name or '(none)'}",
        ]
        if record.reply_to_slug:
            meta_lines.append(f"In Reply To: {record.reply_to_slug}")
        (email_dir / "meta.txt").write_text("\n".join(meta_lines) + "\n", encoding="utf-8")

        pdf_bytes: bytes | None = None
        if record.pdf_name:
            attachments_dir = email_dir / "attachments"
            attachments_dir.mkdir(parents=True, exist_ok=True)
            pdf_bytes = _build_text_pdf_bytes(list(record.pdf_lines))
            (attachments_dir / record.pdf_name).write_bytes(pdf_bytes)

        (email_dir / "email.eml").write_bytes(
            _build_eml_bytes(
                record,
                pdf_bytes,
                message_id=message_ids[record.slug],
                in_reply_to=message_ids.get(record.reply_to_slug or ""),
            )
        )


def main() -> None:
    records = build_records()
    write_corpus(records)
    print(f"Generated {len(records)} demo emails in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
