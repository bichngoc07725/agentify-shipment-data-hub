from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps.permissions import CurrentUser, require_permission
from api.models import (
    UserCreateRequest,
    UserListResponse,
    UserResponse,
    UserUpdateRequest,
)
from db.database import get_db
from db.models import User, UserRole
from services.user_service import create_user, get_user_by_id, list_users, update_user

router = APIRouter(prefix="/api/v1/users", tags=["users"])


def _to_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        role=user.role.value,
        is_active=user.is_active,
        created_at=user.created_at,
    )


@router.get("", response_model=UserListResponse)
async def list_users_endpoint(
    db: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_permission("system_config", "view")),
) -> UserListResponse:
    users = await list_users(db)
    return UserListResponse(items=[_to_response(u) for u in users], total=len(users))


@router.post("", response_model=UserResponse)
async def create_user_endpoint(
    payload: UserCreateRequest,
    db: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(
        require_permission("system_config", "create")
    ),
) -> UserResponse:
    try:
        user = await create_user(
            db,
            username=payload.username,
            display_name=payload.display_name,
            role=UserRole(payload.role),
            password=payload.password,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _to_response(user)


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user_endpoint(
    user_id: UUID,
    payload: UserUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_permission("system_config", "edit")),
) -> UserResponse:
    user = await get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    updated = await update_user(
        db,
        user,
        role=UserRole(payload.role) if payload.role else None,
        is_active=payload.is_active,
        password=payload.password,
    )
    return _to_response(updated)
