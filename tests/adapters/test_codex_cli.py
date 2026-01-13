"""Tests for Codex CLI adapter."""

from pathlib import Path
from unittest.mock import patch

from jefe.adapters.codex_cli import CodexCliAdapter


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
    return Path(__file__).parent / "fixtures" / "codex_cli" / name


def test_adapter_properties() -> None:
    """Test adapter name properties."""
    adapter = CodexCliAdapter()
    assert adapter.name == "codex_cli"
    assert adapter.display_name == "Codex CLI"
    assert adapter.version == "0.1.0"


def test_discover_global_configs(tmp_path: Path) -> None:
    """Discover global Codex CLI configs."""
    base_dir = tmp_path / ".codex"
    base_dir.mkdir(parents=True)
    (base_dir / "config.toml").write_text('[settings]\nmodel = "gpt-4"')
    (base_dir / "AGENTS.md").write_text("# Global instructions")
    (base_dir / "skills").mkdir()

    adapter = CodexCliAdapter()
    with patch("pathlib.Path.home", return_value=tmp_path):
        configs = adapter.discover_global()

    settings = _find_config(configs, kind="settings", scope="global")
    # TOML parsed as dict
    assert "settings" in settings["content"]

    instructions = _find_config(configs, kind="instructions", scope="global")
    assert "# Global instructions" in str(instructions["content"])

    skills = _find_config(configs, kind="skills", scope="global")
    assert skills["path"] == base_dir / "skills"


def test_discover_global_agents_override(tmp_path: Path) -> None:
    """Discover AGENTS.override.md takes precedence over AGENTS.md."""
    base_dir = tmp_path / ".codex"
    base_dir.mkdir(parents=True)
    (base_dir / "AGENTS.md").write_text("# Regular instructions")
    (base_dir / "AGENTS.override.md").write_text("# Override instructions")

    adapter = CodexCliAdapter()
    with patch("pathlib.Path.home", return_value=tmp_path):
        configs = adapter.discover_global()

    instructions = _find_config(configs, kind="instructions", scope="global")
    assert "# Override instructions" in str(instructions["content"])
    assert instructions["path"] == base_dir / "AGENTS.override.md"


def test_discover_global_no_codex_dir(tmp_path: Path) -> None:
    """Return empty list when ~/.codex doesn't exist."""
    adapter = CodexCliAdapter()
    with patch("pathlib.Path.home", return_value=tmp_path):
        configs = adapter.discover_global()
    assert configs == []


def test_discover_project_configs(tmp_path: Path) -> None:
    """Discover project-level Codex CLI configs."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "AGENTS.md").write_text("# Project instructions")
    codex_dir = project_dir / ".codex"
    codex_dir.mkdir()
    (codex_dir / "config.toml").write_text('[project]\nname = "demo"')
    (codex_dir / "skills").mkdir()

    adapter = CodexCliAdapter()
    configs = adapter.discover_project(project_dir, project_id=1, project_name="demo")

    settings = _find_config(configs, kind="settings", scope="project")
    assert "project" in settings["content"]
    assert settings["project_id"] == 1
    assert settings["project_name"] == "demo"

    instructions = _find_config(configs, kind="instructions", scope="project")
    assert "# Project instructions" in str(instructions["content"])

    skills = _find_config(configs, kind="skills", scope="project")
    assert skills["path"] == codex_dir / "skills"


def test_discover_project_agents_override(tmp_path: Path) -> None:
    """Discover AGENTS.override.md takes precedence at project level."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "AGENTS.md").write_text("# Regular project instructions")
    (project_dir / "AGENTS.override.md").write_text("# Override project instructions")

    adapter = CodexCliAdapter()
    configs = adapter.discover_project(project_dir)

    instructions = _find_config(configs, kind="instructions", scope="project")
    assert "# Override project instructions" in str(instructions["content"])
    assert instructions["path"] == project_dir / "AGENTS.override.md"


