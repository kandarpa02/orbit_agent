from __future__ import annotations

import asyncio
import os
import shutil
import stat
import uuid

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field
from agents import FunctionTool


# ============================================================
# CONFIGURATION
# ============================================================

WORKSPACE = Path(
    os.getenv("ORBIT_WORKSPACE", ".cache/orbit/workspace")
).expanduser().resolve()

WORKSPACE.mkdir(parents=True, exist_ok=True)

READ_ONLY_ROOTS = tuple(
    Path(raw_path).expanduser().resolve()
    for raw_path in os.getenv("ORBIT_READONLY_PATHS", "").split(os.pathsep)
    if raw_path.strip()
)

MAX_FILE_SIZE = 2 * 1024 * 1024
MAX_OUTPUT_SIZE = 20_000
SKIP_DIRECTORY_NAMES = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
}


# ============================================================
# COMMAND ALLOWLIST
# ============================================================

ALLOWED_COMMANDS = {
    # Python
    "python",
    "python3",
    "python3.12",
    "pytest",
    "ruff",
    "mypy",
    "pyright",
    "black",
    "isort",
    "uv",
    "pip",
    "pip3",
    "poetry",
    "pdm",
    "hatch",

    # Version control
    "git",

    # JavaScript / TypeScript
    "node",
    "npm",
    "npx",
    "pnpm",
    "yarn",
    "bun",
    "tsc",
    "tsx",
    "vite",
    "next",

    # Build tools
    "make",
    "cmake",
    "cargo",
    "rustc",
    "go",
    "javac",
    "java",

    # Shell utilities
    "ls",
    "dir",
    "pwd",
    "cd",
    "cat",
    "type",
    "echo",
    "head",
    "tail",
    "grep",
    "find",
    "which",
    "where",
    "tree",
    "mkdir",
    "touch",
    "cp",
    "mv",
    "rm",
    "rmdir",
    "del",
    "copy",
    "move",

    # System utilities
    "whoami",
    "hostname",
    "uname",
    "where.exe",
    "tasklist",

    # API / networking
    "curl",
    "wget",

    # Containers
    "docker",
    "docker-compose",

    # Database clients
    "sqlite3",
    "psql",
    "redis-cli",

    # Documentation
    "mkdocs",
    "sphinx-build",
}


# ============================================================
# PATH / PERMISSION HELPERS
# ============================================================

def is_inside(path: Path, root: Path) -> bool:
    """Return True when path is root or a descendant of root."""
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def readable_roots() -> tuple[Path, ...]:
    """Roots available to read/search tools."""
    # De-duplicate while preserving order.
    roots: list[Path] = []
    for root in (WORKSPACE, *READ_ONLY_ROOTS):
        resolved = root.resolve()
        if resolved not in roots:
            roots.append(resolved)
    return tuple(roots)


def resolve_path(path: str, operation: Literal["read", "write"]) -> Path:
    """
    Resolve and authorize a path.

    Read:
        WORKSPACE and explicitly configured READ_ONLY_ROOTS.

    Write:
        WORKSPACE only.

    Resolving symlinks before checking containment helps prevent a
    symlink inside an allowed directory from pointing outside it.
    """
    if not path or not path.strip():
        raise ValueError("Path cannot be empty.")

    candidate = Path(path).expanduser()

    if not candidate.is_absolute():
        candidate = WORKSPACE / candidate

    resolved = candidate.resolve()

    if operation == "read":
        allowed_roots = readable_roots()
    elif operation == "write":
        allowed_roots = (WORKSPACE.resolve(),)
    else:
        raise ValueError(f"Unsupported filesystem operation: {operation}")

    if not any(is_inside(resolved, root) for root in allowed_roots):
        if operation == "write":
            raise PermissionError(
                "Write access denied. ORBIT can only modify files inside "
                f"its workspace: {WORKSPACE}"
            )
        raise PermissionError(
            "Read access denied. The path is outside the workspace and "
            "configured read-only roots."
        )

    return resolved


def relative_display_path(path: Path) -> str:
    """Format a path relative to its matching allowed root."""
    resolved = path.resolve()

    for root in readable_roots():
        if is_inside(resolved, root):
            try:
                relative = resolved.relative_to(root)
                return f"{root.name or str(root)} / {relative}"
            except ValueError:
                pass

    return str(resolved)


def should_skip_path(path: Path) -> bool:
    return any(part.lower() in SKIP_DIRECTORY_NAMES for part in path.parts)


# ============================================================
# FILESYSTEM ARGUMENT SCHEMAS
# ============================================================

class ReadFileArgs(BaseModel):
    path: str


class WriteFileArgs(BaseModel):
    path: str
    content: str


class DeleteFileArgs(BaseModel):
    path: str


class DeleteDirectoryArgs(BaseModel):
    path: str


class SearchFilesArgs(BaseModel):
    query: str
    pattern: str = "**/*"
    max_results: int = Field(default=50, ge=1, le=200)


