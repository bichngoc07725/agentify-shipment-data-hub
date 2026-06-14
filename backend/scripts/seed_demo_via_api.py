from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts._path import ensure_backend_root_on_path
from scripts.seed_demo_data import (
    DEMO_ACCOUNT_EMAIL,
    DEMO_CONTAINER_NOS,
    DEMO_DISPLAY_NAME,
    build_demo_payloads,
)

ensure_backend_root_on_path(__file__)
API_BASE_URL = os.getenv("AGENTIFY_API_BASE_URL", "http://127.0.0.1:8766")
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "agentify-dev-key")


def _request(method: str, path: str, payload: dict | None = None) -> dict:
    body = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
    if path.startswith("/api/v1/internal/"):
        headers["X-Internal-API-Key"] = INTERNAL_API_KEY

    request = urllib.request.Request(
        url=f"{API_BASE_URL}{path}",
        data=body,
        headers=headers,
        method=method,
    )
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> None:
    connection = _request(
        "POST",
        "/api/v1/gmail-connections",
        {
            "account_email": DEMO_ACCOUNT_EMAIL,
            "display_name": DEMO_DISPLAY_NAME,
            "google_account_id": "agentify-demo-google-account",
            "encrypted_refresh_token": "demo-refresh-token",
            "access_scope": "gmail.readonly",
            "status": "connected",
        },
    )

    sync_job = _request(
        "POST",
        "/api/v1/sync-jobs",
        {
            "gmail_connection_id": connection["id"],
            "query": "label:LOGISTICS newer_than:30d",
            "max_results": 200,
        },
    )

    payloads = build_demo_payloads(connection["id"], sync_job["id"])
    for payload in payloads:
        _request(
            "POST",
            "/api/v1/internal/processed-emails",
            payload.model_dump(mode="json"),
        )

    _request(
        "PATCH",
        f"/api/v1/sync-jobs/{sync_job['id']}",
        {
            "status": "completed",
            "started_at": "2026-06-08T03:00:00Z",
            "completed_at": "2026-06-08T03:02:30Z",
            "emails_fetched": len(payloads),
            "attachments_found": sum(len(payload.attachments) for payload in payloads),
            "pdf_text_extracted": sum(len(payload.attachments) for payload in payloads),
            "containers_upserted": len(DEMO_CONTAINER_NOS),
        },
    )

    print(f"seeded_connection_id: {connection['id']}")
    print(f"seeded_sync_job_id: {sync_job['id']}")
    print(f"emails_seeded: {len(payloads)}")


if __name__ == "__main__":
    main()
