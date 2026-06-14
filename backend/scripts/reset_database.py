from __future__ import annotations

import asyncio
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts._path import ensure_backend_root_on_path

ensure_backend_root_on_path(__file__)
from db.database import reset_db


async def _main() -> None:
    await reset_db()


if __name__ == "__main__":
    asyncio.run(_main())