class PatchFileArgs(BaseModel):
    path: str
    old_text: str
    new_text: str


class ListDirectoryArgs(BaseModel):
    path: str = "."


# ============================================================
# FILESYSTEM HANDLERS
# ============================================================

async def read_file(args: ReadFileArgs) -> str:
    path = resolve_path(args.path, operation="read")

    if not path.is_file():
        return f"File not found: {args.path}"

    if path.stat().st_size > MAX_FILE_SIZE:
        return f"File exceeds the {MAX_FILE_SIZE // (1024 * 1024)} MB reading limit."

    try:
        return await asyncio.to_thread(
            path.read_text,
            encoding="utf-8",
        )
    except UnicodeDecodeError:
        return "File is not valid UTF-8 text and cannot be displayed."
    except OSError as exc:
        return f"Could not read file: {exc}"


async def write_file(args: WriteFileArgs) -> str:
    path = resolve_path(args.path, operation="write")

    path.parent.mkdir(parents=True, exist_ok=True)

    await asyncio.to_thread(
        path.write_text,
        args.content,
        encoding="utf-8",
    )

    return f"Successfully wrote {path.relative_to(WORKSPACE)}"


async def delete_file(args: DeleteFileArgs) -> str:
    path = resolve_path(args.path, operation="write")
    candidate = Path(args.path).expanduser()
    if not candidate.is_absolute():
        candidate = WORKSPACE / candidate

    if not candidate.exists() and not candidate.is_symlink():
        return (
            f"File not found: {args.path}. Check the exact filename with "
            "list_directory, then retry delete_file; do not use "
            "execute_command for deletion."
        )

    if candidate.is_dir():
        return "Cannot delete a directory with delete_file."

    try:
        await asyncio.to_thread(candidate.unlink)
    except OSError as exc:
        return f"Could not delete file: {exc}"

    return f"Deleted file: {path}"


def _retry_readonly_delete(function, path, exc_info) -> None:
    error = exc_info[1]
    if os.name != "nt" or not isinstance(error, PermissionError):
        raise error

    try:
        os.chmod(path, stat.S_IWRITE)
        function(path)
    except OSError:
        raise error


async def delete_directory(args: DeleteDirectoryArgs) -> str:
    candidate = Path(args.path).expanduser()
    if not candidate.is_absolute():
        candidate = WORKSPACE / candidate

    if candidate.is_symlink():
        return "Refusing to recursively delete a symbolic link."

    path = resolve_path(args.path, operation="write")
    if path == WORKSPACE.resolve():
        return "Refusing to delete the ORBIT workspace root."

    if not candidate.exists():
        return f"Directory not found: {args.path}"

    if not candidate.is_dir():
        return f"Not a directory: {args.path}"

    try:
        await asyncio.to_thread(
            shutil.rmtree,
            candidate,
            onerror=_retry_readonly_delete,
        )
    except PermissionError as exc:
        blocked_path = exc.filename or str(path)
        return (
            f"Access denied while deleting {blocked_path}. The directory may "
            "be partially deleted; a file may still be open or otherwise "
            "locked. Close programs using it, then retry delete_directory."
        )
    except OSError as exc:
        return f"Could not delete directory (it may be partially deleted): {exc}"

    return f"Deleted directory and its contents: {path}"


async def search_files(args: SearchFilesArgs) -> str:
    """
    Search file contents in the workspace and configured read-only roots.
    Search never writes to any searched directory.
    """
    results: list[str] = []
    query = args.query.casefold()

    for root in readable_roots():
        if not root.exists() or not root.is_dir():
            continue

        for path in root.glob(args.pattern):
            if len(results) >= args.max_results:
                break

            if should_skip_path(path) or not path.is_file():
                continue

            try:
                if path.stat().st_size > MAX_FILE_SIZE:
                    continue

                content = await asyncio.to_thread(
                    path.read_text,
                    encoding="utf-8",
                )

                if query in content.casefold():
                    results.append(relative_display_path(path))

            except (UnicodeDecodeError, OSError, PermissionError):
                continue

        if len(results) >= args.max_results:
            break

    if not results:
        return "No matching files found in the workspace or configured read-only roots."

    return "\n".join(results)


async def list_directory(args: ListDirectoryArgs) -> str:
    path = resolve_path(args.path, operation="read")

    if not path.exists():
        return f"Directory not found: {args.path}"

    if not path.is_dir():
        return f"Not a directory: {args.path}"

    try:
        entries = await asyncio.to_thread(lambda: sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.lower())))
    except OSError as exc:
        return f"Could not list directory: {exc}"

    lines: list[str] = []
    for entry in entries:
        if entry.name.lower() in SKIP_DIRECTORY_NAMES:
            continue

        kind = "[DIR] " if entry.is_dir() else "[FILE]"
        lines.append(f"{kind} {entry.name}")

    return "\n".join(lines) if lines else "Directory is empty."


