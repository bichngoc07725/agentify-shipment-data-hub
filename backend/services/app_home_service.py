from sqlalchemy.ext.asyncio import AsyncSession

from api.models import AppHomeMailbox, AppHomeRecentContainer, AppHomeResponse
from services.container_service import get_container_count, get_recent_containers
from services.gmail_connection_service import list_gmail_connections
from services.sync_job_service import get_latest_completed_sync_job


async def build_app_home_payload(
    db: AsyncSession,
    list_connections=list_gmail_connections,
    get_latest_completed_job=get_latest_completed_sync_job,
    list_recent_containers=get_recent_containers,
    count_containers=get_container_count,
) -> AppHomeResponse:
    connections = [
        connection
        for connection in await list_connections(db)
        if connection.status == "connected"
    ]
    latest_job = await get_latest_completed_job(db)
    recent_containers = await list_recent_containers(db, limit=6)
    container_count = await count_containers(db)

    return AppHomeResponse(
        has_data=container_count > 0,
        container_count=container_count,
        last_sync_at=latest_job.completed_at if latest_job else None,
        connected_mailboxes=[
            AppHomeMailbox(
                id=connection.id,
                account_email=connection.account_email,
                status=connection.status,
            )
            for connection in connections
        ],
        recent_containers=[
            AppHomeRecentContainer(
                container_no=container.container_no,
                booking_no=container.booking_no,
                bl_no=container.bl_no,
                pod=container.pod,
                etd=container.etd,
                status_text=container.status_text,
                eta=container.eta,
                source_count=container.source_count,
                attachment_count=container.attachment_count,
                updated_at=container.updated_at,
            )
            for container in recent_containers
        ],
    )
