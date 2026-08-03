from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps.permissions import CurrentUser, require_permission
from api.models import AppHomeResponse
from db.database import get_db
from services.app_home_service import build_app_home_payload

router = APIRouter(prefix="/api/v1/app-home", tags=["app-home"])


@router.get("", response_model=AppHomeResponse)
async def get_app_home(
    db: AsyncSession = Depends(get_db),
    # Fleet-wide container/exception counters — same audience as reading a
    # container, so it reuses that gate rather than being open to any login.
    _current_user: CurrentUser = Depends(
        require_permission("container_facts", "view")
    ),
) -> AppHomeResponse:
    return await build_app_home_payload(db)
