from uuid import UUID

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi import Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import require_internal_api_key
from api.deps.permissions import CurrentUser, require_permission
from api.models import (
    CreateSyncJobRequest,
    SyncJobListResponse,
    SyncJobResponse,
    UpdateSyncJobRequest,
)
from db.database import AsyncSessionLocal, get_db
from services.gmail_connection_service import get_gmail_connection
from services.gmail_ingestion_service import execute_sync_job
from services.sync_job_service import (
    create_sync_job,
    get_sync_job,
    list_sync_jobs,
    update_sync_job,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/sync-jobs", tags=["sync-jobs"])


@router.get("", response_model=SyncJobListResponse)
async def list_sync_jobs_endpoint(
    gmail_connection_id: UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_permission("system_config", "view")),
) -> SyncJobListResponse:
    items, total = await list_sync_jobs(
        db,
        gmail_connection_id=gmail_connection_id,
        page=page,
        page_size=page_size,
    )
    return SyncJobListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=SyncJobResponse)
async def create_sync_job_endpoint(
    payload: CreateSyncJobRequest,
    db: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_permission("system_config", "edit")),
) -> SyncJobResponse:
    try:
        return await create_sync_job(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/{job_id}", response_model=SyncJobResponse)
async def get_sync_job_endpoint(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_permission("system_config", "view")),
) -> SyncJobResponse:
    job = await get_sync_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Sync job not found")
    return job


@router.patch("/{job_id}", response_model=SyncJobResponse)
async def update_sync_job_endpoint(
    job_id: UUID,
    payload: UpdateSyncJobRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_internal_api_key),
) -> SyncJobResponse:
    job = await update_sync_job(db, job_id, payload)
    if job is None:
        raise HTTPException(status_code=404, detail="Sync job not found")
    return job


async def _run_sync_job_in_background(job_id: UUID) -> None:
    """Fetch + extract on a session of its own.

    The request's session is closed once the response is sent, so the work
    cannot borrow it. Failures are already recorded on the job row by
    `execute_sync_job`; anything escaping that is logged rather than raised,
    since there is no client left to receive it.
    """

    async with AsyncSessionLocal() as session:
        try:
            job = await get_sync_job(session, job_id)
            if job is None:
                return
            connection = await get_gmail_connection(session, job.gmail_connection_id)
            if connection is None:
                return
            await execute_sync_job(session, connection, job)
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception("Background sync job %s failed", job_id)


@router.post("/{job_id}/run", response_model=SyncJobResponse)
async def run_sync_job_endpoint(
    job_id: UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_permission("system_config", "edit")),
) -> SyncJobResponse:
    """Kick the sync off and answer immediately.

    Running it inline held the HTTP request open for the whole fetch (minutes
    on a real mailbox), so the UI could only show a frozen button and never
    the progress the job was already recording.
    """

    job = await get_sync_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Sync job not found")

    connection = await get_gmail_connection(db, job.gmail_connection_id)
    if connection is None:
        raise HTTPException(status_code=404, detail="Gmail connection not found")

    if job.status == "running":
        raise HTTPException(status_code=409, detail="Sync job is already running")

    # Marked here, not in the background task, so the response the UI gets back
    # already reads "running" and its poll loop starts on the first tick.
    updated = await update_sync_job(
        db, job_id, UpdateSyncJobRequest(status="running", error_message=None)
    )
    background_tasks.add_task(_run_sync_job_in_background, job_id)
    return updated
