"""Tests for status CLI command."""

from unittest.mock import patch

import httpx
from typer.testing import CliRunner

from jefe.cli import app

runner = CliRunner()


def _make_client(handler) -> httpx.AsyncClient:
    transport = httpx.MockTransport(handler)
    return httpx.AsyncClient(base_url="http://test", transport=transport)


def test_status_command() -> None:
    """Show status via CLI."""
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return httpx.Response(200, json={"status": "healthy", "version": "1.0.0"})
        if request.url.path == "/api/status":
            return httpx.Response(
                200,
                json={"projects": 1, "manifestations": 1, "configs": 2, "harnesses": 1},
            )
        if request.url.path == "/api/projects":
            return httpx.Response(
                200,
                json=[
                    {
                        "id": 1,
                        "name": "demo",
                        "description": None,
                        "manifestations": [
                            {
                                "id": 7,
                                "type": "local",
                                "path": "/tmp/demo",
                                "last_seen": "2026-01-12T10:00:00+00:00",
                            }
                        ],
                    }
                ],
            )
        if request.url.path == "/api/harnesses":
            return httpx.Response(
                200,
                json=[{"name": "claude-code", "display_name": "Claude Code", "version": "1"}],
            )
        if request.url.path == "/api/harnesses/claude-code/configs":
            return httpx.Response(
                200,
                json=[
                    {
                        "harness": "claude-code",
                        "scope": "project",
                        "kind": "instructions",
                        "path": "/tmp/demo/CLAUDE.md",
                        "project_id": 1,
                        "project_name": "demo",
                    }
                ],
            )
        raise AssertionError(f"Unexpected path: {request.url.path}")

    client = _make_client(handler)
    with (
        patch("jefe.cli.commands.status.get_api_key", return_value="key"),
        patch("jefe.cli.commands.status.create_client", return_value=client),
        patch("jefe.cli.commands.status.set_config_value"),
    ):
        result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    assert "Online" in result.stdout
    assert "Projects" in result.stdout
    assert "claude-code" in result.stdout


def test_status_command_project() -> None:
    """Show project status via CLI."""
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return httpx.Response(200, json={"status": "healthy", "version": "1.0.0"})
        if request.url.path == "/api/status":
            return httpx.Response(
                200,
                json={"projects": 1, "manifestations": 1, "configs": 1, "harnesses": 1},
            )
        if request.url.path == "/api/projects":
            return httpx.Response(
                200,
                json=[{"id": 1, "name": "demo", "description": None, "manifestations": []}],
            )
        if request.url.path == "/api/projects/1":
            return httpx.Response(
                200,
                json={
                    "id": 1,
                    "name": "demo",
                    "description": "Demo project",
                    "manifestations": [],
                    "configs": [
                        {
                            "harness": "claude-code",
                            "scope": "project",
                            "kind": "instructions",
                            "path": "/tmp/demo/CLAUDE.md",
                        }
                    ],
                },
            )
        if request.url.path == "/api/harnesses":
            return httpx.Response(
                200,
                json=[{"name": "claude-code", "display_name": "Claude Code", "version": "1"}],
            )
        if request.url.path == "/api/harnesses/claude-code/configs":
            return httpx.Response(200, json=[])
        raise AssertionError(f"Unexpected path: {request.url.path}")

    client = _make_client(handler)
    with (
        patch("jefe.cli.commands.status.get_api_key", return_value="key"),
        patch("jefe.cli.commands.status.create_client", return_value=client),
        patch("jefe.cli.commands.status.set_config_value"),
    ):
        result = runner.invoke(app, ["status", "--project", "demo"])

    assert result.exit_code == 0
    assert "Project" in result.stdout
    assert "demo" in result.stdout
    assert "Project Configs" in result.stdout


def test_status_command_offline_uses_cache() -> None:
    """Use cached status when offline."""
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    cached = {
        "timestamp": "2026-01-12T11:00:00",
        "health": {"status_code": 200, "payload": {"version": "1.0.0"}},
        "overview": {"projects": 2, "manifestations": 3, "configs": 4, "harnesses": 1},
        "projects": [
            {
                "id": 1,
                "name": "demo",
                "description": None,
                "manifestations": [
                    {
                        "id": 7,
                        "type": "local",
                        "path": "/tmp/demo",
                        "last_seen": "2026-01-12T10:00:00+00:00",
                    }
                ],
            }
        ],
        "harnesses": [
            {"name": "claude-code", "display_name": "Claude Code", "version": "1"}
        ],
        "harness_configs": {"claude-code": []},
        "project_details": {},
    }

    client = _make_client(handler)
    with (
        patch("jefe.cli.commands.status.get_api_key", return_value="key"),
        patch("jefe.cli.commands.status.create_client", return_value=client),
        patch("jefe.cli.commands.status.get_config_value", return_value=cached),
    ):
        result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    assert "Offline" in result.stdout
    assert "cached" in result.stdout.lower()
