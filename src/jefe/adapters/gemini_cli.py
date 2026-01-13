"""Gemini CLI harness adapter.

This adapter supports Google's Gemini CLI, which uses:
- Global config: ~/.gemini/
- Project config: .gemini/ and GEMINI.md files
- Settings: JSON format (settings.json)
- Instructions: Markdown format (GEMINI.md)
- Custom commands: TOML format in commands/ directory
- Skills: Experimental feature controlled via settings
"""

from __future__ import annotations

import json
import shutil
import tomllib
from pathlib import Path
from typing import cast

from jefe.adapters.base import DiscoveredConfig, HarnessAdapter
from jefe.data.models.harness_config import ConfigScope


class GeminiCliAdapter(HarnessAdapter):
    """Adapter for Google's Gemini CLI."""

    version: str = "0.1.0"

    @property
    def name(self) -> str:
        """Machine-friendly adapter name."""
        return "gemini_cli"

    @property
    def display_name(self) -> str:
        """Human-friendly adapter name."""
        return "Gemini CLI"

    def discover_global(self) -> list[DiscoveredConfig]:
        """Discover global configs for Gemini CLI.

        Searches ~/.gemini/ for:
        - settings.json (settings)
        - GEMINI.md (instructions)
        - commands/ directory (custom commands/skills)
        """
        discovered: list[DiscoveredConfig] = []
        gemini_home = Path.home() / ".gemini"

        if not gemini_home.exists():
            return discovered

        # Discover settings.json (settings)
        settings_json = gemini_home / "settings.json"
        if settings_json.is_file():
            discovered.append(
                DiscoveredConfig(
                    harness=self.name,
                    scope=ConfigScope.GLOBAL,
                    kind="settings",
                    path=settings_json,
                    content=self.parse_config(settings_json),
                )
            )

        # Discover GEMINI.md (instructions)
        gemini_md = gemini_home / "GEMINI.md"
        if gemini_md.is_file():
            discovered.append(
                DiscoveredConfig(
                    harness=self.name,
                    scope=ConfigScope.GLOBAL,
                    kind="instructions",
                    path=gemini_md,
                    content=self.parse_config(gemini_md),
                )
            )

        # Discover commands directory (skills)
        commands_dir = gemini_home / "commands"
        if commands_dir.is_dir():
            discovered.append(
                DiscoveredConfig(
                    harness=self.name,
                    scope=ConfigScope.GLOBAL,
                    kind="skills",
                    path=commands_dir,
                    content=None,
                )
            )

        return discovered

    def discover_project(
        self,
        project_path: Path,
        project_id: int | None = None,
        project_name: str | None = None,
    ) -> list[DiscoveredConfig]:
        """Discover project-level configs for Gemini CLI.

        Searches project_path for:
        - .gemini/ directory with config files
        - GEMINI.md at project root
        - .gemini/commands/ directory
        """
        discovered: list[DiscoveredConfig] = []
        project_path = project_path.expanduser()

        if not project_path.exists():
            return discovered

        # Discover .gemini/settings.json
        gemini_dir = project_path / ".gemini"
        if gemini_dir.is_dir():
            settings_json = gemini_dir / "settings.json"
            if settings_json.is_file():
                discovered.append(
                    DiscoveredConfig(
                        harness=self.name,
                        scope=ConfigScope.PROJECT,
                        kind="settings",
                        path=settings_json,
                        content=self.parse_config(settings_json),
                        project_id=project_id,
                        project_name=project_name,
                    )
                )

            # Discover .gemini/commands/
            commands_dir = gemini_dir / "commands"
            if commands_dir.is_dir():
                discovered.append(
                    DiscoveredConfig(
                        harness=self.name,
                        scope=ConfigScope.PROJECT,
                        kind="skills",
                        path=commands_dir,
                        content="",  # Directory listing
                        project_id=project_id,
                        project_name=project_name,
                    )
                )

        # Discover GEMINI.md at project root
        gemini_md = project_path / "GEMINI.md"
        if gemini_md.is_file():
            discovered.append(
                DiscoveredConfig(
                    harness=self.name,
                    scope=ConfigScope.PROJECT,
                    kind="instructions",
                    path=gemini_md,
                    content=self.parse_config(gemini_md),
                    project_id=project_id,
                    project_name=project_name,
                )
            )

        return discovered

    def parse_config(self, path: Path) -> dict[str, object] | str:
        """Parse a config file into structured data.

        For .json files, attempts to parse as JSON (falls back to plain text).
        For .toml files, attempts to parse as TOML (falls back to plain text).
        For .md files, returns as plain text.
        """
        try:
            content = path.read_text()
        except Exception:
            return ""

        # Handle JSON files
        if path.suffix == ".json":
            try:
                return cast(dict[str, object], json.loads(content))
            except json.JSONDecodeError:
                # Fallback to raw text if JSON parsing fails
                return content

        # Handle TOML files (for custom commands)
        if path.suffix == ".toml":
            try:
                return cast(dict[str, object], tomllib.loads(content))
            except Exception:
                # Fallback to raw text if TOML parsing fails
                return content

        # Markdown and other files returned as plain text
        return content

    def get_skills_path(
        self, scope: ConfigScope, project_path: Path | None = None
    ) -> Path:
        """Return the skills install path for a scope.

        For GLOBAL scope: ~/.gemini/commands
        For PROJECT scope: <project_path>/.gemini/commands
        """
        if scope == ConfigScope.GLOBAL:
            return Path.home() / ".gemini" / "commands"

        if project_path is None:
            raise ValueError("project_path required for PROJECT scope")

        return project_path.expanduser() / ".gemini" / "commands"

    def install_skill(
        self, skill: Path, scope: ConfigScope, project_path: Path | None = None
    ) -> Path:
        """Install a skill into the Gemini CLI scope.

        Creates the commands directory if needed, then copies the skill
        (either a directory or single file) to the destination.

        Returns the installed path.
        """
        destination_base = self.get_skills_path(scope, project_path)
        destination_base.mkdir(parents=True, exist_ok=True)

        skill_name = skill.name
        destination = destination_base / skill_name

        # Remove existing installation if present
        if destination.exists():
            if destination.is_dir():
                shutil.rmtree(destination)
            else:
                destination.unlink()

        # Copy skill to destination
        if skill.is_dir():
            shutil.copytree(skill, destination)
        else:
            shutil.copy2(skill, destination)

        return destination

    def uninstall_skill(self, installed_path: Path) -> bool:
        """Uninstall a skill by removing its files.

        Returns True if successful, False if path doesn't exist.
        """
        if not installed_path.exists():
            return False

        if installed_path.is_dir():
            shutil.rmtree(installed_path)
        else:
            installed_path.unlink()

        return True
