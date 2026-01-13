"""Tests for knowledge API endpoints."""

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from jefe.data.database import configure_engine
from jefe.server.app import create_app
from jefe.server.auth import generate_api_key, save_api_key

# Global counter for unique URLs
_url_counter = 0


@pytest.fixture
def client_with_key(tmp_path: Path) -> tuple[TestClient, str]:
    """Create a TestClient with a temporary database and API key."""
    db_path = tmp_path / "knowledge.db"
    configure_engine(f"sqlite+aiosqlite:///{db_path}")

    key_file = tmp_path / "api_key"
    with patch("jefe.server.auth.get_api_key_file", return_value=key_file):
        api_key = generate_api_key()
        save_api_key(api_key)
        app = create_app()
        with TestClient(app) as client:
            yield client, api_key


def _create_entry(
    client: TestClient,
    api_key: str,
    source_url: str | None = None,
    title: str = "Test Article",
    content: str = "Full content goes here.",
    summary: str = "Summary goes here.",
    tags: list[str] | None = None,
) -> dict:
    """Helper to create a knowledge entry."""
    global _url_counter
    if source_url is None:
        _url_counter += 1
        source_url = f"https://example.com/article-{_url_counter}"

    response = client.post(
        "/api/knowledge",
        json={
            "source_url": source_url,
            "title": title,
            "content": content,
            "summary": summary,
            "tags": tags or [],
        },
        headers={"X-API-Key": api_key},
    )
    assert response.status_code == 201
    return response.json()


def test_create_and_list_entries(client_with_key: tuple[TestClient, str]) -> None:
    """Knowledge entries can be created and listed."""
    client, api_key = client_with_key

    created = _create_entry(
        client,
        api_key,
        source_url="https://example.com/best-practice-1",
        title="Python Best Practices",
        content="Use type hints and follow PEP 8 conventions.",
        summary="Guide on Python best practices.",
        tags=["python", "best-practices"],
    )

    assert created["title"] == "Python Best Practices"
    assert created["source_url"] == "https://example.com/best-practice-1"
    assert created["summary"] == "Guide on Python best practices."
    assert created["tags"] == ["python", "best-practices"]
    assert "id" in created
    assert "created_at" in created
    assert "content" not in created  # Content should not be in list response

    # List all entries
    listing = client.get("/api/knowledge", headers={"X-API-Key": api_key})
    assert listing.status_code == 200
    data = listing.json()
    assert len(data) == 1
    assert data[0]["title"] == "Python Best Practices"
    assert data[0]["tags"] == ["python", "best-practices"]


def test_get_entry_with_full_content(client_with_key: tuple[TestClient, str]) -> None:
    """Knowledge entries can be fetched by ID with full content."""
    client, api_key = client_with_key

    created = _create_entry(
        client,
        api_key,
        title="FastAPI Guide",
        content="FastAPI is a modern, fast web framework for building APIs with Python.",
        summary="Introduction to FastAPI.",
    )
    entry_id = created["id"]

    detail = client.get(f"/api/knowledge/{entry_id}", headers={"X-API-Key": api_key})
    assert detail.status_code == 200
    data = detail.json()
    assert data["id"] == entry_id
    assert data["title"] == "FastAPI Guide"
    assert data["content"] == "FastAPI is a modern, fast web framework for building APIs with Python."
    assert data["summary"] == "Introduction to FastAPI."


def test_get_entry_not_found(client_with_key: tuple[TestClient, str]) -> None:
    """Getting a non-existent entry returns 404."""
    client, api_key = client_with_key

    response = client.get("/api/knowledge/999", headers={"X-API-Key": api_key})
    assert response.status_code == 404
    assert response.json()["detail"] == "Knowledge entry not found"


def test_delete_entry(client_with_key: tuple[TestClient, str]) -> None:
    """Knowledge entries can be deleted."""
    client, api_key = client_with_key

    created = _create_entry(client, api_key, title="Delete Me")
    entry_id = created["id"]

    deleted = client.delete(f"/api/knowledge/{entry_id}", headers={"X-API-Key": api_key})
    assert deleted.status_code == 204

    # Verify it's gone
    response = client.get(f"/api/knowledge/{entry_id}", headers={"X-API-Key": api_key})
    assert response.status_code == 404


