from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from scripts._path import ensure_backend_root_on_path


class ScriptPathSetupTest(TestCase):
    def test_adds_backend_root_when_running_script_directly(self) -> None:
        script_path = Path(__file__).resolve().parents[1] / "scripts" / "reset_database.py"
        backend_root = script_path.parents[1]

        with patch("scripts._path.sys.path", [str(script_path.parent)]):
            resolved_root = ensure_backend_root_on_path(script_path)

        self.assertEqual(resolved_root, backend_root)
        self.assertEqual(str(backend_root), str(resolved_root))

    def test_keeps_backend_root_singleton_on_sys_path(self) -> None:
        script_path = Path(__file__).resolve().parents[1] / "scripts" / "reset_database.py"
        backend_root = script_path.parents[1]

        with patch("scripts._path.sys.path", [str(backend_root), str(script_path.parent)]):
            ensure_backend_root_on_path(script_path)
            sys_path_after = list(__import__("sys").path)

        self.assertEqual(sys_path_after.count(str(backend_root)), 1)
