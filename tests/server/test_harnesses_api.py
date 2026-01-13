"""Tests for harness API endpoints and persistence."""

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


def test_harness_list_and_get(client_with_key: tuple[TestClient, str]) -> None:
    """Harness list and detail endpoints should return seeded data."""
    client, api_key = client_with_key

    response = client.get("/api/harnesses", headers={"X-API-Key": api_key})
    assert response.status_code == 200
    harnesses = response.json()
    assert any(harness["name"] == "claude-code" for harness in harnesses)

    detail = client.get("/api/harnesses/claude-code", headers={"X-API-Key": api_key})
    assert detail.status_code == 200
    assert detail.json()["name"] == "claude-code"


def test_discovery_updates_content_hash(
    client_with_key: tuple[TestClient, str],
    tmp_path: Path,
) -> None:
    """Discovery should store configs and update content hash on changes."""
    client, api_key = client_with_key
    project_dir = _create_project_dir(tmp_path)
    settings_path = project_dir / ".claude" / "settings.json"

    response = client.post(
        "/api/projects",
        json={"name": "demo", "path": str(project_dir)},
        headers={"X-API-Key": api_key},
    )
    assert response.status_code == 201
    project_id = response.json()["id"]

    first = client.post("/api/harnesses/discover", headers={"X-API-Key": api_key})
    assert first.status_code == 200
    first_configs = first.json()
    settings_config = next(
        config
        for config in first_configs
        if config["kind"] == "settings"
        and config["path"] == str(settings_path)
        and config["project_id"] == project_id
    )
    original_hash = settings_config["content_hash"]
    assert original_hash

    settings_path.write_text('{"model": "claude-3", "theme": "light"}')

    second = client.post("/api/harnesses/discover", headers={"X-API-Key": api_key})
    assert second.status_code == 200
    second_configs = second.json()
    updated_config = next(
        config
        for config in second_configs
        if config["kind"] == "settings"
        and config["path"] == str(settings_path)
        and config["project_id"] == project_id
    )
    assert updated_config["content_hash"] != original_hash
