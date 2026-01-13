"""Tests for Gemini CLI adapter."""

from pathlib import Path
from unittest.mock import patch

from jefe.adapters.gemini_cli import GeminiCliAdapter


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
    return Path(__file__).parent / "fixtures" / "gemini_cli" / name


def test_adapter_properties() -> None:
    """Test adapter name properties."""
    adapter = GeminiCliAdapter()
    assert adapter.name == "gemini_cli"
    assert adapter.display_name == "Gemini CLI"
    assert adapter.version == "0.1.0"


def test_discover_global_configs(tmp_path: Path) -> None:
    """Discover global Gemini CLI configs."""
    base_dir = tmp_path / ".gemini"
    base_dir.mkdir(parents=True)
    (base_dir / "settings.json").write_text('{"theme": "Default"}')
    (base_dir / "GEMINI.md").write_text("# Global instructions")
    (base_dir / "commands").mkdir()

    adapter = GeminiCliAdapter()
    with patch("pathlib.Path.home", return_value=tmp_path):
        configs = adapter.discover_global()

    settings = _find_config(configs, kind="settings", scope="global")
    # JSON parsed as dict
    assert "theme" in settings["content"]

    instructions = _find_config(configs, kind="instructions", scope="global")
    assert "# Global instructions" in str(instructions["content"])

    skills = _find_config(configs, kind="skills", scope="global")
    assert skills["path"] == base_dir / "commands"


def test_discover_global_no_gemini_dir(tmp_path: Path) -> None:
    """Return empty list when ~/.gemini doesn't exist."""
    adapter = GeminiCliAdapter()
    with patch("pathlib.Path.home", return_value=tmp_path):
        configs = adapter.discover_global()
    assert configs == []


def test_discover_project_configs(tmp_path: Path) -> None:
    """Discover project-level Gemini CLI configs."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "GEMINI.md").write_text("# Project instructions")
    gemini_dir = project_dir / ".gemini"
    gemini_dir.mkdir()
    (gemini_dir / "settings.json").write_text('{"theme": "Dark"}')
    (gemini_dir / "commands").mkdir()

    adapter = GeminiCliAdapter()
    configs = adapter.discover_project(project_dir, project_id=1, project_name="demo")

    settings = _find_config(configs, kind="settings", scope="project")
    assert "theme" in settings["content"]
    assert settings["project_id"] == 1
    assert settings["project_name"] == "demo"

    instructions = _find_config(configs, kind="instructions", scope="project")
    assert "# Project instructions" in str(instructions["content"])

    skills = _find_config(configs, kind="skills", scope="project")
    assert skills["path"] == gemini_dir / "commands"


def test_discover_project_no_configs(tmp_path: Path) -> None:
    """Return empty list when project has no Gemini configs."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    adapter = GeminiCliAdapter()
    configs = adapter.discover_project(project_dir)
    assert configs == []


def test_parse_config_json(tmp_path: Path) -> None:
    """Parse JSON config file."""
    json_path = tmp_path / "settings.json"
    json_path.write_text('{"theme": "Default", "model": "gemini-2.5-pro"}')

    adapter = GeminiCliAdapter()
    data = adapter.parse_config(json_path)
    assert data == {"theme": "Default", "model": "gemini-2.5-pro"}


def test_parse_config_json_fallback(tmp_path: Path) -> None:
    """Fall back to plain text for invalid JSON."""
    json_path = tmp_path / "settings.json"
    json_path.write_text('{"theme": "Default",}')

    adapter = GeminiCliAdapter()
    data = adapter.parse_config(json_path)
    assert data == '{"theme": "Default",}'


def test_parse_config_toml(tmp_path: Path) -> None:
    """Parse TOML config file."""
    toml_path = tmp_path / "command.toml"
    toml_path.write_text('description = "Test command"\nprompt = "Run tests"')

    adapter = GeminiCliAdapter()
    data = adapter.parse_config(toml_path)
    assert isinstance(data, dict)
    assert "description" in data
    assert data["description"] == "Test command"