async def patch_file(args: PatchFileArgs) -> str:
    # Patching is a write operation and is therefore workspace-only.
    path = resolve_path(args.path, operation="write")

    if not path.is_file():
        return "File not found."

    if path.stat().st_size > MAX_FILE_SIZE:
        return f"File exceeds the {MAX_FILE_SIZE // (1024 * 1024)} MB patching limit."

    try:
        content = await asyncio.to_thread(
            path.read_text,
            encoding="utf-8",
        )
    except (UnicodeDecodeError, OSError) as exc:
        return f"Could not read file for patching: {exc}"

    occurrences = content.count(args.old_text)

    if occurrences == 0:
        return "Target text was not found."

    if occurrences > 1:
        return (
            f"Found {occurrences} occurrences. "
            "Provide a more specific old_text."
        )

    updated = content.replace(args.old_text, args.new_text, 1)

    await asyncio.to_thread(
        path.write_text,
        updated,
        encoding="utf-8",
    )

    return "File patched successfully."


# ============================================================
# TERMINAL
# ============================================================

def validate_command(command: list[str]) -> None:
    if not command:
        raise ValueError("Command cannot be empty.")

    executable = Path(command[0]).name.lower()

    if executable.endswith(".exe"):
        executable = executable[:-4]

    if executable not in ALLOWED_COMMANDS:
        raise PermissionError(
            f"Command '{executable}' is not allowed."
        )


def trim_output(output: str) -> str:
    if len(output) > MAX_OUTPUT_SIZE:
        return (
            output[-MAX_OUTPUT_SIZE:]
            + "\n[Output truncated]"
        )

    return output


class ExecuteCommandArgs(BaseModel):
    command: list[str]
    timeout: int = Field(default=30, ge=1, le=300)


async def execute_command(args: ExecuteCommandArgs) -> str:
    validate_command(args.command)

    # NOTE:
    # cwd limits the command's starting directory only. It does NOT
    # sandbox the process. For example, Python, Node, Git, npm, curl,
    # and many other allowed programs can access or modify paths outside
    # WORKSPACE. Use OS-level sandboxing / a restricted helper process
    # before treating external system paths as technically read-only.
    process = await asyncio.create_subprocess_exec(
        *args.command,
        cwd=WORKSPACE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )

    try:
        output, _ = await asyncio.wait_for(
            process.communicate(),
            timeout=args.timeout,
        )

    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        return "Command timed out and was terminated."

    result = output.decode(
        "utf-8",
        errors="replace",
    )

    return (
        f"Exit code: {process.returncode}\n"
        f"{trim_output(result)}"
    )


# ============================================================
# BACKGROUND PROCESS MANAGEMENT
# ============================================================

@dataclass
class ManagedProcess:
    process: asyncio.subprocess.Process
    output: str = ""
    reader: asyncio.Task | None = None


class ProcessManager:

    def __init__(self):
        self.processes: dict[str, ManagedProcess] = {}

    async def _capture(
        self,
        process_id: str,
        process: asyncio.subprocess.Process,
    ):
        entry = self.processes[process_id]

        while True:
            line = await process.stdout.readline()

            if not line:
                break

            entry.output += line.decode(
                "utf-8",
                errors="replace",
            )

            entry.output = trim_output(entry.output)

    async def start(self, command: list[str]) -> str:
        validate_command(command)

        # Same security caveat as execute_command: cwd is not a sandbox.
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=WORKSPACE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

        process_id = uuid.uuid4().hex[:12]

        entry = ManagedProcess(process=process)

        self.processes[process_id] = entry

        entry.reader = asyncio.create_task(
            self._capture(process_id, process)
        )

        return process_id

    async def status(self, process_id: str) -> str:
        entry = self.processes.get(process_id)

        if not entry:
            return "Process not found."

        process = entry.process

        state = (
            "running"
            if process.returncode is None
            else f"exited with code {process.returncode}"
        )

        return (
            f"Process ID: {process_id}\n"
            f"Status: {state}\n"
            f"Output:\n{entry.output}"
        )

    async def stop(self, process_id: str) -> str:
        entry = self.processes.get(process_id)

        if not entry:
            return "Process not found."

        process = entry.process

        if process.returncode is not None:
            return "Process has already exited."

        process.terminate()

        try:
            await asyncio.wait_for(
                process.wait(),
                timeout=3,
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()

        return f"Process {process_id} terminated."


process_manager = ProcessManager()


class ProcessManageArgs(BaseModel):
    action: Literal["start", "status", "stop"]
    command: list[str] | None = None
    process_id: str | None = None


async def process_manage(args: ProcessManageArgs) -> str:
    if args.action == "start":
        if not args.command:
            return "A command is required to start a process."

        process_id = await process_manager.start(args.command)

        return f"Process started. ID: {process_id}"

    if not args.process_id:
        return "A process_id is required."

    if args.action == "status":
        return await process_manager.status(args.process_id)

    if args.action == "stop":
        return await process_manager.stop(args.process_id)

    return "Unsupported action."
