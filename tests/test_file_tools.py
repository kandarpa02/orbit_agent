import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from main.tools.system import (
    DeleteDirectoryArgs,
    DeleteFileArgs,
    delete_directory,
    delete_file,
)
from main.tools.tools_registry import get_system_tools


class DeleteFileTests(unittest.IsolatedAsyncioTestCase):
    def test_delete_file_is_registered(self):
        names = [tool.name for tool in get_system_tools()]

        self.assertIn("delete_file", names)
        self.assertIn("delete_directory", names)

    async def test_deletes_workspace_relative_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            task_dir = workspace / "python_tasks"
            task_dir.mkdir()
            target = task_dir / "beluga_whale_S.jpg"
            target.write_bytes(b"image")

            with patch("main.tools.system.WORKSPACE", workspace):
                result = await delete_file(
                    DeleteFileArgs(path="python_tasks/beluga_whale_S.jpg")
                )

            self.assertIn("Deleted file:", result)
            self.assertFalse(target.exists())

    async def test_accepts_absolute_workspace_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            target = workspace / "beluga_whale_S.jpg"
            target.write_bytes(b"image")

            with patch("main.tools.system.WORKSPACE", workspace):
                result = await delete_file(DeleteFileArgs(path=str(target)))

            self.assertIn("Deleted file:", result)
            self.assertFalse(target.exists())

    async def test_rejects_absolute_path_outside_workspace(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            target = root / "outside.txt"
            target.write_text("keep", encoding="utf-8")

            with patch("main.tools.system.WORKSPACE", workspace):
                with self.assertRaises(PermissionError):
                    await delete_file(DeleteFileArgs(path=str(target)))

            self.assertTrue(target.exists())

    async def test_refuses_to_delete_directories(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            target = workspace / "directory"
            target.mkdir()

            with patch("main.tools.system.WORKSPACE", workspace):
                result = await delete_file(DeleteFileArgs(path=str(target)))

            self.assertIn("Cannot delete a directory", result)
            self.assertTrue(target.is_dir())


class DeleteDirectoryTests(unittest.IsolatedAsyncioTestCase):
    async def test_recursively_deletes_workspace_directory(self):
            with tempfile.TemporaryDirectory() as temp_dir:
                workspace = Path(temp_dir)
                target = workspace / "orbit_agent-main"
                nested = target / "main" / "tools"
                nested.mkdir(parents=True)
                (nested / "system.py").write_text("content", encoding="utf-8")

                with patch("main.tools.system.WORKSPACE", workspace):
                    result = await delete_directory(
                        DeleteDirectoryArgs(path="orbit_agent-main")
                    )

                self.assertIn("Deleted directory and its contents", result)
                self.assertFalse(target.exists())

    async def test_refuses_to_delete_workspace_root(self):
            with tempfile.TemporaryDirectory() as temp_dir:
                workspace = Path(temp_dir)
                marker = workspace / "keep.txt"
                marker.write_text("keep", encoding="utf-8")

                with patch("main.tools.system.WORKSPACE", workspace):
                    result = await delete_directory(DeleteDirectoryArgs(path="."))

                self.assertIn("workspace root", result)
                self.assertTrue(marker.exists())

    async def test_rejects_directory_outside_workspace(self):
            with tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                workspace = root / "workspace"
                workspace.mkdir()
                target = root / "outside"
                target.mkdir()
                (target / "keep.txt").write_text("keep", encoding="utf-8")

                with patch("main.tools.system.WORKSPACE", workspace):
                    with self.assertRaises(PermissionError):
                        await delete_directory(DeleteDirectoryArgs(path=str(target)))

                self.assertTrue(target.is_dir())
                self.assertTrue((target / "keep.txt").exists())

    @unittest.skipUnless(os.name == "nt", "Windows read-only attribute behavior")
    async def test_deletes_directory_with_readonly_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
                workspace = Path(temp_dir)
                target = workspace / "clone"
                target.mkdir()
                readonly_file = target / "repo.idx"
                readonly_file.write_text("index", encoding="utf-8")
                readonly_file.chmod(stat.S_IREAD)

                with patch("main.tools.system.WORKSPACE", workspace):
                    result = await delete_directory(
                        DeleteDirectoryArgs(path="clone")
                    )

                self.assertIn("Deleted directory and its contents", result)
                self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