def test_parse_config_toml_fallback(tmp_path: Path) -> None:
    """Fall back to plain text for invalid TOML."""
    toml_path = tmp_path / "command.toml"
    toml_path.write_text('invalid toml syntax [[[')

    adapter = GeminiCliAdapter()
    data = adapter.parse_config(toml_path)
    assert isinstance(data, str)
    assert "invalid toml syntax" in data


def test_parse_config_markdown(tmp_path: Path) -> None:
    """Parse markdown file as plain text."""
    md_path = tmp_path / "GEMINI.md"
    md_path.write_text("# Gemini instructions\n\nUse these patterns.")

    adapter = GeminiCliAdapter()
    data = adapter.parse_config(md_path)
    assert isinstance(data, str)
    assert "Gemini instructions" in data


def test_get_skills_path_global(tmp_path: Path) -> None:
    """Get global skills path."""
    adapter = GeminiCliAdapter()
    with patch("pathlib.Path.home", return_value=tmp_path):
        path = adapter.get_skills_path("global")
    assert path == tmp_path / ".gemini" / "commands"


def test_get_skills_path_project(tmp_path: Path) -> None:
    """Get project skills path."""
    adapter = GeminiCliAdapter()
    project_path = tmp_path / "project"
    path = adapter.get_skills_path("project", project_path=project_path)
    assert path == project_path / ".gemini" / "commands"


def test_get_skills_path_project_requires_path(tmp_path: Path) -> None:
    """Project scope requires project_path parameter."""
    adapter = GeminiCliAdapter()
    try:
        adapter.get_skills_path("project", project_path=None)
        raise AssertionError("Expected ValueError")
    except ValueError as e:
        assert "project_path required" in str(e)


def test_install_skill_file(tmp_path: Path) -> None:
    """Install a skill file."""
    adapter = GeminiCliAdapter()
    skill_file = tmp_path / "test.toml"
    skill_file.write_text('prompt = "Test command"')
    project_path = tmp_path / "project"

    installed = adapter.install_skill(skill_file, "project", project_path=project_path)

    assert installed == project_path / ".gemini" / "commands" / "test.toml"
    assert installed.read_text() == 'prompt = "Test command"'


def test_install_skill_directory(tmp_path: Path) -> None:
    """Install a skill directory."""
    adapter = GeminiCliAdapter()
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# Skill docs")
    (skill_dir / "command.toml").write_text('prompt = "Run command"')
    project_path = tmp_path / "project"

    installed = adapter.install_skill(skill_dir, "project", project_path=project_path)

    assert installed == project_path / ".gemini" / "commands" / "skill"
    assert (installed / "SKILL.md").read_text() == "# Skill docs"
    assert (installed / "command.toml").read_text() == 'prompt = "Run command"'


def test_install_skill_overwrites_existing(tmp_path: Path) -> None:
    """Installing a skill overwrites existing installation."""
    adapter = GeminiCliAdapter()
    skill_file = tmp_path / "test.toml"
    skill_file.write_text('prompt = "New version"')
    project_path = tmp_path / "project"

    # Install first version
    dest_dir = project_path / ".gemini" / "commands"
    dest_dir.mkdir(parents=True)
    existing = dest_dir / "test.toml"
    existing.write_text('prompt = "Old version"')

    # Install should overwrite
    installed = adapter.install_skill(skill_file, "project", project_path=project_path)

    assert installed.read_text() == 'prompt = "New version"'


def test_uninstall_skill_file(tmp_path: Path) -> None:
    """Uninstall a skill file."""
    adapter = GeminiCliAdapter()
    skill_path = tmp_path / "test.toml"
    skill_path.write_text('prompt = "Test"')

    result = adapter.uninstall_skill(skill_path)

    assert result is True
    assert not skill_path.exists()


def test_uninstall_skill_directory(tmp_path: Path) -> None:
    """Uninstall a skill directory."""
    adapter = GeminiCliAdapter()
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# Skill")

    result = adapter.uninstall_skill(skill_dir)

    assert result is True
    assert not skill_dir.exists()


def test_uninstall_skill_nonexistent(tmp_path: Path) -> None:
    """Uninstalling nonexistent skill returns False."""
    adapter = GeminiCliAdapter()
    fake_path = tmp_path / "nonexistent"

    result = adapter.uninstall_skill(fake_path)

    assert result is False
