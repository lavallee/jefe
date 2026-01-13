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

    version: str = "0.1.0"

    @property
    @abstractmethod
    def name(self) -> str:
        """Machine-friendly adapter name."""

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-friendly adapter name."""

    @abstractmethod
    def discover_global(self) -> list[DiscoveredConfig]:
        """Discover global configs for the harness."""

    @abstractmethod
    def discover_project(
        self, project_path: Path, project_id: int | None = None, project_name: str | None = None
    ) -> list[DiscoveredConfig]:
        """Discover project-level configs for the harness."""

    @abstractmethod
    def parse_config(self, path: Path) -> dict[str, object] | str:
        """Parse a config file into structured data."""

    @abstractmethod
    def get_skills_path(self, scope: ConfigScope, project_path: Path | None = None) -> Path:
        """Return the skills install path for a scope."""

    @abstractmethod
    def install_skill(
        self, skill: Path, scope: ConfigScope, project_path: Path | None = None
    ) -> Path:
        """Install a skill into the harness scope and return the installed path."""
