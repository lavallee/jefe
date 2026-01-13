"""Tests for sources CLI commands."""

import json
from unittest.mock import patch

import httpx
from typer.testing import CliRunner

from jefe.cli import app

runner = CliRunner()


def _make_client(handler) -> httpx.AsyncClient:
    transport = httpx.MockTransport(handler)
    return httpx.AsyncClient(base_url="http://test", transport=transport)


def test_sources_list_command() -> None:
    """List sources via CLI."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/sources"
        return httpx.Response(
            200,
            json=[
                {
                    "id": 1,
                    "name": "anthropic-skills",
                    "source_type": "git",
                    "url": "https://github.com/anthropics/skills",
                    "description": None,
                    "sync_status": "synced",
                    "last_synced_at": "2026-01-12T12:00:00",
                }
            ],
        )

    client = _make_client(handler)
    with (
        patch("jefe.cli.commands.sources.get_api_key", return_value="key"),
        patch("jefe.cli.commands.sources.create_client", return_value=client),
    ):
        result = runner.invoke(app, ["sources", "list"])

    assert result.exit_code == 0
    assert "anthropic-skills" in result.stdout
    assert "synced" in result.stdout


def test_sources_list_empty() -> None:
    """List sources when none exist."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/sources"
        return httpx.Response(200, json=[])

    client = _make_client(handler)
    with (
        patch("jefe.cli.commands.sources.get_api_key", return_value="key"),
        patch("jefe.cli.commands.sources.create_client", return_value=client),
    ):
        result = runner.invoke(app, ["sources", "list"])

    assert result.exit_code == 0
    assert "No sources configured" in result.stdout


def test_sources_add_command() -> None:
    """Add source via CLI."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/sources"
        payload = json.loads(request.content.decode())
        assert payload["name"] == "anthropic-skills"
        assert payload["source_type"] == "git"
        assert payload["url"] == "https://github.com/anthropics/skills"
        return httpx.Response(
            201,
            json={
                "id": 1,
                "name": "anthropic-skills",
                "source_type": "git",
                "url": "https://github.com/anthropics/skills",
                "description": None,
                "sync_status": "pending",
                "last_synced_at": None,
            },
        )

    client = _make_client(handler)
    with (
        patch("jefe.cli.commands.sources.get_api_key", return_value="key"),
        patch("jefe.cli.commands.sources.create_client", return_value=client),
    ):
        result = runner.invoke(
            app,
            ["sources", "add", "anthropic-skills", "https://github.com/anthropics/skills"],
        )

    assert result.exit_code == 0
    assert "Created source anthropic-skills" in result.stdout
    assert "sc sources sync" in result.stdout


def test_sources_add_with_description() -> None:
    """Add source with description via CLI."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/sources"
        payload = json.loads(request.content.decode())
        assert payload["name"] == "test-source"
        assert payload["description"] == "Test description"
        return httpx.Response(
            201,
            json={
                "id": 1,
                "name": "test-source",
                "source_type": "git",
                "url": "https://example.com/repo.git",
                "description": "Test description",
                "sync_status": "pending",
                "last_synced_at": None,
            },
        )

    client = _make_client(handler)
    with (
        patch("jefe.cli.commands.sources.get_api_key", return_value="key"),
        patch("jefe.cli.commands.sources.create_client", return_value=client),
    ):
        result = runner.invoke(
            app,
            [
                "sources",
                "add",
                "test-source",
                "https://example.com/repo.git",
                "--description",
                "Test description",
            ],
        )

    assert result.exit_code == 0
    assert "Created source test-source" in result.stdout


def test_sources_sync_single() -> None:
    """Sync single source via CLI."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/sources":
            return httpx.Response(
                200,
                json=[
                    {
                        "id": 1,
                        "name": "anthropic-skills",
                        "source_type": "git",
                        "url": "https://github.com/anthropics/skills",
                    }
                ],
            )
        assert request.url.path == "/api/sources/1/sync"
        return httpx.Response(
            200,
            json={"message": "Sync completed successfully", "skills_updated": 5},
        )

    client = _make_client(handler)
    with (
        patch("jefe.cli.commands.sources.get_api_key", return_value="key"),
        patch("jefe.cli.commands.sources.create_client", return_value=client),
    ):
        result = runner.invoke(app, ["sources", "sync", "anthropic-skills"])

    assert result.exit_code == 0
    assert "Sync completed successfully" in result.stdout
    assert "Skills updated: 5" in result.stdout


def test_sources_sync_single_by_id() -> None:
    """Sync source by ID via CLI."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/sources/1/sync"
        return httpx.Response(
            200,
            json={"message": "Sync completed successfully", "skills_updated": 3},
        )

    client = _make_client(handler)
    with (
        patch("jefe.cli.commands.sources.get_api_key", return_value="key"),
        patch("jefe.cli.commands.sources.create_client", return_value=client),
    ):
        result = runner.invoke(app, ["sources", "sync", "1"])

    assert result.exit_code == 0
    assert "Sync completed successfully" in result.stdout
    assert "Skills updated: 3" in result.stdout


