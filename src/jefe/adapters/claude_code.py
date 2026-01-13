"""Claude Code harness adapter."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from jefe.adapters.base import ConfigKind, ConfigScope, DiscoveredConfig, HarnessAdapter
from jefe.adapters.registry import register_adapter


class ClaudeCodeAdapter(HarnessAdapter):
    """Adapter for Claude Code config discovery."""

    @property
    def name(self) -> str:
        return "claude-code"

    @property
    def display_name(self) -> str:
        return "Claude Code"

    def discover_global(self) -> list[DiscoveredConfig]:
        base_dir = Path.home() / ".claude"
        results = self._discover_in_dir(base_dir, scope=ConfigScope.GLOBAL)
        results.extend(self._discover_skills(base_dir, scope=ConfigScope.GLOBAL))
        return results

    def discover_project(
        self, project_path: Path, project_id: int | None = None, project_name: str | None = None
    ) -> list[DiscoveredConfig]:
        project_path = project_path.expanduser()
        results: list[DiscoveredConfig] = []

        results.extend(
            self._discover_in_dir(
                project_path / ".claude",
                scope=ConfigScope.PROJECT,
                project_id=project_id,
                project_name=project_name,
            )
        )

        instructions_path = project_path / "CLAUDE.md"
        results.extend(
            self._discover_file(
                instructions_path,
                scope=ConfigScope.PROJECT,
                kind="instructions",
                project_id=project_id,
                project_name=project_name,
            )
        )

        results.extend(
            self._discover_skills(
                project_path / ".claude",
                scope=ConfigScope.PROJECT,
                project_id=project_id,
                project_name=project_name,
            )
        )
        return results

    def _discover_in_dir(
        self,
        base_dir: Path,
        scope: ConfigScope,
        project_id: int | None = None,
        project_name: str | None = None,
    ) -> list[DiscoveredConfig]:
        results: list[DiscoveredConfig] = []
        results.extend(
            self._discover_file(
                base_dir / "settings.json",
                scope=scope,
                kind="settings",
                project_id=project_id,
                project_name=project_name,
            )
        )
        results.extend(
            self._discover_file(
                base_dir / "CLAUDE.md",
                scope=scope,
                kind="instructions",
                project_id=project_id,
                project_name=project_name,
            )
        )
        return results

    def _discover_skills(
        self,
        base_dir: Path,
        scope: ConfigScope,
        project_id: int | None = None,
        project_name: str | None = None,
    ) -> list[DiscoveredConfig]:
        skills_dir = base_dir / "skills"
        if skills_dir.exists() and skills_dir.is_dir():
            return [
                DiscoveredConfig(
                    harness=self.name,
                    scope=scope,
                    kind="skills",
                    path=skills_dir,
                    content=None,
                    project_id=project_id,
                    project_name=project_name,
                )
            ]
        return []

    def _discover_file(
        self,
        path: Path,
        scope: ConfigScope,
        kind: ConfigKind,
        project_id: int | None = None,
        project_name: str | None = None,
    ) -> list[DiscoveredConfig]:
        if not path.exists() or not path.is_file():
            return []

        content = self.parse_config(path)
        return [
            DiscoveredConfig(
                harness=self.name,
                scope=scope,
                kind=kind,
                path=path,
                content=content,
                project_id=project_id,
                project_name=project_name,
            )
        ]

    def parse_config(self, path: Path) -> dict[str, object] | str:
        if path.suffix.lower() == ".json":
            raw = path.read_text()
            try:
                data = json.loads(raw)
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                return raw
            return raw

        return path.read_text()

    def get_skills_path(self, scope: ConfigScope, project_path: Path | None = None) -> Path:
        if scope == ConfigScope.GLOBAL:
            return Path.home() / ".claude" / "skills"

        if project_path is None:
            raise ValueError("project_path is required for project scope skills")

        return project_path.expanduser() / ".claude" / "skills"

    def install_skill(
        self, skill: Path, scope: ConfigScope, project_path: Path | None = None
    ) -> Path:
        skill_path = Path(skill)
        destination_dir = self.get_skills_path(scope, project_path=project_path)
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = destination_dir / skill_path.name

        if skill_path.is_dir():
            if destination.exists():
                shutil.rmtree(destination)
            shutil.copytree(skill_path, destination)
        else:
            shutil.copy2(skill_path, destination)

        return destination

    def uninstall_skill(self, installed_path: Path) -> bool:
        installed_path = Path(installed_path)
        if not installed_path.exists():
            return False

        if installed_path.is_dir():
            shutil.rmtree(installed_path)
        else:
            installed_path.unlink()

        return True


# Auto-register this adapter when module is imported
register_adapter(ClaudeCodeAdapter())
