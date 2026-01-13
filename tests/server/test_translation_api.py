"""Tests for translation API endpoints."""

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
    db_path = tmp_path / "translation.db"
    configure_engine(f"sqlite+aiosqlite:///{db_path}")

    key_file = tmp_path / "api_key"
    with patch("jefe.server.auth.get_api_key_file", return_value=key_file):
        api_key = generate_api_key()
        save_api_key(api_key)
        app = create_app()
        with TestClient(app) as client:
            yield client, api_key


def test_translate_content(client_with_key: tuple[TestClient, str]) -> None:
    """Translation endpoint can translate content between harness formats."""
    client, api_key = client_with_key

    content = """# Overview
This is a test configuration."""

    response = client.post(
        "/api/translate",
        json={
            "content": content,
            "source_harness": "claude-code",
            "target_harness": "codex_cli",
            "config_kind": "instructions",
        },
        headers={"X-API-Key": api_key},
    )

    assert response.status_code == 200
    data = response.json()
    assert "output" in data
    assert "diff" in data
    assert "log_id" in data
    assert isinstance(data["log_id"], int)


def test_translate_invalid_harness(client_with_key: tuple[TestClient, str]) -> None:
    """Translation endpoint rejects invalid harness names."""
    client, api_key = client_with_key

    response = client.post(
        "/api/translate",
        json={
            "content": "test",
            "source_harness": "invalid-harness",
            "target_harness": "codex_cli",
            "config_kind": "instructions",
        },
        headers={"X-API-Key": api_key},
    )

    assert response.status_code == 400
    assert "error" in response.json()["detail"].lower() or "unsupported" in response.json()["detail"].lower()


def test_get_translation_history(client_with_key: tuple[TestClient, str]) -> None:
    """Translation history can be retrieved."""
    client, api_key = client_with_key

    # First, create a translation
    client.post(
        "/api/translate",
        json={
            "content": "# Test",
            "source_harness": "claude-code",
            "target_harness": "codex_cli",
            "config_kind": "instructions",
        },
        headers={"X-API-Key": api_key},
    )

    # Then retrieve history
    response = client.get("/api/translate/log", headers={"X-API-Key": api_key})

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["input_text"] == "# Test"
    assert "output_text" in data[0]
    assert data[0]["translation_type"] == "syntax"
    assert data[0]["model_name"] == "claude-code-to-codex_cli"


def test_get_translation_history_with_filters(
    client_with_key: tuple[TestClient, str]
) -> None:
    """Translation history can be filtered."""
    client, api_key = client_with_key

    # Create multiple translations
    for i in range(3):
        client.post(
            "/api/translate",
            json={
                "content": f"# Test {i}",
                "source_harness": "claude-code",
                "target_harness": "codex_cli",
                "config_kind": "instructions",
            },
            headers={"X-API-Key": api_key},
        )

    # Test limit parameter
    response = client.get(
        "/api/translate/log", params={"limit": 2}, headers={"X-API-Key": api_key}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

    # Test offset parameter
    response = client.get(
        "/api/translate/log", params={"offset": 2}, headers={"X-API-Key": api_key}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1


def test_apply_translation(
    client_with_key: tuple[TestClient, str], tmp_path: Path
) -> None:
    """Translation can be applied to a file."""
    from unittest.mock import patch

    client, api_key = client_with_key

    target_file = tmp_path / "output.md"
    content = "# Translated Content\nThis is the translated output."

    # Patch cwd to be tmp_path so path validation passes
    with patch("pathlib.Path.cwd", return_value=tmp_path):
        response = client.post(
            "/api/translate/apply",
            json={
                "file_path": str(target_file),
                "content": content,
            },
            headers={"X-API-Key": api_key},
        )

    assert response.status_code == 200
    assert "message" in response.json()
    assert target_file.exists()
    assert target_file.read_text() == content


def test_apply_translation_creates_parent_directories(
    client_with_key: tuple[TestClient, str], tmp_path: Path
) -> None:
    """Apply translation creates parent directories if they don't exist."""
    from unittest.mock import patch

    client, api_key = client_with_key

    target_file = tmp_path / "nested" / "dirs" / "output.md"
    content = "# Test"

    # Patch cwd to be tmp_path so path validation passes
    with patch("pathlib.Path.cwd", return_value=tmp_path):
        response = client.post(
            "/api/translate/apply",
            json={
                "file_path": str(target_file),
                "content": content,
            },
            headers={"X-API-Key": api_key},
        )

    assert response.status_code == 200
    assert target_file.exists()
    assert target_file.read_text() == content


def test_openapi_documents_translation_routes(
    client_with_key: tuple[TestClient, str]
) -> None:
    """OpenAPI schema includes translation endpoints."""
    client, _api_key = client_with_key
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/translate" in paths
    assert "/api/translate/log" in paths
    assert "/api/translate/apply" in paths


def test_translation_requires_authentication(
    client_with_key: tuple[TestClient, str]
) -> None:
    """Translation endpoints require API key authentication."""
    client, _api_key = client_with_key

    endpoints = [
        ("POST", "/api/translate", {"content": "test", "source_harness": "claude-code", "target_harness": "codex_cli"}),
        ("GET", "/api/translate/log", None),
        ("POST", "/api/translate/apply", {"file_path": "/tmp/test", "content": "test"}),
    ]

    for method, path, json_data in endpoints:
        response = client.get(path) if method == "GET" else client.post(path, json=json_data)
        assert response.status_code in [401, 403], f"Expected auth error for {method} {path}"
