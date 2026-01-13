"""Tests for source API endpoints."""

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from jefe.data.database import configure_engine
from jefe.server.app import create_app
from jefe.server.auth import generate_api_key, save_api_key


@pytest.fixture
def client_with_key(tmp_path: Path) -> tuple[TestClient, str]:
    """Create a TestClient with a temporary database and API key."""
    db_path = tmp_path / "sources.db"
    configure_engine(f"sqlite+aiosqlite:///{db_path}")

    key_file = tmp_path / "api_key"
    with patch("jefe.server.auth.get_api_key_file", return_value=key_file):
        api_key = generate_api_key()
        save_api_key(api_key)
        app = create_app()
        with TestClient(app) as client:
            yield client, api_key


def _create_source(
    client: TestClient,
    api_key: str,
    name: str = "test-source",
    source_type: str = "git",
    url: str = "https://github.com/example/skills.git",
    description: str | None = "Test source",
) -> dict:
    """Helper to create a source."""
    response = client.post(
        "/api/sources",
        json={
            "name": name,
            "source_type": source_type,
            "url": url,
            "description": description,
        },
        headers={"X-API-Key": api_key},
    )
    assert response.status_code == 201
    return response.json()


def test_create_and_list_sources(client_with_key: tuple[TestClient, str]) -> None:
    """Sources can be created and listed."""
    client, api_key = client_with_key

    created = _create_source(client, api_key, name="alpha")
    assert created["name"] == "alpha"
    assert created["source_type"] == "git"
    assert created["url"] == "https://github.com/example/skills.git"
    assert created["sync_status"] == "pending"
    assert created["last_synced_at"] is None

    listing = client.get("/api/sources", headers={"X-API-Key": api_key})
    assert listing.status_code == 200
    data = listing.json()
    assert len(data) == 1
    assert data[0]["name"] == "alpha"


def test_get_source(client_with_key: tuple[TestClient, str]) -> None:
    """Sources can be fetched by ID."""
    client, api_key = client_with_key

    created = _create_source(client, api_key, name="get-me")
    source_id = created["id"]

    detail = client.get(f"/api/sources/{source_id}", headers={"X-API-Key": api_key})
    assert detail.status_code == 200
    assert detail.json()["name"] == "get-me"
    assert detail.json()["id"] == source_id


def test_get_source_not_found(client_with_key: tuple[TestClient, str]) -> None:
    """Getting a non-existent source returns 404."""
    client, api_key = client_with_key

    response = client.get("/api/sources/999", headers={"X-API-Key": api_key})
    assert response.status_code == 404
    assert response.json()["detail"] == "Source not found"


def test_delete_source(client_with_key: tuple[TestClient, str]) -> None:
    """Sources can be deleted."""
    client, api_key = client_with_key

    created = _create_source(client, api_key, name="delete-me")
    source_id = created["id"]

    deleted = client.delete(f"/api/sources/{source_id}", headers={"X-API-Key": api_key})
    assert deleted.status_code == 204

    missing = client.get(f"/api/sources/{source_id}", headers={"X-API-Key": api_key})
    assert missing.status_code == 404


def test_delete_source_not_found(client_with_key: tuple[TestClient, str]) -> None:
    """Deleting a non-existent source returns 404."""
    client, api_key = client_with_key

    response = client.delete("/api/sources/999", headers={"X-API-Key": api_key})
    assert response.status_code == 404
    assert response.json()["detail"] == "Source not found"


def test_create_source_duplicate_name(client_with_key: tuple[TestClient, str]) -> None:
    """Creating a source with duplicate name returns 400."""
    client, api_key = client_with_key

    _create_source(client, api_key, name="duplicate")

    response = client.post(
        "/api/sources",
        json={
            "name": "duplicate",
            "source_type": "git",
            "url": "https://github.com/another/repo.git",
            "description": "Another source",
        },
        headers={"X-API-Key": api_key},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Source name already exists"


def test_sync_source_not_found(client_with_key: tuple[TestClient, str]) -> None:
    """Syncing a non-existent source returns 400."""
    client, api_key = client_with_key

    response = client.post("/api/sources/999/sync", headers={"X-API-Key": api_key})
    assert response.status_code == 400
    assert "Skill source 999 not found" in response.json()["detail"]


def test_sync_source_invalid_type(client_with_key: tuple[TestClient, str]) -> None:
    """Syncing a non-git source returns 400."""
    client, api_key = client_with_key

    created = _create_source(
        client,
        api_key,
        name="marketplace-source",
        source_type="marketplace",
        url="https://marketplace.example.com",
    )
    source_id = created["id"]

    response = client.post(f"/api/sources/{source_id}/sync", headers={"X-API-Key": api_key})
    assert response.status_code == 400
    assert "Cannot sync source type" in response.json()["detail"]


def test_openapi_documents_source_routes(client_with_key: tuple[TestClient, str]) -> None:
    """OpenAPI schema includes source endpoints."""
    client, _api_key = client_with_key
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/sources" in paths
    assert "/api/sources/{source_id}" in paths
    assert "/api/sources/{source_id}/sync" in paths
