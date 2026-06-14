# Agentify Logistics Backend

FastAPI + PostgreSQL backend for the narrow prototype:

- connect Gmail mailboxes via OAuth
- track sync jobs
- execute Gmail fetch + PDF extraction inside the backend
- ingest processed emails/PDF extraction output through the existing container-centric DB path
- aggregate data by `container_no`
- serve container/email lookup APIs for the frontend

The backend intentionally follows the same operational style as
`~/Documents/a-star/hackathon-aggregator/search-engine`:

- `.env` + `app-config.yaml`
- `config/`, `db/`, `api/`, `services/`
- `gmail_service/` for Gmail-specific integration code
- async SQLAlchemy session dependency
- Alembic migration flow
- Dockerfile + `compose.yaml`
- one canonical `DATABASE_URL`, with sync/async SQLAlchemy URLs derived in config

## Deploy Notes

- Backend listens on `8766`.
- For Vercel frontend deployment, set `CORS_ORIGINS` to include the deployed frontend URL.
- If you use Gmail OAuth, set `GMAIL_FRONTEND_RETURN_URL` to the deployed frontend setup page and `GMAIL_REDIRECT_URI` to the public backend callback URL.
- If the backend is behind a reverse proxy, set `APP_PROXY_ROOT_PATH` accordingly; otherwise leave it empty.

## Quick Start

1. Copy `.env.example` to `.env` if needed.
2. Review `app-config.yaml`.
3. Install deps with `uv sync`.
4. Run migration with `./.venv/bin/alembic upgrade head`.
5. Start API with `./.venv/bin/uvicorn api.routes.api_main:app --reload --port 8766`.

## Reset DB Manually

- Recreate the current schema from `db/models.py` with `./.venv/bin/python -m scripts.reset_database`.
- The API does not auto-run `init_db()` on startup, so Docker/app boot will not reset schema automatically.

## Attachment Storage

- Gmail PDF attachments are persisted under `backend/storage/gmail_attachments/`.
- `docker-compose.yml` mounts `/app/storage` to the named volume `agentify-logistics-storage` so synced PDFs survive container rebuilds and can be previewed later.
- If you change the storage strategy, keep attachment paths under the backend root because `/api/v1/attachments/{id}/file` only serves files from that safe subtree.

## Gmail OAuth Config

The embedded Gmail module expects these env vars:

- `GMAIL_CREDENTIALS_FILE`
- `GMAIL_REDIRECT_URI`
- `GMAIL_FRONTEND_RETURN_URL`
- `GMAIL_QUERY`
- `GEMINI_API_KEY`
- `GEMINI_MODEL`
- `CORS_ORIGINS`
- `ALLOW_ORIGINS_REGEX`

Connection flow:

1. Frontend calls `GET /api/v1/gmail-connections/oauth/start`.
2. Backend returns a Google authorization URL.
3. Google redirects back to `GET /api/v1/gmail-connections/oauth/callback`.
4. Backend exchanges the code, stores the refresh token in `gmail_connections`, and redirects back to the setup page.
5. Frontend creates and runs sync jobs through `/api/v1/sync-jobs` and `/api/v1/sync-jobs/{job_id}/run`.
