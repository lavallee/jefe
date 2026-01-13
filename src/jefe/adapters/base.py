"""Base classes for harness adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

ConfigScope = Literal["global", "project"]
ConfigKind = Literal["settings", "instructions", "skills"]


@dataclass(frozen=True)
class DiscoveredConfig:
    """Config discovered for a harness."""

    harness: str
    scope: ConfigScope
    kind: ConfigKind
    path: Path
    content: dict[str, object] | str | None
    project_id: int | None = None
    project_name: str | None = None


class HarnessAdapter(ABC):
    """Base class for harness adapters."""

    name: str
    display_name: str
    version: str = "0.1.0"

    @abstractmethod
    def discover_global(self) -> list[DiscoveredConfig]:
        """Discover global configs for the harness."""

    @abstractmethod
    def discover_project(
        self, project_path: Path, project_id: int | None = None, project_name: str | None = None
    ) -> list[DiscoveredConfig]:
        """Discover project-level configs for the harness."""
