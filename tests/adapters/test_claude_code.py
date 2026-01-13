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


def _fixture_path(name: str) -> Path:
    return Path(__file__).parent / "fixtures" / "claude_code" / name


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


def test_parse_config_json() -> None:
    adapter = ClaudeCodeAdapter()
    data = adapter.parse_config(_fixture_path("settings.json"))
    assert data == {"model": "claude-3", "temperature": 0.2}


def test_parse_config_markdown() -> None:
    adapter = ClaudeCodeAdapter()
    data = adapter.parse_config(_fixture_path("CLAUDE.md"))
    assert isinstance(data, str)
    assert "Claude Code instructions" in data


def test_parse_config_invalid_json(tmp_path: Path) -> None:
    invalid_path = tmp_path / "settings.json"
    invalid_path.write_text('{"model": "claude-3",}')
    adapter = ClaudeCodeAdapter()
    data = adapter.parse_config(invalid_path)
    assert data == '{"model": "claude-3",}'


def test_get_skills_path_global(tmp_path: Path) -> None:
    adapter = ClaudeCodeAdapter()
    with patch("pathlib.Path.home", return_value=tmp_path):
        path = adapter.get_skills_path("global")
    assert path == tmp_path / ".claude" / "skills"


def test_get_skills_path_project(tmp_path: Path) -> None:
    adapter = ClaudeCodeAdapter()
    project_path = tmp_path / "project"
    path = adapter.get_skills_path("project", project_path=project_path)
    assert path == project_path / ".claude" / "skills"


def test_install_skill_file(tmp_path: Path) -> None:
    adapter = ClaudeCodeAdapter()
    skill_file = tmp_path / "skill.md"
    skill_file.write_text("# Skill")
    project_path = tmp_path / "project"

    installed = adapter.install_skill(skill_file, "project", project_path=project_path)

    assert installed == project_path / ".claude" / "skills" / "skill.md"
    assert installed.read_text() == "# Skill"


def test_install_skill_directory(tmp_path: Path) -> None:
    adapter = ClaudeCodeAdapter()
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    (skill_dir / "README.md").write_text("Skill docs")
    project_path = tmp_path / "project"

    installed = adapter.install_skill(skill_dir, "project", project_path=project_path)

    assert installed == project_path / ".claude" / "skills" / "skill"
    assert (installed / "README.md").read_text() == "Skill docs"
