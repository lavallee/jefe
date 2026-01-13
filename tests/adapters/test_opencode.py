"""Tests for OpenCode adapter."""

from pathlib import Path
from unittest.mock import patch

import pytest

from jefe.adapters.opencode import OpencodeAdapter
from jefe.data.models.harness_config import ConfigScope


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


def test_adapter_properties() -> None:
    """Test adapter name properties."""
    adapter = OpencodeAdapter()
    assert adapter.name == "opencode"
    assert adapter.display_name == "OpenCode"
    assert adapter.version == "0.1.0"


def test_discover_global_configs(tmp_path: Path) -> None:
    """Discover global OpenCode configs."""
    config_dir = tmp_path / ".config" / "opencode"
    config_dir.mkdir(parents=True)
    (config_dir / "opencode.json").write_text('{"theme": "Default"}')
    (config_dir / "agent").mkdir()
    (config_dir / "skill").mkdir()

    adapter = OpencodeAdapter()
    with patch("pathlib.Path.home", return_value=tmp_path):
        configs = adapter.discover_global()

    settings = _find_config(configs, kind="settings", scope="global")
    # JSON parsed as dict
    assert "theme" in settings["content"]

    agent_dir = _find_config(configs, kind="instructions", scope="global")
    assert agent_dir["path"] == config_dir / "agent"
    assert agent_dir["content"] is None

    skill_dir = _find_config(configs, kind="skills", scope="global")
    assert skill_dir["path"] == config_dir / "skill"


def test_discover_global_alt_location(tmp_path: Path) -> None:
    """Discover global config from alternative location."""
    alt_config = tmp_path / ".opencode.json"
    alt_config.write_text('{"theme": "Dark"}')

    adapter = OpencodeAdapter()
    with patch("pathlib.Path.home", return_value=tmp_path):
        configs = adapter.discover_global()

    settings = _find_config(configs, kind="settings", scope="global")
    assert "theme" in settings["content"]
    assert settings["path"] == alt_config


def test_discover_global_no_config_dir(tmp_path: Path) -> None:
    """Return empty list when ~/.config/opencode doesn't exist."""
    adapter = OpencodeAdapter()
    with patch("pathlib.Path.home", return_value=tmp_path):
        configs = adapter.discover_global()
    assert configs == []


def test_discover_project_configs(tmp_path: Path) -> None:
    """Discover project-level OpenCode configs."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "opencode.json").write_text('{"theme": "Dark"}')

    opencode_dir = project_dir / ".opencode"
    opencode_dir.mkdir()
    (opencode_dir / "agent").mkdir()
    (opencode_dir / "skill").mkdir()

    adapter = OpencodeAdapter()
    configs = adapter.discover_project(project_dir, project_id=1, project_name="demo")

    settings = _find_config(configs, kind="settings", scope="project")
    assert "theme" in settings["content"]
    assert settings["project_id"] == 1
    assert settings["project_name"] == "demo"

    agent_dir = _find_config(configs, kind="instructions", scope="project")
    assert agent_dir["path"] == opencode_dir / "agent"

    skill_dir = _find_config(configs, kind="skills", scope="project")
    assert skill_dir["path"] == opencode_dir / "skill"


def test_discover_project_alt_config(tmp_path: Path) -> None:
    """Discover project config from alternative location."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    alt_config = project_dir / ".opencode.json"
    alt_config.write_text('{"theme": "Light"}')

    adapter = OpencodeAdapter()
    configs = adapter.discover_project(project_dir)

    settings = _find_config(configs, kind="settings", scope="project")
    assert "theme" in settings["content"]
    assert settings["path"] == alt_config


