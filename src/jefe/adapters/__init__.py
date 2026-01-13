"""Adapters module - Integration adapters and connectors."""

from jefe.adapters.base import DiscoveredConfig, HarnessAdapter
from jefe.adapters.claude_code import ClaudeCodeAdapter
from jefe.adapters.codex_cli import CodexCliAdapter
from jefe.adapters.gemini_cli import GeminiCliAdapter
from jefe.adapters.registry import get_adapter, list_adapters, register_adapter

register_adapter(ClaudeCodeAdapter())
register_adapter(CodexCliAdapter())
register_adapter(GeminiCliAdapter())


def get_adapters() -> list[HarnessAdapter]:
    """Return registered harness adapters."""
    return list_adapters()


__all__ = [
    "DiscoveredConfig",
    "HarnessAdapter",
    "get_adapter",
    "get_adapters",
    "list_adapters",
    "register_adapter",
]
