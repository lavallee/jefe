"""Tests for authentication middleware and endpoints."""

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from jefe.server.app import create_app
from jefe.server.auth import (
    ensure_api_key_exists,
    generate_api_key,
    load_api_key_hash,
    save_api_key,
    verify_api_key,
)


@pytest.fixture
def temp_api_key_dir(tmp_path: Path) -> Path:
    """Create a temporary directory for API key storage during tests."""
    return tmp_path


@pytest.fixture
def mock_api_key_file(temp_api_key_dir: Path) -> Path:
    """Mock the API key file location to use a temporary directory."""
    key_file = temp_api_key_dir / "api_key"
    with patch("jefe.server.auth.get_api_key_file", return_value=key_file):
        yield key_file


@pytest.fixture
def client(mock_api_key_file: Path) -> TestClient:
    """Create a test client with mocked API key storage."""
    app = create_app()
    return TestClient(app)


@pytest.fixture
def valid_api_key(mock_api_key_file: Path) -> str:
    """Generate and save a valid API key for testing."""
    key = generate_api_key()
    save_api_key(key)
    return key


def test_generate_api_key_returns_string() -> None:
    """Test that generate_api_key returns a string."""
    key = generate_api_key()
    assert isinstance(key, str)
    assert len(key) > 0


def test_generate_api_key_unique() -> None:
    """Test that generate_api_key generates unique keys."""
    key1 = generate_api_key()
    key2 = generate_api_key()
    assert key1 != key2


def test_save_and_load_api_key(mock_api_key_file: Path) -> None:
    """Test saving and loading API key."""
    key = generate_api_key()
    save_api_key(key)

    # File should exist
    assert mock_api_key_file.exists()

    # Should be able to load the hash
    loaded_hash = load_api_key_hash()
    assert loaded_hash is not None
    assert isinstance(loaded_hash, str)


def test_verify_api_key_with_valid_key(mock_api_key_file: Path) -> None:
    """Test that verify_api_key returns True for valid key."""
    key = generate_api_key()
    save_api_key(key)

    assert verify_api_key(key) is True


def test_verify_api_key_with_invalid_key(mock_api_key_file: Path) -> None:
    """Test that verify_api_key returns False for invalid key."""
    key = generate_api_key()
    save_api_key(key)

    # Try with a different key
    wrong_key = generate_api_key()
    assert verify_api_key(wrong_key) is False


def test_verify_api_key_with_no_stored_key(mock_api_key_file: Path) -> None:
    """Test that verify_api_key returns False when no key is stored."""
    key = generate_api_key()
    assert verify_api_key(key) is False


def test_ensure_api_key_exists_creates_new_key(mock_api_key_file: Path) -> None:
    """Test that ensure_api_key_exists creates a new key if none exists."""
    new_key = ensure_api_key_exists()

    assert new_key is not None
    assert isinstance(new_key, str)
    assert mock_api_key_file.exists()
    assert verify_api_key(new_key) is True


def test_ensure_api_key_exists_does_not_overwrite(mock_api_key_file: Path) -> None:
    """Test that ensure_api_key_exists doesn't overwrite existing key."""
    # Create initial key
    first_key = generate_api_key()
    save_api_key(first_key)

    # Ensure key exists should return None (key already exists)
    result = ensure_api_key_exists()
    assert result is None

    # Original key should still be valid
    assert verify_api_key(first_key) is True


def test_auth_verify_endpoint_with_valid_key(client: TestClient, valid_api_key: str) -> None:
    """Test that /api/auth/verify returns 200 with valid API key."""
    response = client.get("/api/auth/verify", headers={"X-API-Key": valid_api_key})

    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "API key is valid"


def test_auth_verify_endpoint_without_key(client: TestClient, valid_api_key: str) -> None:
    """Test that /api/auth/verify returns 401 without API key."""
    response = client.get("/api/auth/verify")

    assert response.status_code == 401
    data = response.json()
    assert "API key is required" in data["detail"]


def test_auth_verify_endpoint_with_invalid_key(client: TestClient, valid_api_key: str) -> None:
    """Test that /api/auth/verify returns 401 with invalid API key."""
    wrong_key = generate_api_key()
    response = client.get("/api/auth/verify", headers={"X-API-Key": wrong_key})

    assert response.status_code == 401
    data = response.json()
    assert "Invalid API key" in data["detail"]


def test_health_endpoint_works_without_auth(client: TestClient, valid_api_key: str) -> None:
    """Test that /health endpoint works without authentication."""
    response = client.get("/health")
    assert response.status_code == 200


def test_docs_endpoint_works_without_auth(client: TestClient, valid_api_key: str) -> None:
    """Test that /docs endpoint works without authentication."""
    response = client.get("/docs")
    assert response.status_code == 200


def test_openapi_json_works_without_auth(client: TestClient, valid_api_key: str) -> None:
    """Test that /openapi.json endpoint works without authentication."""
    response = client.get("/openapi.json")
    assert response.status_code == 200


def test_api_key_file_permissions(mock_api_key_file: Path) -> None:
    """Test that API key file has correct permissions (owner read/write only)."""
    key = generate_api_key()
    save_api_key(key)

    # Check file permissions (should be 0o600 - owner read/write only)
    import stat

    file_stat = mock_api_key_file.stat()
    # Get permission bits
    perms = stat.S_IMODE(file_stat.st_mode)
    assert perms == 0o600
