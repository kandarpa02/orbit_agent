
from __future__ import annotations

import asyncio
import json
import os
import shlex
import uuid

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field
from agents import FunctionTool


# ============================================================
# CONFIGURATION
# ============================================================

WORKSPACE = Path(
    os.getenv("ORBIT_WORKSPACE", "./workspace")
).resolve()

WORKSPACE.mkdir(parents=True, exist_ok=True)

MAX_FILE_SIZE = 2 * 1024 * 1024
MAX_OUTPUT_SIZE = 20_000

ALLOWED_COMMANDS = {
    "python",
    "python3",
    "pytest",
    "ruff",
    "git",
    "uv",
    "pip",
    "npm",
    "node",
}

# ============================================================
# FILESYSTEM
# ============================================================

def resolve_path(path: str) -> Path:
    """Resolve a path and prevent access outside the workspace."""

    candidate = Path(path)

    if not candidate.is_absolute():
        candidate = WORKSPACE / candidate

    resolved = candidate.resolve()

    try:
        resolved.relative_to(WORKSPACE)
    except ValueError:
        raise PermissionError("Access outside ORBIT workspace denied.")

    return resolved


class ReadFileArgs(BaseModel):
    path: str


class WriteFileArgs(BaseModel):
    path: str
    content: str


class SearchFilesArgs(BaseModel):
    query: str
    pattern: str = "**/*"
    max_results: int = Field(default=50, ge=1, le=200)


class PatchFileArgs(BaseModel):
    path: str
    old_text: str
    new_text: str


async def read_file(args: ReadFileArgs) -> str:
    path = resolve_path(args.path)

    if not path.is_file():
        return f"File not found: {args.path}"

    if path.stat().st_size > MAX_FILE_SIZE:
        return "File exceeds the 2 MB reading limit."

    return await asyncio.to_thread(
        path.read_text,
        encoding="utf-8",
    )


async def write_file(args: WriteFileArgs) -> str:
    path = resolve_path(args.path)

    path.parent.mkdir(parents=True, exist_ok=True)

    await asyncio.to_thread(
        path.write_text,
        args.content,
        encoding="utf-8",
    )

    return f"Successfully wrote {path.relative_to(WORKSPACE)}"


async def search_files(args: SearchFilesArgs) -> str:
    results = []

    for path in WORKSPACE.glob(args.pattern):
        if not path.is_file():
            continue

        if len(results) >= args.max_results:
            break

        try:
            if path.stat().st_size > MAX_FILE_SIZE:
                continue

            content = await asyncio.to_thread(
                path.read_text,
                encoding="utf-8",
            )

            if args.query.lower() in content.lower():
                results.append(
                    str(path.relative_to(WORKSPACE))
                )

        except (UnicodeDecodeError, OSError):
            continue

    if not results:
        return "No matching files found."

    return "\n".join(results)


async def patch_file(args: PatchFileArgs) -> str:
    path = resolve_path(args.path)

    if not path.is_file():
        return "File not found."

    if path.stat().st_size > MAX_FILE_SIZE:
        return "File exceeds the 2 MB patching limit."

    content = await asyncio.to_thread(
        path.read_text,
        encoding="utf-8",
    )

    occurrences = content.count(args.old_text)

    if occurrences == 0:
        return "Target text was not found."

    if occurrences > 1:
        return (
            f"Found {occurrences} occurrences. "
            "Provide a more specific old_text."
        )

    updated = content.replace(
        args.old_text,
        args.new_text,
        1,
    )

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

        process_id = await process_manager.start(
            args.command
        )

        return f"Process started. ID: {process_id}"

    if not args.process_id:
        return "A process_id is required."

    if args.action == "status":
        return await process_manager.status(args.process_id)

    if args.action == "stop":
        return await process_manager.stop(args.process_id)

    return "Unsupported action."


# ============================================================
# FUNCTION TOOL FACTORY
# ============================================================

def create_tool(
    name: str,
    description: str,
    schema: type[BaseModel],
    handler,
) -> FunctionTool:

    async def invoke(ctx: Any, raw_arguments: str) -> str:
        try:
            args = schema.model_validate_json(raw_arguments)
            return await handler(args)

        except Exception as exc:
            return f"Tool error: {type(exc).__name__}: {exc}"

    return FunctionTool(
        name=name,
        description=description,
        params_json_schema=schema.model_json_schema(),
        on_invoke_tool=invoke,
        strict_json_schema=False,
    )


# ============================================================
# ORBIT TOOL REGISTRY
# ============================================================

def get_system_tools() -> list[FunctionTool]:

    return [
        create_tool(
            "read_file",
            "Read a text file inside the ORBIT workspace.",
            ReadFileArgs,
            read_file,
        ),

        create_tool(
            "write_file",
            "Create or overwrite a file inside the ORBIT workspace.",
            WriteFileArgs,
            write_file,
        ),

        create_tool(
            "search_files",
            "Search file contents inside the ORBIT workspace.",
            SearchFilesArgs,
            search_files,
        ),

        create_tool(
            "patch_file",
            "Replace one exact occurrence of text in a workspace file.",
            PatchFileArgs,
            patch_file,
        ),

        create_tool(
            "execute_command",
            "Execute an allowed command in the ORBIT workspace.",
            ExecuteCommandArgs,
            execute_command,
        ),

        create_tool(
            "process_manage",
            "Start, inspect or terminate background processes.",
            ProcessManageArgs,
            process_manage,
        ),
    ]
