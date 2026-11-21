from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path

from pydantic import BaseModel, Field

from .system import WORKSPACE, is_inside


TASK_WORKSPACE = WORKSPACE / "python_tasks"
MAX_OUTPUT_SIZE = 20_000


class PythonTaskArgs(BaseModel):
    code: str = Field(min_length=1, max_length=20_000)
    timeout: int = Field(default=120, ge=1, le=300)


def _python_in_venv(venv_path: Path) -> Path:
    if os.name == "nt":
        return venv_path / "Scripts" / "python.exe"
    return venv_path / "bin" / "python"


def _task_environment(temp_dir: str, venv_path: Path) -> dict[str, str]:
    environment = {
        key: os.environ[key]
        for key in ("PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT")
        if key in os.environ
    }

    scripts_dir = venv_path / ("Scripts" if os.name == "nt" else "bin")
    environment["PATH"] = str(scripts_dir) + os.pathsep + environment.get("PATH", "")
    environment["TEMP"] = temp_dir
    environment["TMP"] = temp_dir
    environment["PYTHONNOUSERSITE"] = "1"
    environment["PYTHONUNBUFFERED"] = "1"
    environment["PYTHONIOENCODING"] = "utf-8"
    environment["PIP_CONFIG_FILE"] = os.devnull
    environment["PIP_CACHE_DIR"] = str(Path(temp_dir) / "pip-cache")

    if os.name == "nt":
        environment["USERPROFILE"] = temp_dir
        environment["APPDATA"] = str(Path(temp_dir) / "AppData" / "Roaming")
        environment["LOCALAPPDATA"] = str(Path(temp_dir) / "AppData" / "Local")
    else:
        environment["HOME"] = temp_dir

    return environment


async def _read_output(stream: asyncio.StreamReader) -> str:
    output = bytearray()
    truncated = False

    while True:
        chunk = await stream.read(4096)
        if not chunk:
            break
        remaining = MAX_OUTPUT_SIZE - len(output)
        if remaining > 0:
            output.extend(chunk[:remaining])
        if len(chunk) > remaining:
            truncated = True

    text = output.decode("utf-8", errors="replace")
    if truncated:
        text += "\n[Output truncated]"
    return text


async def _execute(
    command: list[str],
    timeout: int,
    cwd: Path | None = None,
    environment: dict[str, str] | None = None,
) -> tuple[int | None, str, bool]:
    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=cwd,
            env=environment,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
    except OSError as exc:
        return None, f"{type(exc).__name__}: {exc}", False

    output_reader = asyncio.create_task(_read_output(process.stdout))

    try:
        return_code = await asyncio.wait_for(process.wait(), timeout=timeout)
    except asyncio.CancelledError:
        process.kill()
        await process.wait()
        await output_reader
        raise
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        return None, await output_reader, True

    return return_code, await output_reader, False


async def run_python_task(args: PythonTaskArgs) -> str:
    """Run generated Python in a temporary virtual environment on the host."""
    if "\x00" in args.code:
        return "Python task was not started: script contains a null character."

    try:
        TASK_WORKSPACE.mkdir(parents=True, exist_ok=True)
        task_workspace = TASK_WORKSPACE.resolve()
        if not is_inside(task_workspace, WORKSPACE.resolve()):
            return (
                "Python task was not started: its workspace must remain "
                "inside the ORBIT workspace."
            )
    except OSError as exc:
        return f"Could not prepare the Python task workspace: {exc}"

    try:
        with tempfile.TemporaryDirectory(prefix="orbit-python-task-") as temp_dir:
            venv_path = Path(temp_dir) / "venv"
            environment = _task_environment(temp_dir, venv_path)

            setup_code, setup_output, setup_timed_out = await _execute(
                [sys.executable, "-m", "venv", str(venv_path)],
                timeout=60,
                environment=environment,
            )
            if setup_timed_out:
                return "Python task environment setup timed out."
            if setup_code != 0:
                return (
                    "Python task environment setup failed"
                    + (f" (exit code: {setup_code})" if setup_code is not None else "")
                    + f":\n{setup_output}"
                )

            return_code, output, timed_out = await _execute(
                [str(_python_in_venv(venv_path)), "-c", args.code],
                timeout=args.timeout,
                cwd=task_workspace,
                environment=_task_environment(temp_dir, venv_path),
            )
    except OSError as exc:
        return f"Could not run the Python task: {type(exc).__name__}: {exc}"

    if timed_out:
        result = f"Python task timed out after {args.timeout} seconds."
    elif return_code is None:
        result = f"Could not start the Python task: {output}"
    else:
        result = f"Exit code: {return_code}"

    result = f"Task working directory: {task_workspace}\n{result}"
    if output:
        result += f"\n{output}"
    return result
