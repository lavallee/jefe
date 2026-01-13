"""Async HTTP client helpers for the CLI."""

from __future__ import annotations

import httpx

from jefe.cli.config import get_config_value


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
