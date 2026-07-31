"""LLM clients used for logistics document extraction.

Two providers are supported, both constrained by the same strict JSON schema
(`field_extract.EXTRACTION_SCHEMA`) so neither can return a field with the
wrong shape or omit one outright:

- `azure_openai` — Azure AI Foundry Responses API's `json_schema` strict mode.
- `gemini` — `GenerateContentConfig.response_schema`, the equivalent
  structured-output mode on Gemini's side. The JSON Schema is converted first
  by `to_gemini_schema()` because Gemini expects the OpenAPI dialect.

Azure is called with `urllib` rather than an SDK so the backend keeps its
current dependency set.

Both `call_azure_openai` and `call_gemini` accept an optional image (bytes +
mime type) alongside the text prompt, for reading photographed/scanned
documents that have no text layer to extract first.
"""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from typing import Any

from gmail_service.config import (
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_DEPLOYMENT,
    AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_MAX_INPUT_CHARS,
    AZURE_OPENAI_REASONING_EFFORT,
    AZURE_OPENAI_TIMEOUT_SECONDS,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    GEMINI_TIMEOUT_SECONDS,
)


class ExtractionUnavailable(RuntimeError):
    """No LLM provider is configured, or the configured one is unusable."""


def azure_is_configured() -> bool:
    return bool(AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY and AZURE_OPENAI_DEPLOYMENT)


def call_azure_openai(
    prompt: str,
    schema: dict[str, Any],
    schema_name: str = "logistics_document",
    *,
    image_bytes: bytes | None = None,
    image_mime_type: str | None = None,
) -> dict[str, Any]:
    """Call the Azure Responses API and return the parsed structured output.

    Pass `image_bytes`/`image_mime_type` to send a photographed/scanned
    document as an `input_image` content part alongside the text prompt,
    instead of (or in addition to) already-extracted text.
    """
    if not azure_is_configured():
        raise ExtractionUnavailable(
            "Azure extraction needs endpoint, api_key and deployment to be set"
        )

    text_content = prompt[:AZURE_OPENAI_MAX_INPUT_CHARS]
    content: Any = text_content
    if image_bytes is not None:
        encoded = base64.b64encode(image_bytes).decode("ascii")
        content = [
            {"type": "input_text", "text": text_content},
            {
                "type": "input_image",
                "image_url": f"data:{image_mime_type};base64,{encoded}",
            },
        ]

    payload = {
        "model": AZURE_OPENAI_DEPLOYMENT,
        "input": [{"role": "user", "content": content}],
        "text": {
            "format": {
                "type": "json_schema",
                "name": schema_name,
                "strict": True,
                "schema": schema,
            }
        },
    }
    if AZURE_OPENAI_REASONING_EFFORT:
        payload["reasoning"] = {"effort": AZURE_OPENAI_REASONING_EFFORT}

    return json.loads(_azure_output_text(_send_azure_request(payload)))


def call_azure_openai_vision(
    prompt: str,
    image_base64: str,
    mime_type: str,
    schema: dict[str, Any],
    schema_name: str = "field_image",
) -> dict[str, Any]:
    """Same Responses API call as `call_azure_openai`, with an image block
    attached to the user turn so the model can read a field photo."""
    if not azure_is_configured():
        raise ExtractionUnavailable(
            "Azure extraction needs endpoint, api_key and deployment to be set"
        )

    payload = {
        "model": AZURE_OPENAI_DEPLOYMENT,
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {
                        "type": "input_image",
                        "image_url": f"data:{mime_type};base64,{image_base64}",
                    },
                ],
            }
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": schema_name,
                "strict": True,
                "schema": schema,
            }
        },
    }
    if AZURE_OPENAI_REASONING_EFFORT:
        payload["reasoning"] = {"effort": AZURE_OPENAI_REASONING_EFFORT}

    return json.loads(_azure_output_text(_send_azure_request(payload)))


def _send_azure_request(payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        AZURE_OPENAI_ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "api-key": AZURE_OPENAI_API_KEY,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            request, timeout=AZURE_OPENAI_TIMEOUT_SECONDS
        ) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"Azure extraction failed ({exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Azure extraction unreachable: {exc.reason}") from exc


def _azure_output_text(body: dict[str, Any]) -> str:
    """Pull the assistant text out of a Responses API envelope.

    The output array also carries reasoning items, which have no text content.
    """
    if body.get("status") == "incomplete":
        reason = (body.get("incomplete_details") or {}).get("reason", "unknown")
        raise RuntimeError(f"Azure extraction returned an incomplete response: {reason}")

    for item in body.get("output", []):
        if item.get("type") != "message":
            continue
        for chunk in item.get("content", []):
            text = chunk.get("text")
            if text:
                return text

    raise RuntimeError("Azure extraction returned no message content")


