"""Tests for CLI configuration commands."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from jefe.cli.app import app
from jefe.cli.config import (
    get_config_dir,
    get_config_file,
    load_config,
    save_config,
    set_config_value,
)

runner = CliRunner()


@pytest.fixture
def temp_config_dir(tmp_path: Path) -> Path:
    """Create a temporary config directory."""
    config_dir = tmp_path / "config" / "jefe"
    config_dir.mkdir(parents=True)
    return config_dir


def _load_test_config(temp_config_dir: Path) -> dict[str, str]:
    """Helper to load test config."""
    config_file = temp_config_dir / "config.json"
    if config_file.exists():
        return json.loads(config_file.read_text())
    return {}


def _save_test_config(temp_config_dir: Path, key: str, value: str) -> None:
    """Helper to save test config."""
    config_file = temp_config_dir / "config.json"
    existing = _load_test_config(temp_config_dir)
    existing[key] = value
    config_file.write_text(json.dumps(existing, indent=2))


@pytest.fixture(name="_mock_config_dir")
def mock_config_dir(temp_config_dir: Path) -> None:
    """Mock the config directory to use temp directory."""
    with (
        patch("jefe.cli.config.get_config_dir", return_value=temp_config_dir),
        patch(
            "jefe.cli.commands.config.get_config_file",
            return_value=temp_config_dir / "config.json",
        ),
        patch(
            "jefe.cli.commands.config.load_config",
            side_effect=lambda: _load_test_config(temp_config_dir),
        ),
        patch(
            "jefe.cli.commands.config.set_config_value",
            side_effect=lambda k, v: _save_test_config(temp_config_dir, k, v),
        ),
    ):
        yield


class TestConfigDirectory:
    """Test configuration directory functions."""

    def test_get_config_dir_creates_directory(self, tmp_path: Path) -> None:
        """Test that get_config_dir creates the directory if it doesn't exist."""
        with patch("pathlib.Path.home", return_value=tmp_path):
            config_dir = get_config_dir()
            assert config_dir.exists()
            assert config_dir == tmp_path / ".config" / "jefe"

    def test_get_config_file_path(self, tmp_path: Path) -> None:
        """Test that get_config_file returns correct path."""
        with patch("pathlib.Path.home", return_value=tmp_path):
            config_file = get_config_file()
            assert config_file == tmp_path / ".config" / "jefe" / "config.json"


class TestConfigOperations:
    """Test configuration load/save operations."""

    def test_load_config_empty_file(self, temp_config_dir: Path) -> None:
        """Test loading config when file doesn't exist."""
        with patch("jefe.cli.config.get_config_file", return_value=temp_config_dir / "config.json"):
            config = load_config()
            assert config == {}

    def test_save_and_load_config(self, temp_config_dir: Path) -> None:
        """Test saving and loading configuration."""
        config_data = {"server_url": "http://localhost:8000", "api_key": "test123"}

        with patch("jefe.cli.config.get_config_file", return_value=temp_config_dir / "config.json"):
            save_config(config_data)
            loaded = load_config()
            assert loaded == config_data

    def test_set_config_value(self, temp_config_dir: Path) -> None:
        """Test setting a single config value."""
        with patch("jefe.cli.config.get_config_file", return_value=temp_config_dir / "config.json"):
            set_config_value("server_url", "http://localhost:8000")
            config = load_config()
            assert config["server_url"] == "http://localhost:8000"

    def test_set_config_value_preserves_existing(self, temp_config_dir: Path) -> None:
        """Test that setting a value preserves existing values."""
        with patch("jefe.cli.config.get_config_file", return_value=temp_config_dir / "config.json"):
            set_config_value("key1", "value1")
            set_config_value("key2", "value2")
            config = load_config()
            assert config["key1"] == "value1"
            assert config["key2"] == "value2"


class TestVersionCommand:
    """Test version command."""

    def test_version_flag(self) -> None:
        """Test --version flag shows version."""
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "Jefe version" in result.stdout
        assert "0.1.0" in result.stdout

    def test_version_short_flag(self) -> None:
        """Test -v flag shows version."""
        result = runner.invoke(app, ["-v"])
        assert result.exit_code == 0
        assert "Jefe version" in result.stdout


class TestHelpCommand:
    """Test help command."""

    def test_help_flag(self) -> None:
        """Test --help flag shows help."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "Jefe - A comprehensive Git repository management system" in result.stdout
        assert "config" in result.stdout

    def test_config_help(self) -> None:
        """Test config --help shows config commands."""
        result = runner.invoke(app, ["config", "--help"])
        assert result.exit_code == 0
        assert "show" in result.stdout
        assert "set" in result.stdout


class TestConfigShowCommand:
    """Test config show command."""

    def test_config_show_empty(self, _mock_config_dir: None) -> None:
        """Test config show with no configuration."""
        result = runner.invoke(app, ["config", "show"])
        assert result.exit_code == 0
        assert "No configuration found" in result.stdout

    def test_config_show_with_values(self, temp_config_dir: Path, _mock_config_dir: None) -> None:
        """Test config show displays configuration values."""
        # Create config file with values
        config_file = temp_config_dir / "config.json"
        config_file.write_text(
            json.dumps(
                {"server_url": "http://localhost:8000", "api_key": "test123"}, indent=2
            )
        )

        result = runner.invoke(app, ["config", "show"])
        assert result.exit_code == 0
        assert "server_url" in result.stdout
        assert "http://localhost:8000" in result.stdout
        assert "api_key" in result.stdout
        assert "test123" in result.stdout


class TestConfigSetCommand:
    """Test config set command."""

    def test_config_set_value(self, _mock_config_dir: None) -> None:
        """Test config set creates new value."""
        result = runner.invoke(app, ["config", "set", "server_url", "http://localhost:8000"])
        assert result.exit_code == 0
        assert "Set server_url" in result.stdout
        assert "http://localhost:8000" in result.stdout

    def test_config_set_and_show(self, temp_config_dir: Path, _mock_config_dir: None) -> None:
        """Test that config set persists and can be shown."""
        # Set value
        result = runner.invoke(app, ["config", "set", "server_url", "http://localhost:8000"])
        assert result.exit_code == 0

        # Verify it was saved
        config_file = temp_config_dir / "config.json"
        assert config_file.exists()
        config = json.loads(config_file.read_text())
        assert config["server_url"] == "http://localhost:8000"

    def test_config_set_multiple_values(self, temp_config_dir: Path, _mock_config_dir: None) -> None:
        """Test setting multiple config values."""
        runner.invoke(app, ["config", "set", "server_url", "http://localhost:8000"])
        runner.invoke(app, ["config", "set", "api_key", "abc123"])

        config_file = temp_config_dir / "config.json"
        config = json.loads(config_file.read_text())
        assert config["server_url"] == "http://localhost:8000"
        assert config["api_key"] == "abc123"
