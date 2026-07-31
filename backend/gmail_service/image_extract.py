"""Vision extraction for field photos: container, seal, EIR, POD.

Same defensive shape as `field_extract.extract_fields`: a provider outage or
missing configuration must never crash the upload — the photo is still saved,
just without a read, and the user fills the fields in by hand.
"""

from __future__ import annotations

import base64
import logging
from typing import Any

from gmail_service.config import VISION_PROVIDER
from gmail_service.deterministic_extract import is_valid_container_no, normalize_container_no
from gmail_service.llm_client import call_azure_openai_vision, call_gemini_vision

logger = logging.getLogger(__name__)

DOC_KINDS = ("container_photo", "seal_photo", "eir", "pod")

# Azure `strict` mode requires additionalProperties:false and every property
# listed in `required`; optional fields are expressed as a nullable type.
IMAGE_EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "container_no",
        "seal_no",
        "license_plate",
        "doc_kind",
        "depot",
        "datetime_text",
        "raw_text",
        "confidence",
    ],
    "properties": {
        "container_no": {"type": ["string", "null"]},
        "seal_no": {"type": ["string", "null"]},
        "license_plate": {"type": ["string", "null"]},
        "doc_kind": {"type": "string", "enum": list(DOC_KINDS)},
        "depot": {"type": ["string", "null"]},
        "datetime_text": {"type": ["string", "null"]},
        "raw_text": {"type": ["string", "null"]},
        "confidence": {"type": "number"},
    },
}

PROMPT = (
    "You are reading a logistics field photo taken by a truck driver or ops "
    "staff at a container depot/port in Vietnam. It is one of: a container "
    "door photo (container number visible), a seal photo (the numbered seal "
    "clamp), an EIR (equipment interchange receipt / phiếu giao nhận cont), "
    "or a POD (proof of delivery). Read the container number (ISO 6346, "
    "4 letters + 7 digits, e.g. MSKU1234567), the seal number, any visible "
    "license plate, the depot/location name if printed, and any date/time "
    "text. Set fields you cannot read to null. Do not guess or invent a "
    "value — only report what is actually visible in the image."
)

_EMPTY_RESULT: dict[str, Any] = {
    "container_no": None,
    "seal_no": None,
    "license_plate": None,
    "doc_kind": None,
    "depot": None,
    "datetime_text": None,
    "raw_text": None,
    "confidence": None,
}


def humanize_vision_error(exc: Exception) -> str:
    """Turn a provider exception into one line a driver can act on.

    The raw text is a full provider JSON blob (quota ids, help urls, retry
    hints). Dumping that into the upload screen tells the person holding the
    phone nothing about what to do next, so classify the cases we know and
    keep the detail in the server log instead.
    """

    raw = str(exc)

    if "RESOURCE_EXHAUSTED" in raw or "429" in raw:
        return (
            "Hết hạn mức đọc ảnh tự động của nhà cung cấp AI (thường là giới hạn "
            "theo ngày của gói miễn phí). Ảnh đã được lưu — nhập số container tay, "
            "và báo Admin nâng hạn mức."
        )
    if "401" in raw or "403" in raw or "API key" in raw or "PERMISSION_DENIED" in raw:
        return (
            "Khoá API đọc ảnh không hợp lệ hoặc không đủ quyền. Ảnh đã được lưu — "
            "nhập số container tay, và báo Admin kiểm tra cấu hình."
        )
    if "timeout" in raw.lower() or "timed out" in raw.lower():
        return (
            "Đọc ảnh quá thời gian chờ. Ảnh đã được lưu — nhập số container tay "
            "hoặc thử lại với ảnh nhẹ hơn."
        )
    return "Không đọc được ảnh tự động. Ảnh đã được lưu — nhập số container tay."


def extract_from_image(image_bytes: bytes, mime_type: str) -> dict[str, Any]:
    """Read a field photo. Never raises: a failed/unconfigured read still
    returns a result dict, just with `extraction_status` telling why."""

    if VISION_PROVIDER == "none":
        return {
            **_EMPTY_RESULT,
            "extraction_status": "skipped",
            "extraction_error": None,
            "container_no_valid": False,
        }

    try:
        if VISION_PROVIDER == "gemini":
            # Gemini nhận thẳng bytes, không cần base64 như Azure.
            result = call_gemini_vision(
                PROMPT, image_bytes, mime_type, IMAGE_EXTRACTION_SCHEMA
            )
        else:
            image_base64 = base64.b64encode(image_bytes).decode("ascii")
            result = call_azure_openai_vision(
                PROMPT, image_base64, mime_type, IMAGE_EXTRACTION_SCHEMA
            )
    except Exception as exc:  # vision failures must not crash the upload
        # Full provider text goes to the log for whoever debugs the config;
        # the user gets the actionable one-liner.
        logger.warning("Vision extraction failed: %s", exc)
        return {
            **_EMPTY_RESULT,
            "extraction_status": "failed",
            "extraction_error": humanize_vision_error(exc),
            "container_no_valid": False,
        }

    container_no = result.get("container_no")
    container_no_valid = bool(container_no) and is_valid_container_no(container_no)
    if container_no:
        result["container_no"] = normalize_container_no(container_no)

    return {
        **_EMPTY_RESULT,
        **result,
        "extraction_status": "ok",
        "extraction_error": None,
        "container_no_valid": container_no_valid,
    }
