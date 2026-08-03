"""Logistics field extraction: deterministic rules first, LLM second.

Order matters. Rules run on every document so ingestion keeps working with no
LLM configured at all, and so exact-format identifiers (container, B/L, booking,
D/O) come from a rule whose precision is measurable. The LLM then fills in the
fields rules are bad at — parties, cargo descriptions, charge tables, ports and
free-time phrasing that varies per carrier.

On conflict, identifiers from rules win; everything else prefers the LLM.
"""

from __future__ import annotations

from typing import Any

from gmail_service.config import EXTRACTION_PROVIDER
from gmail_service.deterministic_extract import classify_document, extract_deterministic
from gmail_service.llm_client import (
    ExtractionUnavailable,
    call_azure_openai,
    call_gemini,
)

# Rules are more reliable than a model for these exact-format codes.
RULE_OWNED_IDENTIFIERS = (
    "container_no",
    "seal_no",
    "booking_no",
    "bl_no",
    "po_no",
    "do_no",
    "invoice_no",
    "declaration_no",
)

# Rules own the route dates because `05/07/2026` is 5 July on a Vietnamese
# document and models regularly read it as 7 May. Port and vessel names are
# free text, so the model reads them better than a regex does.
RULE_OWNED_ROUTE_FIELDS = ("etd", "eta", "ata")

_PARTY_SCHEMA = {
    "type": ["object", "null"],
    "additionalProperties": False,
    "required": ["name", "address", "contact_person", "email", "phone", "tax_code"],
    "properties": {
        "name": {"type": ["string", "null"]},
        "address": {"type": ["string", "null"]},
        "contact_person": {"type": ["string", "null"]},
        "email": {"type": ["string", "null"]},
        "phone": {"type": ["string", "null"]},
        "tax_code": {"type": ["string", "null"]},
    },
}

# Azure `strict` mode requires additionalProperties:false and every property
# listed in `required`; optional fields are expressed as a nullable type.
EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "doc_type",
        "doc_type_confidence",
        "doc_date",
        "reference_no",
        "payment_term",
        "number_of_originals",
        "carrier",
        "customer_name",
        "free_time_days",
        "identifiers",
        "issuer",
        "shipper",
        "consignee",
        "notify_party",
        "route",
        "cargo",
        "cargo_lines",
        "charges",
        "customs",
    ],
    "properties": {
        "doc_type": {
            "type": "string",
            "enum": [
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
            ],
        },
        "doc_type_confidence": {"type": "number"},
        "doc_date": {"type": ["string", "null"]},
        "reference_no": {"type": ["string", "null"]},
        "payment_term": {"type": ["string", "null"]},
        "number_of_originals": {"type": ["string", "null"]},
        "carrier": {"type": ["string", "null"]},
        "customer_name": {"type": ["string", "null"]},
        "free_time_days": {"type": ["integer", "null"]},
        "identifiers": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "container_no",
                "seal_no",
                "booking_no",
                "bl_no",
                "hbl_no",
                "sb_no",
                "awb_no",
                "po_no",
                "do_no",
                "job_no",
                "invoice_no",
                "hs_code",
                "declaration_no",
            ],
            "properties": {
                "container_no": {"type": "array", "items": {"type": "string"}},
                "seal_no": {"type": "array", "items": {"type": "string"}},
                "booking_no": {"type": ["string", "null"]},
                "bl_no": {"type": ["string", "null"]},
                "hbl_no": {"type": ["string", "null"]},
                "sb_no": {"type": ["string", "null"]},
                "awb_no": {"type": ["string", "null"]},
                "po_no": {"type": ["string", "null"]},
                "do_no": {"type": ["string", "null"]},
                "job_no": {"type": ["string", "null"]},
                "invoice_no": {"type": ["string", "null"]},
                "hs_code": {"type": ["string", "null"]},
                "declaration_no": {"type": ["string", "null"]},
            },
        },
        "issuer": _PARTY_SCHEMA,
        "shipper": _PARTY_SCHEMA,
        "consignee": _PARTY_SCHEMA,
        "notify_party": _PARTY_SCHEMA,
        "route": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "pol",
                "pod",
                "place_of_receipt",
                "final_destination",
                "cfs_terminal",
                "vessel",
                "voyage",
                "etd",
                "eta",
                "ata",
            ],
            "properties": {
                "pol": {"type": ["string", "null"]},
                "pod": {"type": ["string", "null"]},
                "place_of_receipt": {"type": ["string", "null"]},
                "final_destination": {"type": ["string", "null"]},
                "cfs_terminal": {"type": ["string", "null"]},
                "vessel": {"type": ["string", "null"]},
                "voyage": {"type": ["string", "null"]},
                "etd": {"type": ["string", "null"]},
                "eta": {"type": ["string", "null"]},
                "ata": {"type": ["string", "null"]},
            },
        },
        "cargo": {
            "type": ["object", "null"],
            "additionalProperties": False,
            "required": [
                "description",
                "packages",
                "gross_weight_kg",
                "tare_weight_kg",
                "volume_cbm",
                "marks_numbers",
            ],
            "properties": {
                "description": {"type": ["string", "null"]},
                "packages": {"type": ["string", "null"]},
                "gross_weight_kg": {"type": ["number", "null"]},
                "tare_weight_kg": {"type": ["number", "null"]},
                "volume_cbm": {"type": ["number", "null"]},
                "marks_numbers": {"type": ["string", "null"]},
            },
        },
        "cargo_lines": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "description",
                    "hs_code",
                    "origin",
                    "quantity",
                    "unit_price",
                    "amount",
                    "currency",
                ],
                "properties": {
                    "description": {"type": ["string", "null"]},
                    "hs_code": {"type": ["string", "null"]},
                    "origin": {"type": ["string", "null"]},
                    "quantity": {"type": ["string", "null"]},
                    "unit_price": {"type": ["number", "null"]},
                    "amount": {"type": ["number", "null"]},
                    "currency": {"type": ["string", "null"]},
                },
            },
        },
        "charges": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "description",
                    "quantity",
                    "currency",
                    "amount",
                    "vat_rate",
                ],
                "properties": {
                    "description": {"type": ["string", "null"]},
                    "quantity": {"type": ["string", "null"]},
                    "currency": {"type": ["string", "null"]},
                    "amount": {"type": ["number", "null"]},
                    "vat_rate": {"type": ["string", "null"]},
                },
            },
        },
        "customs": {
            "type": ["object", "null"],
            "additionalProperties": False,
            "required": [
                "declaration_type_code",
                "direction",
                "customs_office",
                "clearance_lane",
                "registration_date",
                "clearance_date",
                "total_tax_amount",
                "tax_currency",
            ],
            "properties": {
                "declaration_type_code": {"type": ["string", "null"]},
                "direction": {"type": ["string", "null"]},
                "customs_office": {"type": ["string", "null"]},
                "clearance_lane": {"type": ["string", "null"]},
                "registration_date": {"type": ["string", "null"]},
                "clearance_date": {"type": ["string", "null"]},
                "total_tax_amount": {"type": ["number", "null"]},
                "tax_currency": {"type": ["string", "null"]},
            },
        },
    },
}

