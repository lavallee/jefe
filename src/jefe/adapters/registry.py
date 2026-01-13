"""Harness adapter registry."""

from __future__ import annotations

from jefe.adapters.base import HarnessAdapter

_ADAPTERS: dict[str, HarnessAdapter] = {}


def register_adapter(adapter: HarnessAdapter) -> None:
    """Register a harness adapter."""
    _ADAPTERS[adapter.name] = adapter


def get_adapter(name: str) -> HarnessAdapter | None:
    """Return a harness adapter by name."""
    return _ADAPTERS.get(name)


def list_adapters() -> list[HarnessAdapter]:
    """List registered harness adapters."""
    return list(_ADAPTERS.values())
