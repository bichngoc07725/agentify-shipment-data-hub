from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


def _coerce_to_str(value: object) -> object:
    # Azure's strict schema always returns quantity as a string ("2 Bo"), but
    # Gemini's non-strict JSON mode sometimes reads a numeric-looking field as
    # a bare number (2.0) instead, dropping the unit. Accept either shape
    # rather than failing validation over a provider-specific quirk.
    if isinstance(value, (int, float)):
        return str(value)
    return value


def _coerce_name_like_to_str(value: object) -> object:
    # Gemini's non-strict JSON mode has, in practice, returned a plain string
    # field (e.g. carrier) as a nested object instead — `{"name": "Maersk"}` —
    # as if it confused it with a Party. Pull `name` out if present rather
    # than failing validation.
    if isinstance(value, dict):
        return value.get("name")
    return value

DocType = Literal[
    "arrival_notice",
    "booking_confirmation",
    "bill_of_lading",
    "invoice",
    "packing_list",
    "debit_note",
    "delivery_order",
    "certificate_of_origin",
    "customs_declaration",
    "other",
]


class Source(BaseModel):
    channel: str = "email"
    message_id: str
    sender: str
    subject: str
    received_at: str
    attachment_name: str | None = None


class Identifiers(BaseModel):
    container_no: list[str] = Field(default_factory=list)
    seal_no: list[str] = Field(default_factory=list)
    booking_no: str | None = None
    bl_no: str | None = None
    hbl_no: str | None = None
    sb_no: str | None = None
    awb_no: str | None = None
    po_no: str | None = None
    do_no: str | None = None
    job_no: str | None = None
    invoice_no: str | None = None
    hs_code: str | None = None
    declaration_no: str | None = None


class Party(BaseModel):
    name: str | None = None
    address: str | None = None
    contact_person: str | None = None
    email: str | None = None
    phone: str | None = None
    tax_code: str | None = None


class Route(BaseModel):
    pol: str | None = None
    pod: str | None = None
    place_of_receipt: str | None = None
    final_destination: str | None = None
    cfs_terminal: str | None = None
    vessel: str | None = None
    voyage: str | None = None
    etd: str | None = None
    eta: str | None = None
    ata: str | None = None


class Cargo(BaseModel):
    description: str | None = None
    packages: str | None = None
    gross_weight_kg: float | None = None
    tare_weight_kg: float | None = None
    volume_cbm: float | None = None
    marks_numbers: str | None = None


class Charge(BaseModel):
    description: str | None = None
    quantity: str | None = None
    currency: str | None = None
    amount: float | None = None
    vat_rate: str | None = None

    _coerce_quantity = field_validator("quantity", mode="before")(_coerce_to_str)


class CargoLine(BaseModel):
    """One row of a multi-item goods table (packing list, customs
    declaration's HS-code table, invoice line items) — as opposed to `Cargo`,
    which is a single aggregate summary for a document with only one item."""

    description: str | None = None
    hs_code: str | None = None
    origin: str | None = None
    quantity: str | None = None
    unit_price: float | None = None
    amount: float | None = None
    currency: str | None = None

    _coerce_quantity = field_validator("quantity", mode="before")(_coerce_to_str)


class CustomsDeclaration(BaseModel):
    declaration_type_code: str | None = None
    direction: str | None = None
    customs_office: str | None = None
    clearance_lane: str | None = None
    registration_date: str | None = None
    clearance_date: str | None = None
    total_tax_amount: float | None = None
    tax_currency: str | None = None


class ExtractedRecord(BaseModel):
    source: Source
    doc_type: DocType
    doc_type_confidence: float
    doc_date: str | None = None
    reference_no: str | None = None
    number_of_originals: str | None = None
    payment_term: str | None = None
    identifiers: Identifiers
    carrier: str | None = None
    issuer: Party | None = None
    shipper: Party | None = None
    consignee: Party | None = None
    notify_party: Party | None = None
    customer_name: str | None = None
    route: Route
    cargo: Cargo | None = None
    cargo_lines: list[CargoLine] = Field(default_factory=list)
    charges: list[Charge] = Field(default_factory=list)
    customs: CustomsDeclaration | None = None
    free_time_days: int | None = None
    extraction_status: Literal["ok", "partial", "failed"] = "ok"
    extraction_method: Literal["deterministic", "llm", "hybrid"] = "deterministic"
    extraction_error: str | None = None

    _coerce_carrier = field_validator("carrier", mode="before")(_coerce_name_like_to_str)


class GmailAttachmentPayload(BaseModel):
    gmail_attachment_id: str | None = None
    filename: str
    mime_type: str
    size_bytes: int | None = None
    attachment_bytes: bytes


class GmailEmailPayload(BaseModel):
    gmail_message_id: str
    gmail_thread_id: str | None = None
    subject: str
    from_email: str
    to_emails: list[str] = Field(default_factory=list)
    cc_emails: list[str] = Field(default_factory=list)
    sent_at: datetime
    snippet: str | None = None
    body_text: str | None = None
    body_html: str | None = None
    raw_labels: list[str] = Field(default_factory=list)
    attachments: list[GmailAttachmentPayload] = Field(default_factory=list)