def test_sources_sync_all() -> None:
    """Sync all sources via CLI."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/sources":
            return httpx.Response(
                200,
                json=[
                    {"id": 1, "name": "source1"},
                    {"id": 2, "name": "source2"},
                ],
            )
        if request.url.path == "/api/sources/1/sync":
            return httpx.Response(
                200,
                json={"message": "Sync completed successfully", "skills_updated": 2},
            )
        if request.url.path == "/api/sources/2/sync":
            return httpx.Response(
                200,
                json={"message": "Sync completed successfully", "skills_updated": 3},
            )
        raise AssertionError(f"Unexpected path: {request.url.path}")

    client = _make_client(handler)
    with (
        patch("jefe.cli.commands.sources.get_api_key", return_value="key"),
        patch("jefe.cli.commands.sources.create_client", return_value=client),
    ):
        result = runner.invoke(app, ["sources", "sync"])

    assert result.exit_code == 0
    assert "Syncing 2 source(s)" in result.stdout
    assert "All sources synced successfully" in result.stdout


def test_sources_sync_all_with_failures() -> None:
    """Sync all sources with some failures."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/sources":
            return httpx.Response(
                200,
                json=[
                    {"id": 1, "name": "source1"},
                    {"id": 2, "name": "source2"},
                ],
            )
        if request.url.path == "/api/sources/1/sync":
            return httpx.Response(
                200,
                json={"message": "Sync completed successfully", "skills_updated": 2},
            )
        if request.url.path == "/api/sources/2/sync":
            return httpx.Response(400, text="Invalid source type")
        raise AssertionError(f"Unexpected path: {request.url.path}")

    client = _make_client(handler)
    with (
        patch("jefe.cli.commands.sources.get_api_key", return_value="key"),
        patch("jefe.cli.commands.sources.create_client", return_value=client),
    ):
        result = runner.invoke(app, ["sources", "sync"])

    assert result.exit_code == 0
    assert "Failed to sync: source2" in result.stdout


def test_sources_sync_empty() -> None:
    """Sync all sources when none exist."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/sources"
        return httpx.Response(200, json=[])

    client = _make_client(handler)
    with (
        patch("jefe.cli.commands.sources.get_api_key", return_value="key"),
        patch("jefe.cli.commands.sources.create_client", return_value=client),
    ):
        result = runner.invoke(app, ["sources", "sync"])

    assert result.exit_code == 0
    assert "No sources to sync" in result.stdout


def test_sources_remove_command() -> None:
    """Remove source via CLI."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/sources":
            return httpx.Response(
                200,
                json=[
                    {
                        "id": 1,
                        "name": "anthropic-skills",
                        "source_type": "git",
                        "url": "https://github.com/anthropics/skills",
                    }
                ],
            )
        assert request.url.path == "/api/sources/1"
        assert request.method == "DELETE"
        return httpx.Response(204)

    client = _make_client(handler)
    with (
        patch("jefe.cli.commands.sources.get_api_key", return_value="key"),
        patch("jefe.cli.commands.sources.create_client", return_value=client),
    ):
        result = runner.invoke(app, ["sources", "remove", "anthropic-skills"])

    assert result.exit_code == 0
    assert "Removed source anthropic-skills" in result.stdout


def test_sources_remove_by_id() -> None:
    """Remove source by ID via CLI."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/sources/1"
        assert request.method == "DELETE"
        return httpx.Response(204)

    client = _make_client(handler)
    with (
        patch("jefe.cli.commands.sources.get_api_key", return_value="key"),
        patch("jefe.cli.commands.sources.create_client", return_value=client),
    ):
        result = runner.invoke(app, ["sources", "remove", "1"])

    assert result.exit_code == 0
    assert "Removed source 1" in result.stdout


def test_sources_list_requires_api_key() -> None:
    """List sources requires API key."""
    with patch("jefe.cli.commands.sources.get_api_key", return_value=None):
        result = runner.invoke(app, ["sources", "list"])

    assert result.exit_code == 1
    assert "API key not configured" in result.stdout


def test_sources_add_requires_api_key() -> None:
    """Add source requires API key."""
    with patch("jefe.cli.commands.sources.get_api_key", return_value=None):
        result = runner.invoke(app, ["sources", "add", "test", "http://example.com"])

    assert result.exit_code == 1
    assert "API key not configured" in result.stdout
