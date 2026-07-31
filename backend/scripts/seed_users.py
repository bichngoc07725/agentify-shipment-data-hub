from __future__ import annotations

import asyncio
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts._path import ensure_backend_root_on_path

ensure_backend_root_on_path(__file__)

from sqlalchemy import select

from db.database import AsyncSessionLocal
from db.models import User, UserRole
from services.auth_service import hash_password

# username, default password, role, display name
DEMO_USERS: list[tuple[str, str, UserRole, str]] = [
    ("admin", "admin@123", UserRole.ADMIN, "Quản trị hệ thống"),
    ("manager", "manager@123", UserRole.MANAGER, "Quản lý"),
    ("sales", "sales@123", UserRole.SALES_CS, "Sales / CS"),
    ("docs", "docs@123", UserRole.DOCS, "Chứng từ"),
    ("ops", "ops@123", UserRole.OPS, "Vận hành"),
    ("ketoan", "ketoan@123", UserRole.ACCOUNTANT, "Kế toán"),
    ("taixe", "taixe@123", UserRole.DRIVER, "Tài xế"),
]


async def _main() -> None:
    async with AsyncSessionLocal() as db:
        created = 0
        for username, password, role, display_name in DEMO_USERS:
            existing = (
                await db.execute(select(User).where(User.username == username))
            ).scalar_one_or_none()
            if existing is not None:
                continue
            db.add(
                User(
                    username=username,
                    password_hash=hash_password(password),
                    display_name=display_name,
                    role=role,
                )
            )
            created += 1
        await db.commit()
    print(f"users seeded: {created} created, {len(DEMO_USERS) - created} already existed")


if __name__ == "__main__":
    asyncio.run(_main())
