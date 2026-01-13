"""Tests for harness CLI commands."""

from pathlib import Path
from unittest.mock import patch

import httpx
from typer.testing import CliRunner

from jefe.cli import app

runner = CliRunner()


def _make_client(handler) -> httpx.AsyncClient:
    transport = httpx.MockTransport(handler)
    return httpx.AsyncClient(base_url="http://test", transport=transport)


async def mock_is_online_true() -> bool:
    """Mock is_online that returns True."""
    return True


def test_harnesses_list_command() -> None:
    """List harnesses via CLI."""
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/harnesses"
        return httpx.Response(
            200,
            json=[
                {
                    "id": 1,
                    "name": "claude-code",
                    "display_name": "Claude Code",
                    "version": "1.2.3",
                }
            ],
        )

    client = _make_client(handler)
    with (
        patch("jefe.cli.commands.harnesses.get_api_key", return_value="key"),
        patch("jefe.cli.commands.harnesses.create_client", return_value=client),
        patch("jefe.cli.commands.harnesses.is_online", mock_is_online_true),
    ):
        result = runner.invoke(app, ["harnesses", "list"])

    assert result.exit_code == 0
    assert "claude-code" in result.stdout
    assert "Claude Code" in result.stdout


def test_harnesses_show_command() -> None:
    """Show harness details and configs via CLI."""
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/harnesses/claude-code":
            return httpx.Response(
                200,
                json={
                    "name": "claude-code",
                    "display_name": "Claude Code",
                    "version": "1.2.3",
                },
            )
        assert request.url.path == "/api/harnesses/claude-code/configs"
        return httpx.Response(
            200,
            json=[
                {
                    "harness": "claude-code",
                    "scope": "project",
                    "kind": "instructions",
                    "path": "/tmp/project/CLAUDE.md",
                    "content": "# Instructions",
                    "project_id": 1,
                    "project_name": "demo",
                }
            ],
        )

    client = _make_client(handler)
    with (
        patch("jefe.cli.commands.harnesses.get_api_key", return_value="key"),
        patch("jefe.cli.commands.harnesses.create_client", return_value=client),
    ):
        result = runner.invoke(app, ["harnesses", "show", "claude-code"])

    assert result.exit_code == 0
    assert "Claude Code" in result.stdout
    assert "claude-code" in result.stdout
    assert "Instructions" in result.stdout


def test_harnesses_discover_command_with_project(tmp_path: Path) -> None:
    """Discover configs via CLI with project path filtering."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/projects":
            return httpx.Response(
                200,
                json=[
                    {
                        "id": 1,
                        "name": "demo",
                        "description": None,
                        "manifestations": [
                            {"id": 7, "type": "local", "path": str(project_dir)}
                        ],
                    }
                ],
            )
        assert request.url.path == "/api/harnesses/discover"
        assert request.url.params.get("project_id") == "1"
        return httpx.Response(
            200,
            json=[
                {
                    "harness": "claude-code",
                    "scope": "project",
                    "kind": "instructions",
                    "path": str(project_dir / "CLAUDE.md"),
                    "content": "# Instructions",
                    "project_id": 1,
                    "project_name": "demo",
                }
            ],
        )

    client = _make_client(handler)
    with (
        patch("jefe.cli.commands.harnesses.get_api_key", return_value="key"),
        patch("jefe.cli.commands.harnesses.create_client", return_value=client),
    ):
        result = runner.invoke(
            app,
            ["harnesses", "discover", "--project", str(project_dir)],
        )

    assert result.exit_code == 0
    assert "claude-code" in result.stdout
    assert "Instructions" in result.stdout
