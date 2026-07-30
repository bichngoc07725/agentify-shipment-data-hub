"""LLM clients used for logistics document extraction.

Two providers are supported, both constrained by the same strict JSON schema
(`field_extract.EXTRACTION_SCHEMA`) so neither can return a field with the
wrong shape or omit one outright:

- `azure_openai` — Azure AI Foundry Responses API's `json_schema` strict mode.
- `gemini` — `GenerateContentConfig.response_json_schema`, the equivalent
  structured-output mode on Gemini's side.

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
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"Azure extraction failed ({exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Azure extraction unreachable: {exc.reason}") from exc

    return json.loads(_azure_output_text(body))


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


def call_gemini(
    prompt: str,
    schema: dict[str, Any],
    *,
    image_bytes: bytes | None = None,
    image_mime_type: str | None = None,
) -> dict[str, Any]:
    if not GEMINI_API_KEY:
        raise ExtractionUnavailable("GEMINI_API_KEY is required for Gemini extraction")

    from google import genai
    from google.genai import types

    contents: Any = prompt
    if image_bytes is not None:
        contents = [
            prompt,
            types.Part.from_bytes(data=image_bytes, mime_type=image_mime_type),
        ]

    client = genai.Client(api_key=GEMINI_API_KEY)
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_json_schema=schema,
    )
    response = client.models.generate_content(
        model=GEMINI_MODEL, contents=contents, config=config
    )
    raw = response.text.strip().removeprefix("```json").removesuffix("```").strip()
    return json.loads(raw)
