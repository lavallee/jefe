"""Async HTTP client helpers for the CLI."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx

from jefe.cli.config import get_config_value

# Cache for online status
_online_status_cache: tuple[bool, datetime] | None = None
_online_cache_ttl = timedelta(seconds=30)


def get_server_url() -> str:
    """Return the configured server URL."""
    return str(get_config_value("server_url", "http://localhost:8000"))


def get_api_key() -> str | None:
    """Return the configured API key, if any."""
    api_key = get_config_value("api_key")
    if api_key is None:
        return None
    return str(api_key)


def create_client() -> httpx.AsyncClient:
    """Create an async HTTP client with configured base URL and headers."""
    headers: dict[str, str] = {}
    api_key = get_api_key()
    if api_key:
        headers["X-API-Key"] = api_key

    return httpx.AsyncClient(base_url=get_server_url(), headers=headers, timeout=10.0)


async def is_online() -> bool:
    """Check if the server is online and reachable.

    Uses a quick health check with a 2-second timeout.
    Caches the result for 30 seconds to avoid blocking the CLI.

    Returns:
        True if server is reachable, False otherwise
    """
    global _online_status_cache

    # Check if we have a cached result that's still valid
    if _online_status_cache is not None:
        cached_status, cached_at = _online_status_cache
        now = datetime.now(UTC)
        if now - cached_at < _online_cache_ttl:
            return cached_status

    # Perform health check with short timeout
    try:
        async with httpx.AsyncClient(
            base_url=get_server_url(), timeout=2.0
        ) as client:
            response = await client.get("/health")
            online = response.status_code == 200
    except (httpx.RequestError, httpx.TimeoutException):
        online = False

    # Cache the result
    _online_status_cache = (online, datetime.now(UTC))
    return online


def clear_online_cache() -> None:
    """Clear the online status cache.

    Useful for testing or when you want to force a fresh check.
    """
    global _online_status_cache
    _online_status_cache = None