PROMPT = """You extract structured data from Vietnamese and English logistics documents
(freight forwarding, sea import/export). Read the document below and fill the schema.

Rules:
- Use only what the document states. Never infer or invent a value.
- Unknown fields must be null; unknown arrays must be empty.
- All dates as YYYY-MM-DD. Vietnamese documents often use DD/MM/YYYY, so 05/07/2026
  means 5 July 2026, not 7 May 2026.
- free_time_days is the number of free days before demurrage/detention starts
  ("free time", "mien phi luu container"). Null if not stated.
- ata is the actual arrival date only when the document says the vessel has arrived.
- Never copy one date into another field. If the document states ETA but not ETD,
  leave etd null. The same applies to eta and ata.
- Container numbers are 4 letters + 7 digits.
- declaration_no (số tờ khai) is the customs declaration number, a 6-14 digit
  code. Do not confuse it with booking_no, bl_no, po_no or invoice_no.
- The `customs` object only applies to a customs_declaration document
  (Vietnamese "tờ khai hải quan" / "tờ khai hàng hóa xuất khẩu/nhập khẩu").
  Leave every field in it null for any other document type.
- cargo_lines is for a multi-row goods table (one row per HS code / item —
  columns like "Mô tả hàng hóa", "Mã số hàng hóa", "Xuất xứ", "Lượng hàng",
  "Đơn giá", "Trị giá"). Emit one cargo_lines entry per row, in the order they
  appear. Use `cargo` instead only when the document describes a single,
  unlisted shipment as one summary (no row-by-row table).

--- SUBJECT ---
{subject}
--- SENDER ---
{sender}
--- DOCUMENT TEXT ---
{text}"""


def build_prompt(subject: str, sender: str, text: str) -> str:
    return PROMPT.format(subject=subject, sender=sender, text=text)


def call_llm(subject: str, sender: str, text: str) -> dict[str, Any]:
    prompt = build_prompt(subject, sender, text)
    if EXTRACTION_PROVIDER == "azure_openai":
        return call_azure_openai(prompt, EXTRACTION_SCHEMA)
    if EXTRACTION_PROVIDER == "gemini":
        # Truyền schema để Gemini trả về đúng cấu trúc `merge_records` mong đợi,
        # ngang với ràng buộc `strict: True` của nhánh Azure.
        return call_gemini(prompt, EXTRACTION_SCHEMA)
    raise ExtractionUnavailable(
        f"No LLM extraction provider configured (provider={EXTRACTION_PROVIDER!r})"
    )


