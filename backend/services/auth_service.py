from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import auth_config
from db.models import User


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    result = await db.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def authenticate_user(
    db: AsyncSession, username: str, password: str
) -> User | None:
    user = await get_user_by_username(db, username)
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def create_access_token(user: User) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "role": user.role.value,
        "iat": now,
        "exp": now + timedelta(minutes=auth_config.JWT_EXPIRE_MINUTES),
    }
    return jwt.encode(
        payload, auth_config.JWT_SECRET_KEY, algorithm=auth_config.JWT_ALGORITHM
    )


def decode_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(
        token, auth_config.JWT_SECRET_KEY, algorithms=[auth_config.JWT_ALGORITHM]
    )
