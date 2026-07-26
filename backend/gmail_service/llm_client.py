"""LLM clients used for logistics document extraction.

Two providers are supported:

- `azure_openai` — Azure AI Foundry Responses API with a strict JSON schema, so
  the model cannot return anything but a conforming object.
- `gemini` — kept for backward compatibility; the model is asked for JSON and
  the response is parsed defensively.

Azure is called with `urllib` rather than an SDK so the backend keeps its
current dependency set.
"""

from __future__ import annotations

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
) -> dict[str, Any]:
    """Call the Azure Responses API and return the parsed structured output."""
    if not azure_is_configured():
        raise ExtractionUnavailable(
            "Azure extraction needs endpoint, api_key and deployment to be set"
        )

    payload = {
        "model": AZURE_OPENAI_DEPLOYMENT,
        "input": [{"role": "user", "content": prompt[:AZURE_OPENAI_MAX_INPUT_CHARS]}],
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


def call_gemini(prompt: str) -> dict[str, Any]:
    if not GEMINI_API_KEY:
        raise ExtractionUnavailable("GEMINI_API_KEY is required for Gemini extraction")

    from google import genai

    client = genai.Client(api_key=GEMINI_API_KEY)
    response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
    raw = response.text.strip().removeprefix("```json").removesuffix("```").strip()
    return json.loads(raw)
