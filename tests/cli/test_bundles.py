"""Tests for bundles CLI commands."""

from unittest.mock import patch

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


def test_bundles_list_command() -> None:
    """List bundles via CLI."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/bundles"
        return httpx.Response(
            200,
            json=[
                {
                    "id": 1,
                    "name": "web-dev",
                    "display_name": "Web Development Bundle",
                    "description": "Essential web development skills",
                    "skill_refs": [
                        {"source": "official", "name": "html-helper"},
                        {"source": "official", "name": "css-helper"},
                    ],
                },
                {
                    "id": 2,
                    "name": "git-tools",
                    "display_name": "Git Tools Bundle",
                    "description": "Git workflow helpers",
                    "skill_refs": [
                        {"source": "official", "name": "git-commit"},
                    ],
                },
            ],
        )

    client = _make_client(handler)
    with (
        patch("jefe.cli.commands.bundles.get_api_key", return_value="key"),
        patch("jefe.cli.commands.bundles.create_client", return_value=client),
    ):
        result = runner.invoke(app, ["bundles", "list"])

    assert result.exit_code == 0
    assert "web-dev" in result.stdout
    assert "git-tools" in result.stdout
    assert "2" in result.stdout  # skill count for web-dev
    assert "1" in result.stdout  # skill count for git-tools


def test_bundles_list_empty() -> None:
    """List bundles when none available."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    client = _make_client(handler)
    with (
        patch("jefe.cli.commands.bundles.get_api_key", return_value="key"),
        patch("jefe.cli.commands.bundles.create_client", return_value=client),
    ):
        result = runner.invoke(app, ["bundles", "list"])

    assert result.exit_code == 0
    assert "No bundles available" in result.stdout


def test_bundles_show_command_by_name() -> None:
    """Show bundle details by name via CLI."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/bundles":
            return httpx.Response(
                200,
                json=[
                    {
                        "id": 1,
                        "name": "web-dev",
                        "display_name": "Web Development Bundle",
                        "description": "Essential web development skills",
                        "skill_refs": [
                            {"source": "official", "name": "html-helper"},
                            {"source": "official", "name": "css-helper"},
                        ],
                    }
                ],
            )
        elif request.url.path == "/api/bundles/1":
            return httpx.Response(
                200,
                json={
                    "id": 1,
                    "name": "web-dev",
                    "display_name": "Web Development Bundle",
                    "description": "Essential web development skills",
                    "skill_refs": [
                        {"source": "official", "name": "html-helper"},
                        {"source": "official", "name": "css-helper"},
                    ],
                },
            )
        return httpx.Response(404)

    client = _make_client(handler)
    with (
        patch("jefe.cli.commands.bundles.get_api_key", return_value="key"),
        patch("jefe.cli.commands.bundles.create_client", return_value=client),
    ):
        result = runner.invoke(app, ["bundles", "show", "web-dev"])

    assert result.exit_code == 0
    assert "web-dev" in result.stdout
    assert "Web Development Bundle" in result.stdout
    assert "official/html-helper" in result.stdout
    assert "official/css-helper" in result.stdout


def test_bundles_show_command_by_id() -> None:
    """Show bundle details by ID via CLI."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/bundles/1":
            return httpx.Response(
                200,
                json={
                    "id": 1,
                    "name": "web-dev",
                    "display_name": "Web Development Bundle",
                    "description": "Essential web development skills",
                    "skill_refs": [
                        {"source": "official", "name": "html-helper"},
                    ],
                },
            )
        return httpx.Response(404)

    client = _make_client(handler)
    with (
        patch("jefe.cli.commands.bundles.get_api_key", return_value="key"),
        patch("jefe.cli.commands.bundles.create_client", return_value=client),
    ):
        result = runner.invoke(app, ["bundles", "show", "1"])

    assert result.exit_code == 0
    assert "web-dev" in result.stdout


def test_bundles_show_not_found() -> None:
    """Show bundle that doesn't exist."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    client = _make_client(handler)
    with (
        patch("jefe.cli.commands.bundles.get_api_key", return_value="key"),
        patch("jefe.cli.commands.bundles.create_client", return_value=client),
    ):
        result = runner.invoke(app, ["bundles", "show", "nonexistent"])

    assert result.exit_code == 1
    assert "not found" in result.stdout


def test_bundles_apply_global() -> None:
    """Apply bundle globally via CLI."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/bundles":
            return httpx.Response(
                200,
                json=[
                    {
                        "id": 1,
                        "name": "web-dev",
                        "display_name": "Web Development Bundle",
                        "description": "Essential web development skills",
                        "skill_refs": [
                            {"source": "official", "name": "html-helper"},
                        ],
                    }
                ],
            )
        elif request.url.path == "/api/harnesses":
            return httpx.Response(
                200,
                json=[
                    {"id": 1, "name": "claude-code", "display_name": "Claude Code", "version": "1.0"}
                ],
            )
        elif request.url.path == "/api/bundles/1/apply":
            return httpx.Response(
                200,
                json={
                    "success_count": 1,
                    "failed_count": 0,
                    "errors": [],
                },
            )
        return httpx.Response(404)

    client = _make_client(handler)
    with (
        patch("jefe.cli.commands.bundles.get_api_key", return_value="key"),
        patch("jefe.cli.commands.bundles.create_client", return_value=client),
    ):
        result = runner.invoke(
            app, ["bundles", "apply", "web-dev", "--harness", "claude-code", "--global"]
        )

    assert result.exit_code == 0
    assert "Successfully installed 1 skill(s)" in result.stdout
    assert "globally" in result.stdout


