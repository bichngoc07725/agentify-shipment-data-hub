from __future__ import annotations

import sys
from pathlib import Path


def ensure_backend_root_on_path(current_file: str | Path) -> Path:
    backend_root = Path(current_file).resolve().parents[1]
    backend_root_str = str(backend_root)
    if backend_root_str not in sys.path:
        sys.path.insert(0, backend_root_str)
    return backend_root
