"""Codex CLI harness adapter.

This adapter supports OpenAI's Codex CLI, which uses:
- Global config: ~/.codex/
- Project config: .codex/ and AGENTS.md files
- Skills: ~/.codex/skills (global), .codex/skills (project)
"""

from __future__ import annotations

import json
import shutil
import tomllib
from pathlib import Path
from typing import cast

from jefe.adapters.base import DiscoveredConfig, HarnessAdapter
from jefe.adapters.registry import register_adapter
from jefe.data.models.harness_config import ConfigScope


class CodexCliAdapter(HarnessAdapter):
    """Adapter for OpenAI Codex CLI."""

    version: str = "0.1.0"

    @property
    def name(self) -> str:
        """Machine-friendly adapter name."""
        return "codex_cli"

    @property
    def display_name(self) -> str:
        """Human-friendly adapter name."""
        return "Codex CLI"

    def discover_global(self) -> list[DiscoveredConfig]:
        """Discover global configs for Codex CLI.

        Searches ~/.codex/ for:
        - config.toml (settings)
        - AGENTS.md or AGENTS.override.md (instructions)
        - skills/ directory
        """
        discovered: list[DiscoveredConfig] = []
        codex_home = Path.home() / ".codex"

        if not codex_home.exists():
            return discovered

        # Discover config.toml (settings)
        config_toml = codex_home / "config.toml"
        if config_toml.is_file():
            discovered.append(
                DiscoveredConfig(
                    harness=self.name,
                    scope=ConfigScope.GLOBAL,
                    kind="settings",
                    path=config_toml,
                    content=self.parse_config(config_toml),
                )
            )

        # Discover AGENTS.md (instructions) - check override first
        agents_override = codex_home / "AGENTS.override.md"
        agents_md = codex_home / "AGENTS.md"

        if agents_override.is_file():
            discovered.append(
                DiscoveredConfig(
                    harness=self.name,
                    scope=ConfigScope.GLOBAL,
                    kind="instructions",
                    path=agents_override,
                    content=self.parse_config(agents_override),
                )
            )
        elif agents_md.is_file():
            discovered.append(
                DiscoveredConfig(
                    harness=self.name,
                    scope=ConfigScope.GLOBAL,
                    kind="instructions",
                    path=agents_md,
                    content=self.parse_config(agents_md),
                )
            )

        # Discover skills directory
        skills_dir = codex_home / "skills"
        if skills_dir.is_dir():
            discovered.append(
                DiscoveredConfig(
                    harness=self.name,
                    scope=ConfigScope.GLOBAL,
                    kind="skills",
                    path=skills_dir,
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
        """Discover project-level configs for Codex CLI.

        Searches project_path for:
        - .codex/ directory with config files
        - AGENTS.md or AGENTS.override.md at project root
        - .codex/skills/ directory
        """
        discovered: list[DiscoveredConfig] = []
        project_path = project_path.expanduser()

        if not project_path.exists():
            return discovered

        # Discover .codex/config.toml
        codex_dir = project_path / ".codex"
        if codex_dir.is_dir():
            config_toml = codex_dir / "config.toml"
            if config_toml.is_file():
                discovered.append(
                    DiscoveredConfig(
                        harness=self.name,
                        scope=ConfigScope.PROJECT,
                        kind="settings",
                        path=config_toml,
                        content=self.parse_config(config_toml),
                        project_id=project_id,
                        project_name=project_name,
                        )
                )

            # Discover .codex/skills/
            skills_dir = codex_dir / "skills"
            if skills_dir.is_dir():
                discovered.append(
                    DiscoveredConfig(
                        harness=self.name,
                        scope=ConfigScope.PROJECT,
                        kind="skills",
                        path=skills_dir,
                        content="",  # Directory listing
                        project_id=project_id,
                        project_name=project_name,
                        )
                )

        # Discover AGENTS.md at project root - check override first
        agents_override = project_path / "AGENTS.override.md"
        agents_md = project_path / "AGENTS.md"

        if agents_override.is_file():
            discovered.append(
                DiscoveredConfig(
                    harness=self.name,
                    scope=ConfigScope.PROJECT,
                    kind="instructions",
                    path=agents_override,
                    content=self.parse_config(agents_override),
                    project_id=project_id,
                    project_name=project_name,
                )
            )
        elif agents_md.is_file():
            discovered.append(
                DiscoveredConfig(
                    harness=self.name,
                    scope=ConfigScope.PROJECT,
                    kind="instructions",
                    path=agents_md,
                    content=self.parse_config(agents_md),
                    project_id=project_id,
                    project_name=project_name,
                )
            )

        return discovered

    def parse_config(self, path: Path) -> dict[str, object] | str:
        """Parse a config file into structured data.

        For .toml files, attempts to parse as TOML (falls back to plain text).
        For .json files, attempts to parse as JSON (falls back to plain text).
        For .md files, returns as plain text.
        """
        try:
            content = path.read_text()
        except Exception:
            return ""

        # Handle TOML files
        if path.suffix == ".toml":
            try:
                return cast(dict[str, object], tomllib.loads(content))
            except Exception:
                # Fallback to raw text if TOML parsing fails
                return content

        # Handle JSON files
        if path.suffix == ".json":
            try:
                return cast(dict[str, object], json.loads(content))
            except json.JSONDecodeError:
                # Fallback to raw text if JSON parsing fails
                return content

        # Markdown and other files returned as plain text
        return content

    def get_skills_path(
        self, scope: ConfigScope, project_path: Path | None = None
    ) -> Path:
        """Return the skills install path for a scope.

        For GLOBAL scope: ~/.codex/skills
        For PROJECT scope: <project_path>/.codex/skills
        """
        if scope == ConfigScope.GLOBAL:
            return Path.home() / ".codex" / "skills"

        if project_path is None:
            raise ValueError("project_path required for PROJECT scope")

        return project_path.expanduser() / ".codex" / "skills"

    def install_skill(
        self, skill: Path, scope: ConfigScope, project_path: Path | None = None
    ) -> Path:
        """Install a skill into the Codex CLI scope.

        Creates the skills directory if needed, then copies the skill
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


# Auto-register this adapter when module is imported
register_adapter(CodexCliAdapter())
