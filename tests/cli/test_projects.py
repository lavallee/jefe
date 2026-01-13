"""Tests for project CLI commands."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from typer.testing import CliRunner

from jefe.cli import app
from jefe.cli.client import clear_online_cache

runner = CliRunner()


@pytest.fixture(autouse=True)
def reset_online_cache():
    """Reset the online cache before each test."""
    clear_online_cache()
    yield
    clear_online_cache()


def _make_client(handler) -> httpx.AsyncClient:
    transport = httpx.MockTransport(handler)
    return httpx.AsyncClient(base_url="http://test", transport=transport)


def test_projects_list_command() -> None:
    """List projects via CLI."""
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/projects"
        return httpx.Response(
            200,
            json=[{"id": 1, "name": "demo", "description": None, "manifestations": []}],
        )

    client = _make_client(handler)
    with (
        patch("jefe.cli.commands.projects.get_api_key", return_value="key"),
        patch("jefe.cli.commands.projects.create_client", return_value=client),
        patch("jefe.cli.commands.projects.is_online", new_callable=AsyncMock, return_value=True),
    ):
        result = runner.invoke(app, ["projects", "list"])

    assert result.exit_code == 0
    assert "demo" in result.stdout


def test_projects_add_command(tmp_path: Path) -> None:
    """Add project via CLI."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/projects"
        payload = json.loads(request.content.decode())
        assert payload["name"] == "demo"
        assert payload["path"] == str(project_dir)
        return httpx.Response(
            201,
            json={
                "id": 1,
                "name": "demo",
                "description": None,
                "manifestations": [],
            },
        )

    client = _make_client(handler)
    with (
        patch("jefe.cli.commands.projects.get_api_key", return_value="key"),
        patch("jefe.cli.commands.projects.create_client", return_value=client),
        patch("jefe.cli.commands.projects.is_online", new_callable=AsyncMock, return_value=True),
    ):
        result = runner.invoke(
            app,
            ["projects", "add", "demo", "--path", str(project_dir)],
        )

    assert result.exit_code == 0
    assert "Created project demo" in result.stdout


def test_projects_add_with_remote_command(tmp_path: Path) -> None:
    """Add project with remote manifestation."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/projects":
            payload = json.loads(request.content.decode())
            assert payload["name"] == "demo"
            assert payload["path"] == str(project_dir)
            return httpx.Response(
                201,
                json={
                    "id": 1,
                    "name": "demo",
                    "description": None,
                    "manifestations": [],
                },
            )
        assert request.url.path == "/api/projects/1/manifestations"
        payload = json.loads(request.content.decode())
        assert payload["type"] == "remote"
        assert payload["path"] == "https://example.com/repo.git"
        return httpx.Response(201, json={"id": 5})

    client = _make_client(handler)
    with (
        patch("jefe.cli.commands.projects.get_api_key", return_value="key"),
        patch("jefe.cli.commands.projects.create_client", return_value=client),
        patch("jefe.cli.commands.projects.is_online", new_callable=AsyncMock, return_value=True),
    ):
        result = runner.invoke(
            app,
            [
                "projects",
                "add",
                "demo",
                "--path",
                str(project_dir),
                "--remote",
                "https://example.com/repo.git",
            ],
        )

    assert result.exit_code == 0
    assert "Added remote https://example.com/repo.git" in result.stdout


def test_projects_show_command() -> None:
    """Show project via CLI."""
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/projects":
            return httpx.Response(200, json=[{"id": 1, "name": "demo", "manifestations": []}])
        assert request.url.path == "/api/projects/1"
        return httpx.Response(
            200,
            json={
                "id": 1,
                "name": "demo",
                "description": "Demo project",
                "manifestations": [],
                "configs": [],
            },
        )

    client = _make_client(handler)
    with (
        patch("jefe.cli.commands.projects.get_api_key", return_value="key"),
        patch("jefe.cli.commands.projects.create_client", return_value=client),
        patch("jefe.cli.commands.projects.is_online", new_callable=AsyncMock, return_value=True),
    ):
        result = runner.invoke(app, ["projects", "show", "demo"])

    assert result.exit_code == 0
    assert "Demo project" in result.stdout


def test_projects_remove_command() -> None:
    """Remove project via CLI."""
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/projects":
            return httpx.Response(200, json=[{"id": 1, "name": "demo", "manifestations": []}])
        assert request.url.path == "/api/projects/1"
        assert request.method == "DELETE"
        return httpx.Response(204)

    client = _make_client(handler)
    with (
        patch("jefe.cli.commands.projects.get_api_key", return_value="key"),
        patch("jefe.cli.commands.projects.create_client", return_value=client),
    ):
        result = runner.invoke(app, ["projects", "remove", "demo"])

    assert result.exit_code == 0
    assert "Removed project demo" in result.stdout


def test_projects_connection_error() -> None:
    """Show offline mode when server is unreachable."""
    # When is_online returns False, we get offline mode with cached data
    with (
        patch("jefe.cli.commands.projects.get_api_key", return_value="key"),
        patch("jefe.cli.commands.projects.is_online", new_callable=AsyncMock, return_value=False),
        patch("jefe.cli.commands.projects.CacheManager") as mock_cache_cls,
    ):
        mock_cache = mock_cache_cls.return_value
        mock_cache.get_all_projects.return_value = []
        result = runner.invoke(app, ["projects", "list"])

    assert result.exit_code == 0
    assert "Offline mode" in result.stdout