def test_discover_project_no_configs(tmp_path: Path) -> None:
    """Return empty list when project has no OpenCode configs."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    adapter = OpencodeAdapter()
    configs = adapter.discover_project(project_dir)
    assert configs == []


def test_parse_config_json(tmp_path: Path) -> None:
    """Parse JSON config file."""
    json_path = tmp_path / "opencode.json"
    json_path.write_text('{"theme": "Default", "model": "claude-3.5-sonnet"}')

    adapter = OpencodeAdapter()
    data = adapter.parse_config(json_path)
    assert data == {"theme": "Default", "model": "claude-3.5-sonnet"}


def test_parse_config_jsonc_with_comments(tmp_path: Path) -> None:
    """Parse JSONC (JSON with Comments) config file."""
    json_path = tmp_path / "opencode.json"
    json_path.write_text('''
{
  "theme": "Default", // This is a comment
  // This is a full line comment
  "model": "claude-3.5-sonnet"
}
''')

    adapter = OpencodeAdapter()
    data = adapter.parse_config(json_path)
    assert isinstance(data, dict)
    assert "theme" in data
    assert data["theme"] == "Default"
    assert data["model"] == "claude-3.5-sonnet"


def test_parse_config_json_fallback(tmp_path: Path) -> None:
    """Fall back to plain text for invalid JSON."""
    json_path = tmp_path / "opencode.json"
    json_path.write_text('{"theme": "Default",}')

    adapter = OpencodeAdapter()
    data = adapter.parse_config(json_path)
    assert isinstance(data, str)
    assert "theme" in data


def test_parse_config_markdown(tmp_path: Path) -> None:
    """Parse markdown file as plain text."""
    md_path = tmp_path / "agent.md"
    md_path.write_text("# Agent instructions\n\nUse these patterns.")

    adapter = OpencodeAdapter()
    data = adapter.parse_config(md_path)
    assert isinstance(data, str)
    assert "Agent instructions" in data


def test_get_skills_path_global() -> None:
    """Get global skills path."""
    adapter = OpencodeAdapter()
    skills_path = adapter.get_skills_path(ConfigScope.GLOBAL)
    assert skills_path == Path.home() / ".config" / "opencode" / "skill"


def test_get_skills_path_project(tmp_path: Path) -> None:
    """Get project skills path."""
    project_dir = tmp_path / "project"
    adapter = OpencodeAdapter()
    skills_path = adapter.get_skills_path(ConfigScope.PROJECT, project_path=project_dir)
    assert skills_path == project_dir / ".opencode" / "skill"


def test_get_skills_path_project_no_path() -> None:
    """Raise error when project_path is required but not provided."""
    adapter = OpencodeAdapter()
    with pytest.raises(ValueError, match="project_path required"):
        adapter.get_skills_path(ConfigScope.PROJECT)


def test_install_skill_directory_global(tmp_path: Path) -> None:
    """Install a skill directory to global scope."""
    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# My Skill")

    adapter = OpencodeAdapter()
    with patch("pathlib.Path.home", return_value=tmp_path):
        installed_path = adapter.install_skill(skill_dir, ConfigScope.GLOBAL)

    expected = tmp_path / ".config" / "opencode" / "skill" / "my-skill"
    assert installed_path == expected
    assert (expected / "SKILL.md").exists()


def test_install_skill_directory_project(tmp_path: Path) -> None:
    """Install a skill directory to project scope."""
    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# My Skill")

    project_dir = tmp_path / "project"
    project_dir.mkdir()

    adapter = OpencodeAdapter()
    installed_path = adapter.install_skill(
        skill_dir, ConfigScope.PROJECT, project_path=project_dir
    )

    expected = project_dir / ".opencode" / "skill" / "my-skill"
    assert installed_path == expected
    assert (expected / "SKILL.md").exists()


def test_install_skill_single_file(tmp_path: Path) -> None:
    """Install a single skill file."""
    skill_file = tmp_path / "SKILL.md"
    skill_file.write_text("# Single file skill")

    project_dir = tmp_path / "project"
    project_dir.mkdir()

    adapter = OpencodeAdapter()
    installed_path = adapter.install_skill(
        skill_file, ConfigScope.PROJECT, project_path=project_dir
    )

    expected = project_dir / ".opencode" / "skill" / "SKILL.md"
    assert installed_path == expected
    assert (expected / "SKILL.md").exists()


def test_install_skill_replaces_existing(tmp_path: Path) -> None:
    """Installing a skill replaces existing installation."""
    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# My Skill v2")

    project_dir = tmp_path / "project"
    project_dir.mkdir()

    # Create existing installation
    existing = project_dir / ".opencode" / "skill" / "my-skill"
    existing.mkdir(parents=True)
    (existing / "SKILL.md").write_text("# My Skill v1")

    adapter = OpencodeAdapter()
    installed_path = adapter.install_skill(
        skill_dir, ConfigScope.PROJECT, project_path=project_dir
    )

    assert installed_path == existing
    content = (existing / "SKILL.md").read_text()
    assert "v2" in content
    assert "v1" not in content


def test_uninstall_skill_directory(tmp_path: Path) -> None:
    """Uninstall a skill directory."""
    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# My Skill")

    adapter = OpencodeAdapter()
    result = adapter.uninstall_skill(skill_dir)

    assert result is True
    assert not skill_dir.exists()


def test_uninstall_skill_file(tmp_path: Path) -> None:
    """Uninstall a skill file."""
    skill_file = tmp_path / "SKILL.md"
    skill_file.write_text("# My Skill")

    adapter = OpencodeAdapter()
    result = adapter.uninstall_skill(skill_file)

    assert result is True
    assert not skill_file.exists()


def test_uninstall_skill_not_exists(tmp_path: Path) -> None:
    """Uninstall returns False for non-existent path."""
    skill_dir = tmp_path / "nonexistent"

    adapter = OpencodeAdapter()
    result = adapter.uninstall_skill(skill_dir)

    assert result is False