def test_bundles_apply_to_project() -> None:
    """Apply bundle to project via CLI."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/bundles":
            return httpx.Response(
                200,
                json=[
                    {
                        "id": 1,
                        "name": "web-dev",
                        "display_name": "Web Development Bundle",
                        "description": "Essential web development skills",
                        "skill_refs": [
                            {"source": "official", "name": "html-helper"},
                            {"source": "official", "name": "css-helper"},
                        ],
                    }
                ],
            )
        elif request.url.path == "/api/harnesses":
            return httpx.Response(
                200,
                json=[
                    {"id": 1, "name": "claude-code", "display_name": "Claude Code", "version": "1.0"}
                ],
            )
        elif request.url.path == "/api/projects":
            return httpx.Response(
                200,
                json=[
                    {"id": 1, "name": "my-project", "path": "/path/to/project"}
                ],
            )
        elif request.url.path == "/api/bundles/1/apply":
            return httpx.Response(
                200,
                json={
                    "success_count": 2,
                    "failed_count": 0,
                    "errors": [],
                },
            )
        return httpx.Response(404)

    client = _make_client(handler)
    with (
        patch("jefe.cli.commands.bundles.get_api_key", return_value="key"),
        patch("jefe.cli.commands.bundles.create_client", return_value=client),
    ):
        result = runner.invoke(
            app,
            ["bundles", "apply", "web-dev", "--harness", "claude-code", "--project", "my-project"],
        )

    assert result.exit_code == 0
    assert "Successfully installed 2 skill(s)" in result.stdout
    assert "to project 'my-project'" in result.stdout


def test_bundles_apply_with_failures() -> None:
    """Apply bundle with some failures."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/bundles":
            return httpx.Response(
                200,
                json=[
                    {
                        "id": 1,
                        "name": "test-bundle",
                        "display_name": "Test Bundle",
                        "description": "Test bundle",
                        "skill_refs": [
                            {"source": "official", "name": "skill1"},
                            {"source": "official", "name": "skill2"},
                        ],
                    }
                ],
            )
        elif request.url.path == "/api/harnesses":
            return httpx.Response(
                200,
                json=[
                    {"id": 1, "name": "claude-code", "display_name": "Claude Code", "version": "1.0"}
                ],
            )
        elif request.url.path == "/api/bundles/1/apply":
            return httpx.Response(
                200,
                json={
                    "success_count": 1,
                    "failed_count": 1,
                    "errors": ["Failed to install skill2: not found"],
                },
            )
        return httpx.Response(404)

    client = _make_client(handler)
    with (
        patch("jefe.cli.commands.bundles.get_api_key", return_value="key"),
        patch("jefe.cli.commands.bundles.create_client", return_value=client),
    ):
        result = runner.invoke(
            app, ["bundles", "apply", "test-bundle", "--harness", "claude-code", "--global"]
        )

    assert result.exit_code == 0
    assert "Successfully installed 1 skill(s)" in result.stdout
    assert "Failed to install 1 skill(s)" in result.stdout
    assert "Failed to install skill2: not found" in result.stdout


def test_bundles_apply_requires_scope() -> None:
    """Apply bundle without specifying scope."""

    with patch("jefe.cli.commands.bundles.get_api_key", return_value="key"):
        result = runner.invoke(app, ["bundles", "apply", "test-bundle", "--harness", "claude-code"])

    assert result.exit_code == 1
    assert "Must specify either --global or --project" in result.stdout


def test_bundles_apply_requires_one_scope() -> None:
    """Apply bundle with both global and project."""

    with patch("jefe.cli.commands.bundles.get_api_key", return_value="key"):
        result = runner.invoke(
            app,
            [
                "bundles",
                "apply",
                "test-bundle",
                "--harness",
                "claude-code",
                "--global",
                "--project",
                "my-project",
            ],
        )

    assert result.exit_code == 1
    assert "Cannot specify both --global and --project" in result.stdout


def test_bundles_list_requires_api_key() -> None:
    """List bundles without API key."""

    with patch("jefe.cli.commands.bundles.get_api_key", return_value=None):
        result = runner.invoke(app, ["bundles", "list"])

    assert result.exit_code == 1
    assert "API key not configured" in result.stdout


def test_bundles_show_requires_api_key() -> None:
    """Show bundle without API key."""

    with patch("jefe.cli.commands.bundles.get_api_key", return_value=None):
        result = runner.invoke(app, ["bundles", "show", "test"])

    assert result.exit_code == 1
    assert "API key not configured" in result.stdout


def test_bundles_apply_requires_api_key() -> None:
    """Apply bundle without API key."""

    with patch("jefe.cli.commands.bundles.get_api_key", return_value=None):
        result = runner.invoke(
            app, ["bundles", "apply", "test", "--harness", "claude-code", "--global"]
        )

    assert result.exit_code == 1
    assert "API key not configured" in result.stdout
