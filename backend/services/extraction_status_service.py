"""Phơi bày trạng thái trích xuất để nó không âm thầm tắt (P0-2).

Bối cảnh: `image_extract`/`field_extract` cố ý được viết phòng thủ — thiếu cấu
hình thì trả `extraction_status="skipped"` chứ không ném lỗi, để việc upload
ảnh không bao giờ crash. Mặt trái là hệ thống chạy y như bình thường trong khi
OCR **không hề hoạt động**: ảnh vẫn lưu, form vẫn hiện, chỉ là mọi trường đều
rỗng và người dùng tưởng "AI đọc không ra" thay vì "AI chưa từng được bật".

Module này trả lời đúng một câu: ngay lúc này, đọc ảnh và đọc văn bản có chạy
được không, và nếu không thì thiếu gì.
"""

from __future__ import annotations

from typing import Any

from gmail_service.config import (
    AZURE_OPENAI_DEPLOYMENT,
    AZURE_OPENAI_ENDPOINT,
    EXTRACTION_PROVIDER,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    VISION_PROVIDER,
)
from gmail_service.llm_client import azure_is_configured

# Tên hiển thị cho người vận hành, không phải giá trị cấu hình.
VISION_PROVIDER_LABELS = {
    "azure_openai": "azure_openai_vision",
    "gemini": "gemini_vision",
}


def _missing_azure_keys() -> list[str]:
    missing = []
    if not AZURE_OPENAI_ENDPOINT:
        missing.append("AZURE_OPENAI_ENDPOINT")
    if not AZURE_OPENAI_DEPLOYMENT:
        missing.append("AZURE_OPENAI_DEPLOYMENT")
    if not azure_is_configured() and "AZURE_OPENAI_ENDPOINT" not in missing:
        missing.append("AZURE_OPENAI_API_KEY")
    if not AZURE_OPENAI_ENDPOINT and not AZURE_OPENAI_DEPLOYMENT:
        missing = ["AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_DEPLOYMENT"]
    return missing


def get_extraction_status() -> dict[str, Any]:
    azure_ready = azure_is_configured()
    gemini_ready = bool(GEMINI_API_KEY)

    if EXTRACTION_PROVIDER == "none":
        text_ready = False
        text_provider = None
        text_reason = "EXTRACTION_PROVIDER đang đặt là 'none'"
    elif azure_ready:
        text_ready, text_provider, text_reason = True, "azure_openai", None
    elif gemini_ready:
        text_ready, text_provider, text_reason = True, "gemini", None
    else:
        text_ready = False
        text_provider = None
        text_reason = "Chưa cấu hình nhà cung cấp nào (thiếu API key)"

    image_ready = VISION_PROVIDER != "none"
    if image_ready:
        image_reason = None
    elif EXTRACTION_PROVIDER == "none":
        image_reason = "EXTRACTION_PROVIDER đang đặt là 'none'"
    else:
        image_reason = (
            f"Provider '{EXTRACTION_PROVIDER}' chưa có đủ khoá để đọc ảnh"
        )

    # Chỉ liệt kê khoá còn thiếu khi CHƯA có nhà cung cấp nào chạy được. Nếu
    # ảnh đã đọc được bằng Gemini thì việc thiếu khoá Azure không còn là vấn
    # đề, hiện ra chỉ gây hiểu nhầm là hệ thống đang hỏng.
    if image_ready and text_ready:
        missing_keys: list[str] = []
    elif gemini_ready:
        missing_keys = ["GEMINI_API_KEY"] if not GEMINI_API_KEY else []
    else:
        missing_keys = _missing_azure_keys()

    return {
        "provider_setting": EXTRACTION_PROVIDER,
        "text_extraction": {
            "ready": text_ready,
            "provider": text_provider,
            "reason": text_reason,
            "fallback": "Vẫn trích được bằng luật (regex) khi không có LLM",
        },
        "image_ocr": {
            "ready": image_ready,
            "provider": VISION_PROVIDER_LABELS.get(VISION_PROVIDER),
            "reason": image_reason,
            "fallback": "Không có — ảnh vẫn lưu nhưng mọi trường phải nhập tay",
        },
        "missing_keys": missing_keys,
        "gemini_model": GEMINI_MODEL if gemini_ready else None,
    }
