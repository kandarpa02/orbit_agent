import asyncio
import os
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from main.tools.python_task import (
    PythonTaskArgs,
    _python_in_venv,
    _task_environment,
    run_python_task,
)
from main.tools.python_task import TASK_WORKSPACE


class PythonTaskTests(unittest.IsolatedAsyncioTestCase):
    def test_uses_platform_virtualenv_interpreter(self):
        venv_path = Path("temporary-venv")
        expected = (
            venv_path / "Scripts" / "python.exe"
            if os.name == "nt"
            else venv_path / "bin" / "python"
        )

        self.assertEqual(_python_in_venv(venv_path), expected)

    def test_task_environment_does_not_inherit_orbit_secrets(self):
        with patch.dict(os.environ, {"ORBIT_API_KEY": "secret-value"}):
            environment = _task_environment("C:/temp/task", Path("C:/temp/task/venv"))

        self.assertNotIn("ORBIT_API_KEY", environment)
        self.assertEqual(environment["TEMP"], "C:/temp/task")

    async def test_runs_script_in_temporary_virtual_environment(self):
        with patch(
            "main.tools.python_task._execute",
            new=AsyncMock(
                side_effect=[
                    (0, "", False),
                    (0, "download complete\n", False),
                ]
            ),
        ) as execute:
            result = await run_python_task(PythonTaskArgs(code="print('ok')"))

        self.assertIn("Exit code: 0", result)
        self.assertIn("download complete", result)
        self.assertIn(f"Task working directory: {TASK_WORKSPACE.resolve()}", result)
        self.assertIn("print('ok')", execute.await_args_list[1].args[0])
        self.assertEqual(execute.await_args_list[1].kwargs["cwd"], TASK_WORKSPACE.resolve())

    async def test_reports_virtual_environment_setup_failure(self):
        with patch(
            "main.tools.python_task._execute",
            new=AsyncMock(return_value=(1, "ensurepip unavailable", False)),
        ):
            result = await run_python_task(PythonTaskArgs(code="print('ok')"))

        self.assertIn("environment setup failed", result)
        self.assertIn("ensurepip unavailable", result)


if __name__ == "__main__":
    unittest.main()
