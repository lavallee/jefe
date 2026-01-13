"""Tests for Claude Code adapter."""

from pathlib import Path
from unittest.mock import patch

from jefe.adapters.claude_code import ClaudeCodeAdapter


def _find_config(configs: list, kind: str, scope: str) -> dict:
    for config in configs:
        if config.kind == kind and config.scope == scope:
            return {
                "path": config.path,
                "content": config.content,
                "project_id": config.project_id,
                "project_name": config.project_name,
            }
    raise AssertionError(f"Missing config {kind} ({scope})")


def test_discover_global_configs(tmp_path: Path) -> None:
    """Discover global Claude Code configs."""
    base_dir = tmp_path / ".claude"
    base_dir.mkdir(parents=True)
    (base_dir / "settings.json").write_text('{"model": "claude-3"}')
    (base_dir / "CLAUDE.md").write_text("# Global instructions")
    (base_dir / "skills").mkdir()

    adapter = ClaudeCodeAdapter()
    with patch("pathlib.Path.home", return_value=tmp_path):
        configs = adapter.discover_global()

    settings = _find_config(configs, kind="settings", scope="global")
    assert settings["content"] == {"model": "claude-3"}

    instructions = _find_config(configs, kind="instructions", scope="global")
    assert "# Global instructions" in str(instructions["content"])

    skills = _find_config(configs, kind="skills", scope="global")
    assert skills["path"] == base_dir / "skills"


def test_discover_project_configs(tmp_path: Path) -> None:
    """Discover project-level Claude Code configs."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "CLAUDE.md").write_text("# Project instructions")
    claude_dir = project_dir / ".claude"
    claude_dir.mkdir()
    (claude_dir / "settings.json").write_text('{"temperature": 0.2}')
    (claude_dir / "skills").mkdir()

    adapter = ClaudeCodeAdapter()
    configs = adapter.discover_project(project_dir, project_id=1, project_name="demo")

    settings = _find_config(configs, kind="settings", scope="project")
    assert settings["content"] == {"temperature": 0.2}
    assert settings["project_id"] == 1
    assert settings["project_name"] == "demo"

    instructions = _find_config(configs, kind="instructions", scope="project")
    assert "# Project instructions" in str(instructions["content"])

    skills = _find_config(configs, kind="skills", scope="project")
    assert skills["path"] == claude_dir / "skills"
