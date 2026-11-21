from __future__ import annotations

import asyncio
from time import time_ns
from typing import Any

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from .security import validate_public_url
from .browser_setup import ensure_chromium


class BrowserSession:
    """One persistent browser context shared by ORBIT browser tool calls."""

    def __init__(self) -> None:
        self._playwright: Any = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._lock = asyncio.Lock()


    async def _guard_request(self, route) -> None:
        try:
            await validate_public_url(route.request.url)
        except Exception:
            await route.abort("blockedbyclient")
            return
        await route.continue_()

    
    async def _ensure_page(self) -> Page:
        if self._page and not self._page.is_closed():
            return self._page

        if self._playwright is None:
            self._playwright = await async_playwright().start()

        if self._browser is None or not self._browser.is_connected():
            await ensure_chromium(self._playwright)

            self._browser = await self._playwright.chromium.launch(
                headless=True
            )

            self._context = await self._browser.new_context(
                viewport={"width": 1440, "height": 900},
                accept_downloads=False,
            )

            self._context.set_default_timeout(10_000)
            self._context.set_default_navigation_timeout(30_000)

            await self._context.route(
                "**/*",
                self._guard_request
            )

        if self._context is None:
            self._context = await self._browser.new_context()

        self._page = await self._context.new_page()

        return self._page


    async def run(self, args) -> str:
        async with self._lock:
            if args.action == "navigate":
                await validate_public_url(args.url)

            page = await self._ensure_page()
            try:
                if args.action == "navigate":
                    response = await page.goto(args.url, wait_until="domcontentloaded")
                    status = response.status if response else "unknown"
                    return f"Navigated to {page.url}\nHTTP status: {status}\nTitle: {await page.title()}"

                if args.action == "snapshot":
                    if page.url == "about:blank":
                        return "No page is open. Use browser navigate first."
                    title = await page.title()
                    text = await page.locator("body").inner_text(timeout=10_000)
                    text = text[:18_000] + ("\n[Snapshot truncated]" if len(text) > 18_000 else "")
                    return f"Title: {title}\nURL: {page.url}\n\n{text}"

                if args.action == "click":
                    await page.locator(args.selector).first.click()
                    return f"Clicked: {args.selector}\nCurrent URL: {page.url}"

                if args.action == "type":
                    await page.locator(args.selector).first.fill(args.text)
                    return f"Entered text into: {args.selector}"

                if args.action == "screenshot":
                    # Import lazily to avoid a cycle: system.py imports this module.
                    from ..system import WORKSPACE

                    screenshot_dir = WORKSPACE / "browser_screenshots"
                    screenshot_dir.mkdir(parents=True, exist_ok=True)
                    filename = f"orbit-{time_ns()}.png"
                    path = screenshot_dir / filename
                    await page.screenshot(path=str(path), full_page=True)
                    return f"Screenshot saved: {path}"

                if args.action == "execute":
                    result = await page.evaluate(args.script)
                    rendered = repr(result)
                    if len(rendered) > 12_000:
                        rendered = rendered[:12_000] + " [result truncated]"
                    return f"Browser JavaScript result:\n{rendered}"

                return f"Unsupported browser action: {args.action}"
            except Exception as exc:
                return f"Browser error: {type(exc).__name__}: {exc}"


browser_session = BrowserSession()


async def browser_action(args) -> str:
    return await browser_session.run(args)
