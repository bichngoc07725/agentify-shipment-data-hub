"""Admin-only user directory CRUD — the only way to create/manage users
besides the `scripts/seed_users.py` bootstrap script from GĐ1. See
`plan/phase_9_ui_theme_brief.md` Part 9B.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import User, UserRole
from services.auth_service import hash_password


async def list_users(db: AsyncSession) -> list[User]:
    result = await db.execute(select(User).order_by(User.created_at))
    return list(result.scalars().all())


async def get_user_by_id(db: AsyncSession, user_id: UUID) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def create_user(
    db: AsyncSession,
    username: str,
    display_name: str,
    role: UserRole,
    password: str,
) -> User:
    existing = await db.execute(select(User).where(User.username == username))
    if existing.scalar_one_or_none() is not None:
        raise ValueError(f"Username '{username}' already exists")

    user = User(
        username=username,
        display_name=display_name,
        role=role,
        password_hash=hash_password(password),
        is_active=True,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def update_user(
    db: AsyncSession,
    user: User,
    role: UserRole | None = None,
    is_active: bool | None = None,
    password: str | None = None,
) -> User:
    if role is not None:
        user.role = role
    if is_active is not None:
        user.is_active = is_active
    if password is not None:
        user.password_hash = hash_password(password)
    await db.flush()
    await db.refresh(user)
    return user
