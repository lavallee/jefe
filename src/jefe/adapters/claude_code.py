"""Claude Code harness adapter."""

from __future__ import annotations

import json
from pathlib import Path

from jefe.adapters.base import ConfigKind, ConfigScope, DiscoveredConfig, HarnessAdapter


class ClaudeCodeAdapter(HarnessAdapter):
    """Adapter for Claude Code config discovery."""

    name = "claude-code"
    display_name = "Claude Code"

    def discover_global(self) -> list[DiscoveredConfig]:
        base_dir = Path.home() / ".claude"
        results = self._discover_in_dir(base_dir, scope="global")
        results.extend(self._discover_skills(base_dir, scope="global"))
        return results

    def discover_project(
        self, project_path: Path, project_id: int | None = None, project_name: str | None = None
    ) -> list[DiscoveredConfig]:
        project_path = project_path.expanduser()
        results: list[DiscoveredConfig] = []

        results.extend(
            self._discover_in_dir(
                project_path / ".claude",
                scope="project",
                project_id=project_id,
                project_name=project_name,
            )
        )

        instructions_path = project_path / "CLAUDE.md"
        results.extend(
            self._discover_file(
                instructions_path,
                scope="project",
                kind="instructions",
                project_id=project_id,
                project_name=project_name,
            )
        )

        results.extend(
            self._discover_skills(
                project_path / ".claude",
                scope="project",
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

        content = self._parse_config(path)
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

    def _parse_config(self, path: Path) -> dict[str, object] | str:
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
