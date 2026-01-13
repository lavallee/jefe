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
        assert request.url.path == "/api/status"
        return httpx.Response(
            200,
            json={"projects": 1, "manifestations": 1, "configs": 2, "harnesses": 1},
        )

    client = _make_client(handler)
    with (
        patch("jefe.cli.commands.status.get_api_key", return_value="key"),
        patch("jefe.cli.commands.status.create_client", return_value=client),
    ):
        result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    assert "Projects" in result.stdout
