"""Tests for project and harness discovery APIs."""

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
    db_path = tmp_path / "test.db"
    configure_engine(f"sqlite+aiosqlite:///{db_path}")

    key_file = tmp_path / "api_key"
    with patch("jefe.server.auth.get_api_key_file", return_value=key_file):
        api_key = generate_api_key()
        save_api_key(api_key)
        app = create_app()
        with TestClient(app) as client:
            yield client, api_key


def _create_project_dir(tmp_path: Path) -> Path:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "CLAUDE.md").write_text("# Project instructions")
    claude_dir = project_dir / ".claude"
    claude_dir.mkdir()
    (claude_dir / "settings.json").write_text('{"model": "claude-3"}')
    return project_dir


def test_project_endpoints_include_configs(client_with_key: tuple[TestClient, str], tmp_path: Path) -> None:
    """Project detail should include discovered configs."""
    client, api_key = client_with_key
    project_dir = _create_project_dir(tmp_path)

    response = client.post(
        "/api/projects",
        json={"name": "demo", "path": str(project_dir)},
        headers={"X-API-Key": api_key},
    )
    assert response.status_code == 201
    project_id = response.json()["id"]

    discovery = client.post("/api/harnesses/discover", headers={"X-API-Key": api_key})
    assert discovery.status_code == 200

    detail = client.get(
        f"/api/projects/{project_id}",
        headers={"X-API-Key": api_key},
    )
    assert detail.status_code == 200
    configs = detail.json()["configs"]
    kinds = {config["kind"] for config in configs}
    assert "settings" in kinds
    assert "instructions" in kinds


def test_harness_discover_endpoint(client_with_key: tuple[TestClient, str], tmp_path: Path) -> None:
    """Harness discovery should return configs."""
    client, api_key = client_with_key
    project_dir = _create_project_dir(tmp_path)

    response = client.post(
        "/api/projects",
        json={"name": "demo", "path": str(project_dir)},
        headers={"X-API-Key": api_key},
    )
    assert response.status_code == 201

    discovery = client.post("/api/harnesses/discover", headers={"X-API-Key": api_key})
    assert discovery.status_code == 200
    configs = discovery.json()
    assert any(config["harness"] == "claude-code" for config in configs)