def to_gemini_schema(node: Any) -> Any:
    """Chuyển JSON Schema (kiểu OpenAI) sang schema OpenAPI mà Gemini nhận.

    Hai bảng schema khác nhau ở chỗ:
    - JSON Schema cho phép union `"type": ["string", "null"]`; Gemini chỉ nhận
      MỘT type viết hoa kèm cờ `nullable`.
    - `additionalProperties` không được hỗ trợ nên bị bỏ.

    Không ép schema thì Gemini tự đặt tên trường theo ý nó (`vessel_name`,
    `container_numbers`...), và `merge_records` — vốn đọc `llm["identifiers"]`
    / `llm["route"]` — sẽ lặng lẽ vứt toàn bộ dữ liệu LLM, chỉ còn regex.
    """
    if not isinstance(node, dict):
        return node

    out: dict[str, Any] = {}
    node_type = node.get("type")
    if isinstance(node_type, list):
        non_null = [t for t in node_type if t != "null"]
        out["type"] = (non_null[0] if non_null else "string").upper()
        if "null" in node_type:
            out["nullable"] = True
    elif isinstance(node_type, str):
        out["type"] = node_type.upper()

    for key in ("enum", "description"):
        if key in node:
            out[key] = node[key]
    if "properties" in node:
        out["properties"] = {
            name: to_gemini_schema(value) for name, value in node["properties"].items()
        }
        if node.get("required"):
            out["required"] = list(node["required"])
    if "items" in node:
        out["items"] = to_gemini_schema(node["items"])
    return out


def call_gemini(
    prompt: str,
    schema: dict[str, Any] | None = None,
    *,
    image_bytes: bytes | None = None,
    image_mime_type: str | None = None,
) -> dict[str, Any]:
    if not GEMINI_API_KEY:
        raise ExtractionUnavailable("GEMINI_API_KEY is required for Gemini extraction")

    from google import genai
    from google.genai import types

    # Ảnh (nếu có) đi kèm prompt trong cùng `contents` — dùng cho chứng từ scan
    # không có lớp text. Không có ảnh thì `contents` chỉ là prompt như cũ.
    contents: Any = prompt
    if image_bytes is not None:
        contents = [
            prompt,
            types.Part.from_bytes(data=image_bytes, mime_type=image_mime_type),
        ]

    # SDK mặc định `timeout=None` (chờ vô hạn). Nhánh Azure đã có timeout riêng;
    # thiếu ở đây thì một lần Gemini treo sẽ làm đứng luôn worker ingestion, và
    # `extract_fields` không cứu được vì treo không sinh exception để bắt.
    # `timeout` của SDK tính bằng mili-giây.
    client = genai.Client(
        api_key=GEMINI_API_KEY,
        http_options=types.HttpOptions(timeout=GEMINI_TIMEOUT_SECONDS * 1000),
    )

    # Ép cấu trúc đầu ra giống hệt nhánh Azure (`strict: True`). Thiếu bước này
    # Gemini vẫn trả JSON hợp lệ nhưng tự đặt tên trường, và dữ liệu nó đọc được
    # sẽ bị `merge_records` bỏ đi hết — pipeline báo "hybrid" trong khi thực chất
    # chỉ có regex chạy.
    config = None
    if schema is not None:
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=to_gemini_schema(schema),
        )

    response = client.models.generate_content(
        model=GEMINI_MODEL, contents=contents, config=config
    )

    # `response.text` là None khi model bị chặn bởi safety filter hoặc trả về
    # phần rỗng — khi đó `.strip()` sẽ ném AttributeError khó đọc, nên báo lỗi
    # rõ ràng để `extract_fields` ghi được nguyên nhân thật vào extraction_error.
    text = response.text
    if not text:
        raise RuntimeError(
            f"Gemini returned no text (model={GEMINI_MODEL!r}); "
            "có thể bị safety filter chặn hoặc model trả về rỗng"
        )

    raw = text.strip().removeprefix("```json").removesuffix("```").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Gemini trả về JSON không hợp lệ: {exc}. Đoạn đầu: {raw[:200]!r}"
        ) from exc


def call_gemini_vision(
    prompt: str,
    image_bytes: bytes,
    mime_type: str,
    schema: dict[str, Any],
) -> dict[str, Any]:
    """Đọc ảnh hiện trường bằng Gemini — đối ứng của `call_azure_openai_vision`.

    Khác `call_gemini` ở chỗ ảnh được gửi thẳng dạng bytes (`Part.from_bytes`)
    thay vì base64 nhúng trong chuỗi như Azure yêu cầu, nên không phải tự mã
    hoá. Vẫn ép `response_schema` để model trả đúng khuôn
    `IMAGE_EXTRACTION_SCHEMA`, giống ràng buộc `strict: True` bên Azure.
    """
    if not GEMINI_API_KEY:
        raise ExtractionUnavailable("GEMINI_API_KEY is required for Gemini extraction")

    from google import genai
    from google.genai import types

    client = genai.Client(
        api_key=GEMINI_API_KEY,
        http_options=types.HttpOptions(timeout=GEMINI_TIMEOUT_SECONDS * 1000),
    )
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            prompt,
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=to_gemini_schema(schema),
        ),
    )

    text = response.text
    if not text:
        raise RuntimeError(
            f"Gemini không trả về nội dung khi đọc ảnh (model={GEMINI_MODEL!r}); "
            "có thể bị safety filter chặn"
        )

    raw = text.strip().removeprefix("```json").removesuffix("```").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Gemini trả về JSON không hợp lệ khi đọc ảnh: {exc}. "
            f"Đoạn đầu: {raw[:200]!r}"
        ) from exc
