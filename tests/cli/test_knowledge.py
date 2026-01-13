"""Tests for knowledge CLI commands."""

from unittest.mock import AsyncMock, patch

import httpx
from typer.testing import CliRunner

from jefe.cli import app

runner = CliRunner()


def _make_client(handler) -> httpx.AsyncClient:
    """Create a mock HTTP client with a custom request handler."""
    transport = httpx.MockTransport(handler)
    return httpx.AsyncClient(base_url="http://test", transport=transport)


def test_knowledge_ingest_command():
    """Test ingesting a URL via CLI."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/knowledge/ingest":
            assert request.method == "POST"
            body = request.read()
            # Verify the request payload
            assert b"https://example.com/article" in body
            return httpx.Response(
                200,
                json={
                    "id": 1,
                    "title": "Example Article",
                    "source_url": "https://example.com/article",
                    "summary": "This is a test article about testing.",
                    "tags": ["testing", "example"],
                },
            )
        return httpx.Response(404)

    client = _make_client(handler)
    with (
        patch("jefe.cli.commands.knowledge.get_api_key", return_value="test-key"),
        patch("jefe.cli.commands.knowledge.create_client", return_value=client),
        patch("jefe.cli.commands.knowledge.is_online", new_callable=AsyncMock, return_value=True),
    ):
        result = runner.invoke(app, ["knowledge", "ingest", "https://example.com/article"])

    assert result.exit_code == 0
    assert "Successfully ingested entry 1" in result.stdout
    assert "Example Article" in result.stdout


def test_knowledge_ingest_with_content_type():
    """Test ingesting a URL with content type hint."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/knowledge/ingest":
            body = request.read()
            assert b"markdown" in body
            return httpx.Response(
                200,
                json={
                    "id": 2,
                    "title": "Markdown Doc",
                    "source_url": "https://example.com/doc.md",
                    "summary": "A markdown document.",
                    "tags": ["docs"],
                },
            )
        return httpx.Response(404)

    client = _make_client(handler)
    with (
        patch("jefe.cli.commands.knowledge.get_api_key", return_value="test-key"),
        patch("jefe.cli.commands.knowledge.create_client", return_value=client),
        patch("jefe.cli.commands.knowledge.is_online", new_callable=AsyncMock, return_value=True),
    ):
        result = runner.invoke(
            app, ["knowledge", "ingest", "https://example.com/doc.md", "--content-type", "markdown"]
        )

    assert result.exit_code == 0
    assert "Successfully ingested entry 2" in result.stdout


def test_knowledge_ingest_offline():
    """Test that ingest fails gracefully when offline."""
    with (
        patch("jefe.cli.commands.knowledge.get_api_key", return_value="test-key"),
        patch("jefe.cli.commands.knowledge.is_online", new_callable=AsyncMock, return_value=False),
    ):
        result = runner.invoke(app, ["knowledge", "ingest", "https://example.com/article"])

    assert result.exit_code == 1
    assert "Cannot ingest URLs while offline" in result.stdout


def test_knowledge_ingest_no_api_key():
    """Test that ingest requires API key."""
    with patch("jefe.cli.commands.knowledge.get_api_key", return_value=None):
        result = runner.invoke(app, ["knowledge", "ingest", "https://example.com/article"])

    assert result.exit_code == 1
    assert "API key not configured" in result.stdout


def test_knowledge_search_command():
    """Test searching knowledge entries."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/knowledge":
            assert request.method == "GET"
            # Check query parameters
            assert "q=best+practices" in str(request.url) or "q=best%20practices" in str(request.url)
            return httpx.Response(
                200,
                json=[
                    {
                        "id": 1,
                        "title": "Best Practices Guide",
                        "summary": "A comprehensive guide to best practices.",
                        "tags": ["guide", "best-practices"],
                    },
                    {
                        "id": 2,
                        "title": "Testing Best Practices",
                        "summary": "Best practices for testing software.",
                        "tags": ["testing", "best-practices"],
                    },
                ],
            )
        return httpx.Response(404)

    client = _make_client(handler)
    with (
        patch("jefe.cli.commands.knowledge.get_api_key", return_value="test-key"),
        patch("jefe.cli.commands.knowledge.create_client", return_value=client),
        patch("jefe.cli.commands.knowledge.is_online", new_callable=AsyncMock, return_value=True),
    ):
        result = runner.invoke(app, ["knowledge", "search", "best practices"])

    assert result.exit_code == 0
    assert "Found 2 entries" in result.stdout
    assert "Best Practices Guide" in result.stdout
    assert "Testing Best Practices" in result.stdout


def test_knowledge_search_with_tags():
    """Test searching with tag filter."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/knowledge":
            # Check that tags parameter is present
            assert "tags=testing" in str(request.url)
            return httpx.Response(
                200,
                json=[
                    {
                        "id": 1,
                        "title": "Testing Article",
                        "summary": "About testing.",
                        "tags": ["testing"],
                    }
                ],
            )
        return httpx.Response(404)

    client = _make_client(handler)
    with (
        patch("jefe.cli.commands.knowledge.get_api_key", return_value="test-key"),
        patch("jefe.cli.commands.knowledge.create_client", return_value=client),
        patch("jefe.cli.commands.knowledge.is_online", new_callable=AsyncMock, return_value=True),
    ):
        result = runner.invoke(app, ["knowledge", "search", "--tags", "testing"])

    assert result.exit_code == 0
    assert "Found 1 entries" in result.stdout


