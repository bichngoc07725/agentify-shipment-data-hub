from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage
from email.utils import format_datetime, make_msgid
from pathlib import Path
import re
import shutil


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "demo_email"
TARGET_TO = "vuphungminh250@gmail.com"


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


def _build_eml_bytes(record: EmailRecord, pdf_bytes: bytes) -> bytes:
    sent_at = record.sent_at
    if re.search(r" [+-]\d{2}$", sent_at):
        sent_at = f"{sent_at}00"

    message = EmailMessage()
    message["Subject"] = record.title
    message["To"] = TARGET_TO
    message["From"] = record.from_email
    message["Date"] = format_datetime(datetime.strptime(sent_at, "%Y-%m-%d %H:%M %z"))
    message["Message-ID"] = make_msgid(idstring=record.slug, domain="agentify.local")
    message.set_content(record.body.strip())
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
) -> tuple[str, ...]:
    lines = [f"Document Type: {doc_type}"]
    if not omit_container:
        lines.append(f"Container No: {profile.container_no}")
    lines.extend(
        [
            f"Booking No: {profile.booking_no}",
            f"PO No: {profile.po_no}",
            f"POL: {profile.pol}",
            f"POD: {profile.pod}",
            f"Vessel/Voyage: {profile.vessel_voyage}",
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
    if profile.mbl_no:
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
    )


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
    return records


def write_corpus(records: list[EmailRecord], output_dir: Path = OUTPUT_DIR) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for child in output_dir.iterdir():
        if child.name.startswith("email_") and child.is_dir():
            shutil.rmtree(child)

    readme = [
        "# Demo Email Corpus",
        "",
        "Generated by `python3 backend/scripts/generate_demo_email_corpus.py`.",
        "",
        "Status coverage:",
        "- Đã hoàn tất: OOLU7215245",
        "- Đang vận chuyển: TGHU4982331",
        "- Chờ xuất cảng: SEKU6678912",
        "- Chờ thông quan: FSCU3301847",
        "- Chờ chứng từ: CMAU1182456",
        "- Thiếu dữ liệu: TEMU5522441",
        "",
        f"Target recipient for all sample emails: `{TARGET_TO}`",
        "",
        "Each `email_*` folder contains:",
        "- `title.txt`",
        "- `body.txt`",
        "- `meta.txt`",
        "- `attachments/*.pdf`",
        "",
        "All PDFs are plain text PDFs intended for text extraction tests.",
        "",
    ]
    (output_dir / "README.md").write_text("\n".join(readme), encoding="utf-8")

    for record in records:
        email_dir = output_dir / f"email_{record.seq:02d}_{record.slug}"
        attachments_dir = email_dir / "attachments"
        attachments_dir.mkdir(parents=True, exist_ok=True)

        (email_dir / "title.txt").write_text(record.title + "\n", encoding="utf-8")
        (email_dir / "body.txt").write_text(record.body.strip() + "\n", encoding="utf-8")

        profile = PROFILES[record.container_key]
        meta_lines = [
            f"To: {TARGET_TO}",
            f"From: {record.from_email}",
            f"Sent At: {record.sent_at}",
            f"Container No: {profile.container_no}",
            f"Booking No: {profile.booking_no}",
            f"Status Bucket: {profile.status_bucket}",
            f"Thread Key: {profile.key}",
            f"Attachment: {record.pdf_name}",
        ]
        (email_dir / "meta.txt").write_text("\n".join(meta_lines) + "\n", encoding="utf-8")
        pdf_bytes = _build_text_pdf_bytes(list(record.pdf_lines))
        (attachments_dir / record.pdf_name).write_bytes(pdf_bytes)
        (email_dir / "email.eml").write_bytes(_build_eml_bytes(record, pdf_bytes))


def main() -> None:
    records = build_records()
    write_corpus(records)
    print(f"Generated {len(records)} demo emails in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
