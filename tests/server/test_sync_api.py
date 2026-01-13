"""Tests for sync API endpoints."""

from datetime import UTC, datetime, timedelta
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
    db_path = tmp_path / "sync.db"
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
    """Helper to create a project."""
    response = client.post(
        "/api/projects",
        json={"name": name, "description": description},
        headers={"X-API-Key": api_key},
    )
    assert response.status_code == 201
    return response.json()


class TestSyncPushEndpoint:
    """Tests for POST /api/sync/push."""

    def test_push_empty_request(self, client_with_key: tuple[TestClient, str]) -> None:
        """Empty push request succeeds."""
        client, api_key = client_with_key

        response = client.post(
            "/api/sync/push",
            json={},
            headers={"X-API-Key": api_key},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["projects_synced"] == 0
        assert data["skills_synced"] == 0
        assert data["installed_skills_synced"] == 0
        assert data["harness_configs_synced"] == 0
        assert data["conflicts"] == []

    def test_push_new_project(self, client_with_key: tuple[TestClient, str]) -> None:
        """New project can be pushed to server."""
        client, api_key = client_with_key
        now = datetime.now(UTC)

        response = client.post(
            "/api/sync/push",
            json={
                "projects": [
                    {
                        "local_id": 1,
                        "server_id": None,
                        "name": "pushed-project",
                        "description": "Pushed from client",
                        "updated_at": now.isoformat(),
                    }
                ]
            },
            headers={"X-API-Key": api_key},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["projects_synced"] == 1
        # Should have a server ID mapping (keys are strings in JSON)
        assert "project" in data["server_id_mappings"]
        assert "1" in data["server_id_mappings"]["project"]

    def test_push_update_existing_project(
        self, client_with_key: tuple[TestClient, str]
    ) -> None:
        """Existing project can be updated via push."""
        client, api_key = client_with_key

        # Create a project first
        created = _create_project(client, api_key, name="to-update")
        project_id = created["id"]

        # Push an update
        now = datetime.now(UTC) + timedelta(hours=1)
        response = client.post(
            "/api/sync/push",
            json={
                "projects": [
                    {
                        "local_id": 100,
                        "server_id": project_id,
                        "name": "updated-name",
                        "description": "Updated description",
                        "updated_at": now.isoformat(),
                    }
                ]
            },
            headers={"X-API-Key": api_key},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["projects_synced"] == 1

        # Verify the update
        detail = client.get(
            f"/api/projects/{project_id}", headers={"X-API-Key": api_key}
        )
        assert detail.status_code == 200
        assert detail.json()["name"] == "updated-name"

    def test_push_conflict_server_wins(
        self, client_with_key: tuple[TestClient, str]
    ) -> None:
        """Server wins when its data is newer."""
        client, api_key = client_with_key

        # Create a project
        created = _create_project(client, api_key, name="conflict-test")
        project_id = created["id"]

        # Push with old timestamp (server should win)
        old_time = datetime.now(UTC) - timedelta(days=1)
        response = client.post(
            "/api/sync/push",
            json={
                "projects": [
                    {
                        "local_id": 100,
                        "server_id": project_id,
                        "name": "client-version",
                        "description": "From client",
                        "updated_at": old_time.isoformat(),
                    }
                ]
            },
            headers={"X-API-Key": api_key},
        )

        assert response.status_code == 200
        data = response.json()
        # Should still sync (server wins means server keeps its value)
        assert data["projects_synced"] == 1

        # Verify server version was preserved
        detail = client.get(
            f"/api/projects/{project_id}", headers={"X-API-Key": api_key}
        )
        assert detail.status_code == 200
        # Server's original name should be preserved
        assert detail.json()["name"] == "conflict-test"

    def test_push_requires_auth(self, client_with_key: tuple[TestClient, str]) -> None:
        """Push endpoint requires authentication."""
        client, _ = client_with_key

        response = client.post("/api/sync/push", json={})

        assert response.status_code == 401


class TestSyncPullEndpoint:
    """Tests for POST /api/sync/pull."""

    def test_pull_empty_database(self, client_with_key: tuple[TestClient, str]) -> None:
        """Pull from empty database returns empty lists."""
        client, api_key = client_with_key

        response = client.post(
            "/api/sync/pull",
            json={},
            headers={"X-API-Key": api_key},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "server_time" in data
        assert data["projects"] == []
        assert data["skills"] == []
        assert data["installed_skills"] == []
        assert data["harness_configs"] == []

    def test_pull_all_projects(self, client_with_key: tuple[TestClient, str]) -> None:
        """Pull returns all projects when no timestamp provided."""
        client, api_key = client_with_key

        # Create some projects
        _create_project(client, api_key, name="project-1")
        _create_project(client, api_key, name="project-2")

        response = client.post(
            "/api/sync/pull",
            json={},
            headers={"X-API-Key": api_key},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["projects"]) == 2

        names = {p["name"] for p in data["projects"]}
        assert "project-1" in names
        assert "project-2" in names

    def test_pull_with_timestamp_filter(
        self, client_with_key: tuple[TestClient, str]
    ) -> None:
        """Pull with timestamp only returns newer items."""
        client, api_key = client_with_key

        # Create some projects
        _create_project(client, api_key, name="project-a")
        _create_project(client, api_key, name="project-b")

        # Pull with a timestamp far in the past - should get all
        past = datetime.now(UTC) - timedelta(days=1)
        response = client.post(
            "/api/sync/pull",
            json={"last_synced": past.isoformat()},
            headers={"X-API-Key": api_key},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["projects"]) == 2

        # Pull with a timestamp far in the future - should get none
        future = datetime.now(UTC) + timedelta(days=1)
        response = client.post(
            "/api/sync/pull",
            json={"last_synced": future.isoformat()},
            headers={"X-API-Key": api_key},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["projects"]) == 0

    def test_pull_specific_entity_types(
        self, client_with_key: tuple[TestClient, str]
    ) -> None:
        """Pull can filter by entity type."""
        client, api_key = client_with_key

        _create_project(client, api_key, name="a-project")

        response = client.post(
            "/api/sync/pull",
            json={"entity_types": ["project"]},
            headers={"X-API-Key": api_key},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["projects"]) == 1
        # Other types should be empty since we only requested projects
        assert data["skills"] == []
        assert data["installed_skills"] == []
        assert data["harness_configs"] == []

    def test_pull_requires_auth(self, client_with_key: tuple[TestClient, str]) -> None:
        """Pull endpoint requires authentication."""
        client, _ = client_with_key

        response = client.post("/api/sync/pull", json={})

        assert response.status_code == 401

    def test_pull_server_time_returned(
        self, client_with_key: tuple[TestClient, str]
    ) -> None:
        """Pull response includes server time."""
        client, api_key = client_with_key
        before = datetime.now(UTC)

        response = client.post(
            "/api/sync/pull",
            json={},
            headers={"X-API-Key": api_key},
        )

        after = datetime.now(UTC)

        assert response.status_code == 200
        data = response.json()
        server_time = datetime.fromisoformat(data["server_time"])

        # Server time should be between request start and end
        assert before <= server_time <= after


class TestSyncOpenAPI:
    """Tests for OpenAPI documentation of sync endpoints."""

    def test_openapi_documents_sync_routes(
        self, client_with_key: tuple[TestClient, str]
    ) -> None:
        """OpenAPI schema includes sync endpoints."""
        client, _ = client_with_key

        response = client.get("/openapi.json")

        assert response.status_code == 200
        paths = response.json()["paths"]
        assert "/api/sync/push" in paths
        assert "/api/sync/pull" in paths
