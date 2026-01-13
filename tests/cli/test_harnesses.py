"""Tests for harness CLI commands."""

from unittest.mock import patch

import httpx
from typer.testing import CliRunner

from jefe.cli import app

runner = CliRunner()


def _make_client(handler) -> httpx.AsyncClient:
    transport = httpx.MockTransport(handler)
    return httpx.AsyncClient(base_url="http://test", transport=transport)


def test_harnesses_discover_command() -> None:
    """Discover configs via CLI."""
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/harnesses/discover"
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
        result = runner.invoke(app, ["harnesses", "discover"])

    assert result.exit_code == 0
    assert "claude-code" in result.stdout
