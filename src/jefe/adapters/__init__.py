"""Adapters module - Integration adapters and connectors."""

from jefe.adapters.base import DiscoveredConfig, HarnessAdapter
from jefe.adapters.claude_code import ClaudeCodeAdapter

_ADAPTERS: list[HarnessAdapter] = [
    ClaudeCodeAdapter(),
]


def get_adapters() -> list[HarnessAdapter]:
    """Return registered harness adapters."""
    return list(_ADAPTERS)


def get_adapter(name: str) -> HarnessAdapter | None:
    """Get a harness adapter by name."""
    for adapter in _ADAPTERS:
        if adapter.name == name:
            return adapter
    return None


__all__ = ["DiscoveredConfig", "HarnessAdapter", "get_adapter", "get_adapters"]
