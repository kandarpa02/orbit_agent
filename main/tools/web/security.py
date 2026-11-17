from __future__ import annotations

import asyncio
import ipaddress
import socket
from urllib.parse import urlsplit


async def validate_public_url(url: str) -> str:
    """Allow public HTTP(S) URLs only; reject local/private network targets."""
    try:
        parsed = urlsplit(url)
        scheme = parsed.scheme.lower()
        host = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise ValueError(f"Invalid URL: {exc}") from exc

    if scheme not in {"http", "https"}:
        raise ValueError("Only http:// and https:// URLs are supported")
    if not host or parsed.username or parsed.password:
        raise ValueError("URL must have a hostname and must not contain credentials")

    normalized_host = host.rstrip(".").lower()
    if normalized_host in {"localhost", "localhost.localdomain"} or normalized_host.endswith((".local", ".internal", ".test")):
        raise PermissionError("Requests to local or internal hostnames are blocked")

    try:
        addresses = [ipaddress.ip_address(normalized_host)]
    except ValueError:
        try:
            records = await asyncio.to_thread(
                socket.getaddrinfo,
                normalized_host,
                port or (443 if scheme == "https" else 80),
                type=socket.SOCK_STREAM,
            )
        except OSError as exc:
            raise ValueError(f"Could not resolve hostname: {normalized_host}") from exc
        addresses = [ipaddress.ip_address(record[4][0]) for record in records]

    if not addresses or any(
        address.is_private or address.is_loopback or address.is_link_local
        or address.is_reserved or address.is_multicast or address.is_unspecified
        for address in addresses
    ):
        raise PermissionError("Requests to private, local, or reserved IP addresses are blocked")

    return url
