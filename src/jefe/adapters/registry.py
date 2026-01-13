"""Harness adapter registry."""

from __future__ import annotations

import contextlib
import importlib
import pkgutil
from pathlib import Path

from jefe.adapters.base import HarnessAdapter

_ADAPTERS: dict[str, HarnessAdapter] = {}
_AUTO_DISCOVERED = False


def register_adapter(adapter: HarnessAdapter) -> None:
    """Register a harness adapter."""
    _ADAPTERS[adapter.name] = adapter


def get_adapter(name: str) -> HarnessAdapter | None:
    """Return a harness adapter by name."""
    _ensure_auto_discovery()
    return _ADAPTERS.get(name)


def list_adapters() -> list[HarnessAdapter]:
    """List registered harness adapters."""
    _ensure_auto_discovery()
    return list(_ADAPTERS.values())


def _ensure_auto_discovery() -> None:
    """Ensure adapters have been auto-discovered."""
    global _AUTO_DISCOVERED
    if not _AUTO_DISCOVERED:
        _auto_discover_adapters()
        _AUTO_DISCOVERED = True


def _auto_discover_adapters() -> None:
    """Auto-discover and register all adapter modules in the adapters package."""
    # Get the adapters package directory
    adapters_dir = Path(__file__).parent

    # Import all Python modules in the adapters package
    for module_info in pkgutil.iter_modules([str(adapters_dir)]):
        module_name = module_info.name

        # Skip base, registry, and __init__ modules
        if module_name in ("base", "registry", "__init__"):
            continue

        # Import the module to trigger adapter instantiation
        with contextlib.suppress(Exception):
            importlib.import_module(f"jefe.adapters.{module_name}")