def test_delete_entry_not_found(client_with_key: tuple[TestClient, str]) -> None:
    """Deleting a non-existent entry returns 404."""
    client, api_key = client_with_key

    response = client.delete("/api/knowledge/999", headers={"X-API-Key": api_key})
    assert response.status_code == 404


def test_duplicate_url_rejected(client_with_key: tuple[TestClient, str]) -> None:
    """Creating an entry with duplicate URL returns 400."""
    client, api_key = client_with_key

    url = "https://example.com/unique-article"
    _create_entry(client, api_key, source_url=url, title="First")

    # Try to create another with same URL
    response = client.post(
        "/api/knowledge",
        json={
            "source_url": url,
            "title": "Second",
            "content": "Different content",
            "summary": "Different summary",
            "tags": [],
        },
        headers={"X-API-Key": api_key},
    )
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


def test_search_by_text_query(client_with_key: tuple[TestClient, str]) -> None:
    """Entries can be searched by text query."""
    client, api_key = client_with_key

    _create_entry(
        client,
        api_key,
        title="Python Type Hints",
        content="Python 3.5+ supports type hints for better code quality.",
        summary="Guide to Python type hints.",
    )
    _create_entry(
        client,
        api_key,
        title="JavaScript Best Practices",
        content="Use ESLint and Prettier for JavaScript projects.",
        summary="JavaScript coding standards.",
    )

    # Search for Python-related entries
    response = client.get("/api/knowledge?q=Python", headers={"X-API-Key": api_key})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["title"] == "Python Type Hints"


def test_search_by_tags(client_with_key: tuple[TestClient, str]) -> None:
    """Entries can be filtered by tags."""
    client, api_key = client_with_key

    _create_entry(
        client,
        api_key,
        title="Article 1",
        tags=["python", "testing"],
    )
    _create_entry(
        client,
        api_key,
        title="Article 2",
        tags=["javascript", "testing"],
    )
    _create_entry(
        client,
        api_key,
        title="Article 3",
        tags=["python", "performance"],
    )

    # Search for entries tagged with "python"
    response = client.get("/api/knowledge?tags=python", headers={"X-API-Key": api_key})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    titles = [entry["title"] for entry in data]
    assert "Article 1" in titles
    assert "Article 3" in titles


def test_search_by_multiple_tags(client_with_key: tuple[TestClient, str]) -> None:
    """Entries can be filtered by multiple tags."""
    client, api_key = client_with_key

    _create_entry(
        client,
        api_key,
        title="Article 1",
        tags=["python", "testing"],
    )
    _create_entry(
        client,
        api_key,
        title="Article 2",
        tags=["python", "performance"],
    )

    # Search for entries with both python AND testing tags
    response = client.get("/api/knowledge?tags=python,testing", headers={"X-API-Key": api_key})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["title"] == "Article 1"


def test_search_with_pagination(client_with_key: tuple[TestClient, str]) -> None:
    """Search results can be paginated."""
    client, api_key = client_with_key

    # Create 5 entries
    for i in range(5):
        _create_entry(client, api_key, title=f"Article {i}", source_url=f"https://example.com/{i}")

    # Get first 2 results
    response = client.get("/api/knowledge?limit=2&offset=0", headers={"X-API-Key": api_key})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

    # Get next 2 results
    response = client.get("/api/knowledge?limit=2&offset=2", headers={"X-API-Key": api_key})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

    # Get last result
    response = client.get("/api/knowledge?limit=2&offset=4", headers={"X-API-Key": api_key})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1


def test_search_limit_validation(client_with_key: tuple[TestClient, str]) -> None:
    """Search limit is validated."""
    client, api_key = client_with_key

    # Limit too low
    response = client.get("/api/knowledge?limit=0", headers={"X-API-Key": api_key})
    assert response.status_code == 400

    # Limit too high
    response = client.get("/api/knowledge?limit=101", headers={"X-API-Key": api_key})
    assert response.status_code == 400


def test_ingest_endpoint_not_implemented(client_with_key: tuple[TestClient, str]) -> None:
    """Ingest endpoint returns 501 Not Implemented."""
    client, api_key = client_with_key

    response = client.post(
        "/api/knowledge/ingest",
        json={
            "source_url": "https://example.com/article",
            "content_type": "documentation",
        },
        headers={"X-API-Key": api_key},
    )
    assert response.status_code == 501
    assert "not yet implemented" in response.json()["detail"].lower()
