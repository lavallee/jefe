"""OpenCode harness adapter.

This adapter supports OpenCode CLI, which uses:
- Global config: ~/.config/opencode/
- Project config: .opencode/ and opencode.json files
- Settings: JSON/JSONC format (opencode.json)
- Instructions: Markdown format (custom agent files)
- Skills: SKILL.md files in .opencode/skill/<name>/ directories
- Claude compatibility: Can read from .claude/ directories
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import cast

from jefe.adapters.base import DiscoveredConfig, HarnessAdapter
from jefe.data.models.harness_config import ConfigScope


class OpencodeAdapter(HarnessAdapter):
    """Adapter for OpenCode CLI."""

    version: str = "0.1.0"

    @property
    def name(self) -> str:
        """Machine-friendly adapter name."""
        return "opencode"

    @property
    def display_name(self) -> str:
        """Human-friendly adapter name."""
        return "OpenCode"

    def discover_global(self) -> list[DiscoveredConfig]:
        """Discover global configs for OpenCode.

        Searches ~/.config/opencode/ for:
        - opencode.json (settings)
        - .opencode.json (alternative settings location)
        - agent/ directory (agent definitions)
        - skill/ directory (skills)
        """
        discovered: list[DiscoveredConfig] = []

        # Primary global config location
        config_home = Path.home() / ".config" / "opencode"
        if config_home.exists():
            # Discover opencode.json
            opencode_json = config_home / "opencode.json"
            if opencode_json.is_file():
                discovered.append(
                    DiscoveredConfig(
                        harness=self.name,
                        scope=ConfigScope.GLOBAL,
                        kind="settings",
                        path=opencode_json,
                        content=self.parse_config(opencode_json),
                    )
                )

            # Discover agent directory
            agent_dir = config_home / "agent"
            if agent_dir.is_dir():
                discovered.append(
                    DiscoveredConfig(
                        harness=self.name,
                        scope=ConfigScope.GLOBAL,
                        kind="instructions",
                        path=agent_dir,
                        content=None,
                    )
                )

            # Discover skill directory
            skill_dir = config_home / "skill"
            if skill_dir.is_dir():
                discovered.append(
                    DiscoveredConfig(
                        harness=self.name,
                        scope=ConfigScope.GLOBAL,
                        kind="skills",
                        path=skill_dir,
                        content=None,
                    )
                )

        # Alternative global config location
        alt_config = Path.home() / ".opencode.json"
        if alt_config.is_file():
            discovered.append(
                DiscoveredConfig(
                    harness=self.name,
                    scope=ConfigScope.GLOBAL,
                    kind="settings",
                    path=alt_config,
                    content=self.parse_config(alt_config),
                )
            )

        return discovered

    def discover_project(
        self,
        project_path: Path,
        project_id: int | None = None,
        project_name: str | None = None,
    ) -> list[DiscoveredConfig]:
        """Discover project-level configs for OpenCode.

        Searches project_path for:
        - .opencode/ directory with config files
        - opencode.json at project root
        - .opencode.json at project root
        - .opencode/agent/ directory
        - .opencode/skill/ directory
        """
        discovered: list[DiscoveredConfig] = []
        project_path = project_path.expanduser()

        if not project_path.exists():
            return discovered

        # Discover .opencode directory
        opencode_dir = project_path / ".opencode"
        if opencode_dir.is_dir():
            # Discover .opencode/agent/
            agent_dir = opencode_dir / "agent"
            if agent_dir.is_dir():
                discovered.append(
                    DiscoveredConfig(
                        harness=self.name,
                        scope=ConfigScope.PROJECT,
                        kind="instructions",
                        path=agent_dir,
                        content=None,
                        project_id=project_id,
                        project_name=project_name,
                    )
                )

            # Discover .opencode/skill/
            skill_dir = opencode_dir / "skill"
            if skill_dir.is_dir():
                discovered.append(
                    DiscoveredConfig(
                        harness=self.name,
                        scope=ConfigScope.PROJECT,
                        kind="skills",
                        path=skill_dir,
                        content=None,
                        project_id=project_id,
                        project_name=project_name,
                    )
                )

        # Discover opencode.json at project root
        opencode_json = project_path / "opencode.json"
        if opencode_json.is_file():
            discovered.append(
                DiscoveredConfig(
                    harness=self.name,
                    scope=ConfigScope.PROJECT,
                    kind="settings",
                    path=opencode_json,
                    content=self.parse_config(opencode_json),
                    project_id=project_id,
                    project_name=project_name,
                )
            )

        # Discover .opencode.json at project root (alternative)
        alt_config = project_path / ".opencode.json"
        if alt_config.is_file():
            discovered.append(
                DiscoveredConfig(
                    harness=self.name,
                    scope=ConfigScope.PROJECT,
                    kind="settings",
                    path=alt_config,
                    content=self.parse_config(alt_config),
                    project_id=project_id,
                    project_name=project_name,
                )
            )

        return discovered

    def parse_config(self, path: Path) -> dict[str, object] | str:
        """Parse a config file into structured data.

        For .json files, attempts to parse as JSON (falls back to plain text).
        For .md files, returns as plain text.
        OpenCode supports JSONC (JSON with Comments) - stripped by simple approach.
        """
        try:
            content = path.read_text()
        except Exception:
            return ""

        # Handle JSON/JSONC files
        if path.suffix == ".json":
            try:
                # Simple JSONC support: strip // comments (line comments only)
                lines = content.split("\n")
                cleaned_lines = []
                for line in lines:
                    # Remove line comments but preserve strings with //
                    if "//" in line:
                        # Simple heuristic: if // appears outside quotes, it's a comment
                        # Check if line has quotes before //
                        comment_idx = line.find("//")
                        # Count quotes before the comment marker
                        quotes_before = line[:comment_idx].count('"')
                        # If even number of quotes, comment is outside string
                        if quotes_before % 2 == 0:
                            line = line[:comment_idx]
                    cleaned_lines.append(line)

                cleaned_content = "\n".join(cleaned_lines)
                return cast(dict[str, object], json.loads(cleaned_content))
            except json.JSONDecodeError:
                # Fallback to raw text if JSON parsing fails
                return content

        # Markdown and other files returned as plain text
        return content

    def get_skills_path(
        self, scope: ConfigScope, project_path: Path | None = None
    ) -> Path:
        """Return the skills install path for a scope.

        For GLOBAL scope: ~/.config/opencode/skill
        For PROJECT scope: <project_path>/.opencode/skill
        """
        if scope == ConfigScope.GLOBAL:
            return Path.home() / ".config" / "opencode" / "skill"

        if project_path is None:
            raise ValueError("project_path required for PROJECT scope")

        return project_path.expanduser() / ".opencode" / "skill"

    def install_skill(
        self, skill: Path, scope: ConfigScope, project_path: Path | None = None
    ) -> Path:
        """Install a skill into the OpenCode scope.

        Creates the skill directory if needed, then copies the skill
        (either a directory or single file) to the destination.
        Each skill gets its own directory with a SKILL.md file.

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
            # For single files, create a directory and copy the file
            destination.mkdir(parents=True, exist_ok=True)
            shutil.copy2(skill, destination / skill.name)

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
