"""Tests for project API endpoints."""

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
    db_path = tmp_path / "projects.db"
    configure_engine(f"sqlite+aiosqlite:///{db_path}")

    key_file = tmp_path / "api_key"
    with patch("jefe.server.auth.get_api_key_file", return_value=key_file):
        api_key = generate_api_key()
        save_api_key(api_key)
        app = create_app()
        with TestClient(app) as client:
            yield client, api_key


def _create_project(
    client: TestClient,
    api_key: str,
    name: str = "demo",
    description: str | None = "Test project",
) -> dict:
    response = client.post(
        "/api/projects",
        json={"name": name, "description": description},
        headers={"X-API-Key": api_key},
    )
    assert response.status_code == 201
    return response.json()


def test_create_and_list_projects(client_with_key: tuple[TestClient, str]) -> None:
    """Projects can be created and listed."""
    client, api_key = client_with_key

    created = _create_project(client, api_key, name="alpha")
    assert created["name"] == "alpha"
    assert created["manifestations"] == []

    listing = client.get("/api/projects", headers={"X-API-Key": api_key})
    assert listing.status_code == 200
    data = listing.json()
    assert len(data) == 1
    assert data[0]["name"] == "alpha"


def test_get_update_and_delete_project(client_with_key: tuple[TestClient, str]) -> None:
    """Projects can be fetched, updated, and deleted."""
    client, api_key = client_with_key

    created = _create_project(client, api_key, name="update-me")
    project_id = created["id"]

    detail = client.get(f"/api/projects/{project_id}", headers={"X-API-Key": api_key})
    assert detail.status_code == 200
    assert detail.json()["name"] == "update-me"

    updated = client.patch(
        f"/api/projects/{project_id}",
        json={"description": "Updated"},
        headers={"X-API-Key": api_key},
    )
    assert updated.status_code == 200
    assert updated.json()["description"] == "Updated"

    deleted = client.delete(f"/api/projects/{project_id}", headers={"X-API-Key": api_key})
    assert deleted.status_code == 204

    missing = client.get(f"/api/projects/{project_id}", headers={"X-API-Key": api_key})
    assert missing.status_code == 404


def test_add_and_remove_manifestation(
    client_with_key: tuple[TestClient, str], tmp_path: Path
) -> None:
    """Manifestations can be added and removed from projects."""
    client, api_key = client_with_key
    project = _create_project(client, api_key, name="manifestations")
    project_id = project["id"]

    project_dir = tmp_path / "project"
    project_dir.mkdir()

    added = client.post(
        f"/api/projects/{project_id}/manifestations",
        json={"type": "local", "path": str(project_dir), "machine_id": "host-1"},
        headers={"X-API-Key": api_key},
    )
    assert added.status_code == 201
    manifestation_id = added.json()["id"]

    detail = client.get(f"/api/projects/{project_id}", headers={"X-API-Key": api_key})
    assert detail.status_code == 200
    manifestations = detail.json()["manifestations"]
    assert len(manifestations) == 1
    assert manifestations[0]["id"] == manifestation_id

    removed = client.delete(
        f"/api/projects/{project_id}/manifestations/{manifestation_id}",
        headers={"X-API-Key": api_key},
    )
    assert removed.status_code == 204

    detail = client.get(f"/api/projects/{project_id}", headers={"X-API-Key": api_key})
    assert detail.status_code == 200
    assert detail.json()["manifestations"] == []


def test_openapi_documents_project_routes(client_with_key: tuple[TestClient, str]) -> None:
    """OpenAPI schema includes project endpoints."""
    client, _api_key = client_with_key
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/projects" in paths
    assert "/api/projects/{project_id}" in paths
    assert "/api/projects/{project_id}/manifestations" in paths
    assert "/api/projects/{project_id}/manifestations/{manifestation_id}" in paths
