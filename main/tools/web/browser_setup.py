
import asyncio
import sys
from pathlib import Path
from playwright.async_api import Playwright


_install_lock = asyncio.Lock()


async def ensure_chromium(playwright: Playwright) -> None:
    """Install Chromium automatically if it is not already installed."""

    executable = Path(playwright.chromium.executable_path)

    if executable.is_file():
        return

    async with _install_lock:
        # Another browser initialization may have installed it already.
        if executable.is_file():
            return

        print("ORBIT: Chromium not found. Installing...")

        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "python",
            "-m",
            "playwright",
            "install",
            "chromium",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

        output, _ = await process.communicate()

        if process.returncode != 0:
            raise RuntimeError(
                "Chromium installation failed:\n"
                + output.decode(errors="replace")
            )

        if not executable.is_file():
            raise RuntimeError(
                "Chromium installation completed, "
                "but the browser executable was not found."
            )

        print("ORBIT: Chromium installed successfully.")