def test_knowledge_search_with_limit():
    """Test searching with custom limit."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/knowledge":
            # Check that limit parameter is present
            assert "limit=5" in str(request.url)
            return httpx.Response(200, json=[])
        return httpx.Response(404)

    client = _make_client(handler)
    with (
        patch("jefe.cli.commands.knowledge.get_api_key", return_value="test-key"),
        patch("jefe.cli.commands.knowledge.create_client", return_value=client),
        patch("jefe.cli.commands.knowledge.is_online", new_callable=AsyncMock, return_value=True),
    ):
        result = runner.invoke(app, ["knowledge", "search", "--limit", "5"])

    assert result.exit_code == 0
    assert "No entries found" in result.stdout


def test_knowledge_search_offline():
    """Test that search fails gracefully when offline."""
    with (
        patch("jefe.cli.commands.knowledge.get_api_key", return_value="test-key"),
        patch("jefe.cli.commands.knowledge.is_online", new_callable=AsyncMock, return_value=False),
    ):
        result = runner.invoke(app, ["knowledge", "search", "query"])

    assert result.exit_code == 1
    assert "Cannot search while offline" in result.stdout


def test_knowledge_show_command():
    """Test showing a single entry."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/knowledge/1":
            assert request.method == "GET"
            return httpx.Response(
                200,
                json={
                    "id": 1,
                    "title": "Detailed Article",
                    "source_url": "https://example.com/article",
                    "summary": "This is a detailed summary of the article.",
                    "tags": ["detailed", "example"],
                    "content": "This is the full content of the article with lots of details...",
                },
            )
        return httpx.Response(404)

    client = _make_client(handler)
    with (
        patch("jefe.cli.commands.knowledge.get_api_key", return_value="test-key"),
        patch("jefe.cli.commands.knowledge.create_client", return_value=client),
        patch("jefe.cli.commands.knowledge.is_online", new_callable=AsyncMock, return_value=True),
    ):
        result = runner.invoke(app, ["knowledge", "show", "1"])

    assert result.exit_code == 0
    assert "Knowledge Entry 1" in result.stdout
    assert "Detailed Article" in result.stdout
    assert "https://example.com/article" in result.stdout
    assert "detailed, example" in result.stdout
    assert "full content" in result.stdout


def test_knowledge_show_not_found():
    """Test showing a non-existent entry."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/knowledge/999":
            return httpx.Response(404)
        return httpx.Response(404)

    client = _make_client(handler)
    with (
        patch("jefe.cli.commands.knowledge.get_api_key", return_value="test-key"),
        patch("jefe.cli.commands.knowledge.create_client", return_value=client),
        patch("jefe.cli.commands.knowledge.is_online", new_callable=AsyncMock, return_value=True),
    ):
        result = runner.invoke(app, ["knowledge", "show", "999"])

    assert result.exit_code == 1
    assert "Entry 999 not found" in result.stdout


def test_knowledge_show_offline():
    """Test that show fails gracefully when offline."""
    with (
        patch("jefe.cli.commands.knowledge.get_api_key", return_value="test-key"),
        patch("jefe.cli.commands.knowledge.is_online", new_callable=AsyncMock, return_value=False),
    ):
        result = runner.invoke(app, ["knowledge", "show", "1"])

    assert result.exit_code == 1
    assert "Cannot show entry details while offline" in result.stdout