def call_llm_vision(
    subject: str, sender: str, image_bytes: bytes, mime_type: str
) -> dict[str, Any]:
    prompt = build_prompt(subject, sender, "(no text layer — read the attached document image)")
    if EXTRACTION_PROVIDER == "azure_openai":
        return call_azure_openai(
            prompt, EXTRACTION_SCHEMA, image_bytes=image_bytes, image_mime_type=mime_type
        )
    if EXTRACTION_PROVIDER == "gemini":
        return call_gemini(
            prompt, EXTRACTION_SCHEMA, image_bytes=image_bytes, image_mime_type=mime_type
        )
    raise ExtractionUnavailable(
        f"No LLM extraction provider configured (provider={EXTRACTION_PROVIDER!r})"
    )


def extract_fields_from_image(
    subject: str, sender: str, image_bytes: bytes, mime_type: str
) -> dict[str, Any]:
    """Extract fields from a photographed/scanned document via a vision LLM.

    There is no text layer to regex against here, so unlike `extract_fields`
    this has no partial/deterministic-fallback state for the fields
    themselves — only doc_type gets a best-effort guess from the subject line
    when no vision provider is configured or the call fails. On success,
    extraction_method is "llm" (never "hybrid" — rules contributed nothing).
    """
    subject = subject or ""
    sender = sender or ""
    doc_type, doc_type_confidence = classify_document(subject, "")

    if EXTRACTION_PROVIDER == "none":
        return {
            "doc_type": doc_type,
            "doc_type_confidence": doc_type_confidence,
            "identifiers": {},
            "route": {},
            "extraction_status": "failed",
            "extraction_method": "deterministic",
            "extraction_error": (
                "No LLM extraction provider configured; image documents "
                "require a vision LLM."
            ),
        }

    try:
        llm = call_llm_vision(subject, sender, image_bytes, mime_type)
    except Exception as exc:
        return {
            "doc_type": doc_type,
            "doc_type_confidence": doc_type_confidence,
            "identifiers": {},
            "route": {},
            "extraction_status": "failed",
            "extraction_method": "deterministic",
            "extraction_error": str(exc),
        }

    llm.setdefault("identifiers", {})
    llm.setdefault("route", {})
    llm["extraction_method"] = "llm"
    llm["extraction_status"] = "ok"
    if float(llm.get("doc_type_confidence") or 0) < doc_type_confidence:
        llm["doc_type"] = doc_type
        llm["doc_type_confidence"] = doc_type_confidence
    return llm


def extract_fields(subject: str, sender: str, pdf_text: str) -> dict[str, Any]:
    """Extract logistics fields, combining rules with the configured LLM.

    Never raises for LLM problems: rule output is always a usable result, so a
    provider outage degrades quality instead of failing ingestion.
    """
    subject = subject or ""
    sender = sender or ""
    pdf_text = pdf_text or ""

    rules = extract_deterministic(subject, sender, pdf_text)
    rules.pop("container_confidences", None)

    if EXTRACTION_PROVIDER == "none":
        rules["extraction_method"] = "deterministic"
        return rules

    try:
        llm = call_llm(subject, sender, pdf_text)
    except Exception as exc:
        rules["extraction_method"] = "deterministic"
        rules["extraction_status"] = "partial"
        rules["extraction_error"] = str(exc)
        return rules

    merged = merge_records(rules, llm)
    merged["extraction_method"] = "hybrid"
    return merged


def merge_records(rules: dict[str, Any], llm: dict[str, Any]) -> dict[str, Any]:
    """Combine rule output with LLM output.

    Identifiers listed in `RULE_OWNED_IDENTIFIERS` come from rules when rules
    found anything; every other field prefers the LLM and falls back to rules.
    """
    merged: dict[str, Any] = {**rules, **{k: v for k, v in llm.items() if v is not None}}

    rule_ids = rules.get("identifiers") or {}
    llm_ids = llm.get("identifiers") or {}
    identifiers = {**llm_ids}
    for field in RULE_OWNED_IDENTIFIERS:
        rule_value = rule_ids.get(field)
        if rule_value:
            identifiers[field] = rule_value
        elif field not in identifiers:
            identifiers[field] = [] if field in {"container_no", "seal_no"} else None
    merged["identifiers"] = identifiers

    rule_route = rules.get("route") or {}
    llm_route = llm.get("route") or {}
    route = {**{k: v for k, v in rule_route.items() if v}, **{
        key: value for key, value in llm_route.items() if value
    }}
    for field in RULE_OWNED_ROUTE_FIELDS:
        if rule_route.get(field):
            route[field] = rule_route[field]
    merged["route"] = route

    if not merged.get("free_time_days"):
        merged["free_time_days"] = rules.get("free_time_days") or llm.get(
            "free_time_days"
        )

    # A confident rule classification beats a weak model guess and vice versa.
    if float(llm.get("doc_type_confidence") or 0) < float(
        rules.get("doc_type_confidence") or 0
    ):
        merged["doc_type"] = rules["doc_type"]
        merged["doc_type_confidence"] = rules["doc_type_confidence"]

    return merged
