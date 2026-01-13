"""Tests for bundle API endpoints."""

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
    db_path = tmp_path / "bundles.db"
    configure_engine(f"sqlite+aiosqlite:///{db_path}")

    key_file = tmp_path / "api_key"
    with patch("jefe.server.auth.get_api_key_file", return_value=key_file):
        api_key = generate_api_key()
        save_api_key(api_key)
        app = create_app()
        with TestClient(app) as client:
            yield client, api_key


def _create_bundle(
    client: TestClient,
    api_key: str,
    name: str = "test-bundle",
    display_name: str | None = "Test Bundle",
    description: str | None = "A test bundle",
    skill_refs: list[dict[str, str]] | None = None,
) -> dict:
    """Helper to create a bundle."""
    if skill_refs is None:
        skill_refs = [
            {"source": "test-source", "name": "skill1"},
            {"source": "test-source", "name": "skill2"},
        ]

    response = client.post(
        "/api/bundles",
        json={
            "name": name,
            "display_name": display_name,
            "description": description,
            "skill_refs": skill_refs,
        },
        headers={"X-API-Key": api_key},
    )
    assert response.status_code == 201
    return response.json()


def test_create_and_list_bundles(client_with_key: tuple[TestClient, str]) -> None:
    """Bundles can be created and listed."""
    client, api_key = client_with_key

    created = _create_bundle(client, api_key, name="alpha")
    assert created["name"] == "alpha"
    assert created["display_name"] == "Test Bundle"
    assert created["description"] == "A test bundle"
    assert len(created["skill_refs"]) == 2
    assert created["skill_refs"][0]["source"] == "test-source"
    assert created["skill_refs"][0]["name"] == "skill1"

    listing = client.get("/api/bundles", headers={"X-API-Key": api_key})
    assert listing.status_code == 200
    data = listing.json()
    assert len(data) == 1
    assert data[0]["name"] == "alpha"


def test_get_bundle(client_with_key: tuple[TestClient, str]) -> None:
    """Bundles can be fetched by ID."""
    client, api_key = client_with_key

    created = _create_bundle(client, api_key, name="get-me")
    bundle_id = created["id"]

    detail = client.get(f"/api/bundles/{bundle_id}", headers={"X-API-Key": api_key})
    assert detail.status_code == 200
    assert detail.json()["name"] == "get-me"
    assert detail.json()["id"] == bundle_id
    assert len(detail.json()["skill_refs"]) == 2


def test_get_bundle_not_found(client_with_key: tuple[TestClient, str]) -> None:
    """Getting a non-existent bundle returns 404."""
    client, api_key = client_with_key

    response = client.get("/api/bundles/999", headers={"X-API-Key": api_key})
    assert response.status_code == 404
    assert response.json()["detail"] == "Bundle not found"


def test_create_bundle_duplicate_name(client_with_key: tuple[TestClient, str]) -> None:
    """Creating a bundle with duplicate name returns 400."""
    client, api_key = client_with_key

    _create_bundle(client, api_key, name="duplicate")

    response = client.post(
        "/api/bundles",
        json={
            "name": "duplicate",
            "display_name": "Another Bundle",
            "description": "Another bundle",
            "skill_refs": [{"source": "source", "name": "skill"}],
        },
        headers={"X-API-Key": api_key},
    )
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


def test_create_bundle_empty_skill_refs(client_with_key: tuple[TestClient, str]) -> None:
    """Bundles can be created with empty skill_refs."""
    client, api_key = client_with_key

    created = _create_bundle(
        client, api_key, name="empty-bundle", skill_refs=[]
    )
    assert created["name"] == "empty-bundle"
    assert len(created["skill_refs"]) == 0


def test_openapi_documents_bundle_routes(client_with_key: tuple[TestClient, str]) -> None:
    """OpenAPI schema includes bundle endpoints."""
    client, _api_key = client_with_key
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/bundles" in paths
    assert "/api/bundles/{bundle_id}" in paths
    assert "/api/bundles/{bundle_id}/apply" in paths
