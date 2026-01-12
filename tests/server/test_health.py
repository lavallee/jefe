"""Tests for health check endpoint."""

import pytest
from fastapi.testclient import TestClient

import jefe
from jefe.server.app import create_app


@pytest.fixture
def client() -> TestClient:
    """Create a test client for the FastAPI application."""
    app = create_app()
    return TestClient(app)


def test_health_endpoint_returns_200(client: TestClient) -> None:
    """Test that health endpoint returns 200 status code."""
    response = client.get("/health")
    assert response.status_code == 200


def test_health_endpoint_returns_correct_structure(client: TestClient) -> None:
    """Test that health endpoint returns correct JSON structure."""
    response = client.get("/health")
    data = response.json()

    assert "status" in data
    assert "version" in data


def test_health_endpoint_returns_correct_values(client: TestClient) -> None:
    """Test that health endpoint returns correct values."""
    response = client.get("/health")
    data = response.json()

    assert data["status"] == "healthy"
    assert data["version"] == jefe.__version__


def test_openapi_docs_available(client: TestClient) -> None:
    """Test that OpenAPI documentation is available."""
    response = client.get("/docs")
    assert response.status_code == 200


def test_openapi_json_available(client: TestClient) -> None:
    """Test that OpenAPI JSON schema is available."""
    response = client.get("/openapi.json")
    assert response.status_code == 200

    data = response.json()
    assert "openapi" in data
    assert "info" in data
    assert data["info"]["title"] == "Station Chief"
    assert data["info"]["version"] == jefe.__version__
