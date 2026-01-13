"""Tests for jefe projects init command."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from typer.testing import CliRunner

from jefe.cli.app import app

runner = CliRunner()


def _make_client(handler) -> httpx.AsyncClient:
    """Create a mock HTTP client with a custom request handler."""
    transport = httpx.MockTransport(handler)
    return httpx.AsyncClient(base_url="http://test", transport=transport)


@pytest.fixture
def mock_recipe_yaml(tmp_path: Path) -> Path:
    """Create a mock recipe YAML file."""
    recipe_file = tmp_path / "test-recipe.yaml"
    recipe_file.write_text("""name: test-recipe
description: Test recipe for unit tests
harnesses:
  - claude-code
skills:
  - source: test-source
    name: test-skill
    version: 1.0.0
bundles:
  - test-bundle
""")
    return recipe_file


@pytest.fixture
def mock_project_path(tmp_path: Path) -> Path:
    """Create a mock project directory."""
    project_dir = tmp_path / "test-project"
    project_dir.mkdir()
    return project_dir


def test_init_command_success(
    mock_recipe_yaml: Path,
    mock_project_path: Path,
) -> None:
    """Test successful project initialization with recipe."""
    call_count = [0]

    def handler(request: httpx.Request) -> httpx.Response:
        call_count[0] += 1
        if "/api/recipes/parse" in str(request.url):
            return httpx.Response(
                200,
                json={
                    "name": "test-recipe",
                    "description": "Test recipe",
                    "harnesses": ["claude-code"],
                    "skills": [
                        {
                            "source": "test-source",
                            "name": "test-skill",
                            "version": "1.0.0",
                            "pinned": False,
                        }
                    ],
                    "bundles": ["test-bundle"],
                    "skill_count": 1,
                    "bundle_count": 1,
                },
            )
        if request.url.path == "/api/projects" and request.method == "GET":
            return httpx.Response(200, json=[])
        if request.url.path == "/api/projects" and request.method == "POST":
            return httpx.Response(
                201,
                json={
                    "id": 1,
                    "name": "test-project",
                    "description": None,
                },
            )
        if "/api/recipes/resolve" in str(request.url):
            return httpx.Response(
                200,
                json={
                    "claude-code": [
                        {
                            "skill_id": 1,
                            "skill_name": "test-skill",
                            "source_name": "test-source",
                            "version": "1.0.0",
                            "pinned": False,
                        }
                    ]
                },
            )
        if "/api/harnesses" in str(request.url):
            return httpx.Response(
                200,
                json=[
                    {"id": 1, "name": "claude-code", "display_name": "Claude Code"}
                ],
            )
        if "/api/skills/install" in str(request.url):
            return httpx.Response(
                201,
                json={
                    "id": 1,
                    "skill_id": 1,
                    "harness_id": 1,
                    "scope": "project",
                    "project_id": 1,
                },
            )
        return httpx.Response(404, json={"detail": "Not found"})

    client = _make_client(handler)
    with (
        patch("jefe.cli.commands.projects.get_api_key", return_value="test-key"),
        patch("jefe.cli.commands.projects.create_client", return_value=client),
        patch("jefe.cli.commands.projects.is_online", new_callable=AsyncMock, return_value=True),
    ):
        result = runner.invoke(
            app,
            [
                "projects",
                "init",
                "--recipe",
                str(mock_recipe_yaml),
                "--path",
                str(mock_project_path),
                "--name",
                "test-project",
            ],
        )

    assert result.exit_code == 0, f"Failed with output: {result.stdout}"
    assert "Recipe: test-recipe" in result.stdout
    assert "Project: test-project" in result.stdout
    assert "Resolved 1 skills" in result.stdout
    assert "Installed 1 skill(s)" in result.stdout


def test_init_command_recipe_not_found() -> None:
    """Test init command with non-existent recipe file."""
    with patch("jefe.cli.commands.projects.get_api_key", return_value="test-key"):
        result = runner.invoke(
            app,
            [
                "projects",
                "init",
                "--recipe",
                "/nonexistent/recipe.yaml",
            ],
        )

    assert result.exit_code == 1
    assert "Recipe file not found" in result.stdout


def test_init_command_project_path_not_found(mock_recipe_yaml: Path) -> None:
    """Test init command with non-existent project path."""
    with patch("jefe.cli.commands.projects.get_api_key", return_value="test-key"):
        result = runner.invoke(
            app,
            [
                "projects",
                "init",
                "--recipe",
                str(mock_recipe_yaml),
                "--path",
                "/nonexistent/path",
            ],
        )

    assert result.exit_code == 1
    assert "Project path does not exist" in result.stdout


def test_init_command_offline(mock_recipe_yaml: Path) -> None:
    """Test init command when server is offline."""
    with (
        patch("jefe.cli.commands.projects.get_api_key", return_value="test-key"),
        patch("jefe.cli.commands.projects.is_online", new_callable=AsyncMock, return_value=False),
    ):
        result = runner.invoke(
            app,
            [
                "projects",
                "init",
                "--recipe",
                str(mock_recipe_yaml),
            ],
        )

    assert result.exit_code == 1
    assert "Init command requires server connection" in result.stdout


def test_init_command_existing_project(
    mock_recipe_yaml: Path,
    mock_project_path: Path,
) -> None:
    """Test init command with existing project."""

    def handler(request: httpx.Request) -> httpx.Response:
        if "/api/recipes/parse" in str(request.url):
            return httpx.Response(
                200,
                json={
                    "name": "test-recipe",
                    "description": "Test recipe",
                    "harnesses": ["claude-code"],
                    "skills": [],
                    "bundles": [],
                    "skill_count": 0,
                    "bundle_count": 0,
                },
            )
        if request.url.path == "/api/projects" and request.method == "GET":
            return httpx.Response(
                200, json=[{"id": 1, "name": "test-project", "description": None}]
            )
        if "/api/recipes/resolve" in str(request.url):
            return httpx.Response(200, json={"claude-code": []})
        if "/api/harnesses" in str(request.url):
            return httpx.Response(
                200,
                json=[
                    {"id": 1, "name": "claude-code", "display_name": "Claude Code"}
                ],
            )
        return httpx.Response(404, json={"detail": "Not found"})

    client = _make_client(handler)
    with (
        patch("jefe.cli.commands.projects.get_api_key", return_value="test-key"),
        patch("jefe.cli.commands.projects.create_client", return_value=client),
        patch("jefe.cli.commands.projects.is_online", new_callable=AsyncMock, return_value=True),
    ):
        result = runner.invoke(
            app,
            [
                "projects",
                "init",
                "--recipe",
                str(mock_recipe_yaml),
                "--path",
                str(mock_project_path),
                "--name",
                "test-project",
            ],
        )

    assert result.exit_code == 0
    assert "Project: test-project" in result.stdout


def test_init_command_no_api_key() -> None:
    """Test init command without API key configured."""
    with patch("jefe.cli.commands.projects.get_api_key", return_value=None):
        result = runner.invoke(
            app,
            [
                "projects",
                "init",
                "--recipe",
                "recipe.yaml",
            ],
        )

    assert result.exit_code == 1
    assert "API key not configured" in result.stdout
