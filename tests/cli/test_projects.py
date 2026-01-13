"""Tests for project CLI commands."""

import json
from pathlib import Path
from unittest.mock import patch

import httpx
from typer.testing import CliRunner

from jefe.cli import app

runner = CliRunner()


def _make_client(handler) -> httpx.Client:
    transport = httpx.MockTransport(handler)
    return httpx.Client(base_url="http://test", transport=transport)


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
    ):
        result = runner.invoke(
            app,
            ["projects", "add", "demo", "--path", str(project_dir)],
        )

    assert result.exit_code == 0
    assert "Created project demo" in result.stdout
