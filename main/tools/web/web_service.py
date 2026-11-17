from __future__ import annotations

import asyncio
from typing import Any

import httpx
from bs4 import BeautifulSoup
from ddgs import DDGS

from .security import validate_public_url


async def search_web(query: str, limit: int = 5) -> str:
    """Search the web through the DDGS metasearch client."""
    def run_search() -> list[dict[str, Any]]:
        return list(DDGS().text(query, max_results=limit))

    try:
        results = await asyncio.to_thread(run_search)
    except Exception as exc:
        return f"Web search failed: {type(exc).__name__}: {exc}"

    if not results:
        return "No search results found."

    output: list[str] = []
    for index, result in enumerate(results[:limit], start=1):
        title = str(result.get("title") or "Untitled").strip()
        url = str(result.get("href") or result.get("url") or "").strip()
        snippet = str(result.get("body") or result.get("snippet") or "").strip()
        output.append(f"{index}. {title}\nURL: {url}\n{snippet}")
    return "\n\n".join(output)


async def fetch_webpage(url: str) -> str:
    """Fetch and extract readable text from one public webpage."""
    try:
        await validate_public_url(url)
        timeout = httpx.Timeout(20.0, connect=8.0)
        headers = {"User-Agent": "ORBIT/1.0 (+web research tool)"}
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=False,
            headers=headers,
        ) as client:
            response = await client.get(url)

        if 300 <= response.status_code < 400:
            location = response.headers.get("location", "")
            return (
                f"The page redirected (HTTP {response.status_code}). "
                "Automatic redirects are disabled for safety. "
                f"Redirect target: {location or '[not provided]'}"
            )
        response.raise_for_status()

        content_type = response.headers.get("content-type", "").lower()
        if "html" not in content_type and "text/plain" not in content_type:
            return f"Unsupported content type: {content_type or 'unknown'}"

        soup = BeautifulSoup(response.text, "html.parser")
        for element in soup(["script", "style", "noscript", "svg", "nav", "footer"]):
            element.decompose()
        title = soup.title.get_text(" ", strip=True) if soup.title else "Untitled page"
        main = soup.find("main") or soup.find("article") or soup.body or soup
        body = "\n".join(
            line.strip() for line in main.get_text("\n").splitlines() if line.strip()
        )
        if len(body) > 18_000:
            body = body[:18_000] + "\n[Page text truncated]"
        return f"Title: {title}\nURL: {response.url}\n\n{body or '[No readable text found]'}"
    except Exception as exc:
        return f"Web fetch failed: {type(exc).__name__}: {exc}"