def test_discover_project_no_configs(tmp_path: Path) -> None:
    """Return empty list when project has no Codex configs."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    adapter = CodexCliAdapter()
    configs = adapter.discover_project(project_dir)
    assert configs == []


def test_parse_config_toml(tmp_path: Path) -> None:
    """Parse TOML config file."""
    toml_path = tmp_path / "config.toml"
    toml_path.write_text('[settings]\nmodel = "gpt-4"\ntemperature = 0.7')

    adapter = CodexCliAdapter()
    data = adapter.parse_config(toml_path)
    assert isinstance(data, dict)
    assert "settings" in data


def test_parse_config_toml_fallback(tmp_path: Path) -> None:
    """Fall back to plain text for invalid TOML."""
    toml_path = tmp_path / "config.toml"
    toml_path.write_text('invalid toml syntax [[[')

    adapter = CodexCliAdapter()
    data = adapter.parse_config(toml_path)
    assert isinstance(data, str)
    assert "invalid toml syntax" in data


def test_parse_config_json(tmp_path: Path) -> None:
    """Parse JSON config file."""
    json_path = tmp_path / "settings.json"
    json_path.write_text('{"model": "gpt-4", "temperature": 0.2}')

    adapter = CodexCliAdapter()
    data = adapter.parse_config(json_path)
    assert data == {"model": "gpt-4", "temperature": 0.2}


def test_parse_config_json_fallback(tmp_path: Path) -> None:
    """Fall back to plain text for invalid JSON."""
    json_path = tmp_path / "settings.json"
    json_path.write_text('{"model": "gpt-4",}')

    adapter = CodexCliAdapter()
    data = adapter.parse_config(json_path)
    assert data == '{"model": "gpt-4",}'


def test_parse_config_markdown(tmp_path: Path) -> None:
    """Parse markdown file as plain text."""
    md_path = tmp_path / "AGENTS.md"
    md_path.write_text("# Codex instructions\n\nUse these patterns.")

    adapter = CodexCliAdapter()
    data = adapter.parse_config(md_path)
    assert isinstance(data, str)
    assert "Codex instructions" in data


def test_get_skills_path_global(tmp_path: Path) -> None:
    """Get global skills path."""
    adapter = CodexCliAdapter()
    with patch("pathlib.Path.home", return_value=tmp_path):
        path = adapter.get_skills_path("global")
    assert path == tmp_path / ".codex" / "skills"


def test_get_skills_path_project(tmp_path: Path) -> None:
    """Get project skills path."""
    adapter = CodexCliAdapter()
    project_path = tmp_path / "project"
    path = adapter.get_skills_path("project", project_path=project_path)
    assert path == project_path / ".codex" / "skills"


def test_get_skills_path_project_requires_path(tmp_path: Path) -> None:
    """Project scope requires project_path parameter."""
    adapter = CodexCliAdapter()
    try:
        adapter.get_skills_path("project", project_path=None)
        assert False, "Expected ValueError"
    except ValueError as e:
        assert "project_path required" in str(e)


def test_install_skill_file(tmp_path: Path) -> None:
    """Install a skill file."""
    adapter = CodexCliAdapter()
    skill_file = tmp_path / "skill.md"
    skill_file.write_text("# Skill")
    project_path = tmp_path / "project"

    installed = adapter.install_skill(skill_file, "project", project_path=project_path)

    assert installed == project_path / ".codex" / "skills" / "skill.md"
    assert installed.read_text() == "# Skill"


def test_install_skill_directory(tmp_path: Path) -> None:
    """Install a skill directory."""
    adapter = CodexCliAdapter()
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# Skill docs")
    (skill_dir / "script.py").write_text("print('hello')")
    project_path = tmp_path / "project"

    installed = adapter.install_skill(skill_dir, "project", project_path=project_path)

    assert installed == project_path / ".codex" / "skills" / "skill"
    assert (installed / "SKILL.md").read_text() == "# Skill docs"
    assert (installed / "script.py").read_text() == "print('hello')"


def test_install_skill_overwrites_existing(tmp_path: Path) -> None:
    """Installing a skill overwrites existing installation."""
    adapter = CodexCliAdapter()
    skill_file = tmp_path / "skill.md"
    skill_file.write_text("# New version")
    project_path = tmp_path / "project"

    # Install first version
    dest_dir = project_path / ".codex" / "skills"
    dest_dir.mkdir(parents=True)
    existing = dest_dir / "skill.md"
    existing.write_text("# Old version")

    # Install should overwrite
    installed = adapter.install_skill(skill_file, "project", project_path=project_path)

    assert installed.read_text() == "# New version"


def test_uninstall_skill_file(tmp_path: Path) -> None:
    """Uninstall a skill file."""
    adapter = CodexCliAdapter()
    skill_path = tmp_path / "skill.md"
    skill_path.write_text("# Skill")

    result = adapter.uninstall_skill(skill_path)

    assert result is True
    assert not skill_path.exists()


def test_uninstall_skill_directory(tmp_path: Path) -> None:
    """Uninstall a skill directory."""
    adapter = CodexCliAdapter()
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# Skill")

    result = adapter.uninstall_skill(skill_dir)

    assert result is True
    assert not skill_dir.exists()


def test_uninstall_skill_nonexistent(tmp_path: Path) -> None:
    """Uninstalling nonexistent skill returns False."""
    adapter = CodexCliAdapter()
    fake_path = tmp_path / "nonexistent"

    result = adapter.uninstall_skill(fake_path)

    assert result is False
