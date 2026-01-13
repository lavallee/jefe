"""Tests for offline detection and cache fallback."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from jefe.cli.cache.manager import CacheManager
from jefe.cli.cache.models import CacheBase
from jefe.cli.client import clear_online_cache, is_online


@pytest.fixture
def in_memory_engine():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    CacheBase.metadata.create_all(engine)
    return engine


@pytest.fixture
def mock_get_session(in_memory_engine):
    """Mock get_cache_session to use in-memory database."""
    SessionLocal = sessionmaker(bind=in_memory_engine)

    def _get_session():
        return SessionLocal()

    with (
        patch("jefe.cli.cache.repositories.get_cache_session", side_effect=_get_session),
        patch("jefe.cli.cache.repositories.init_cache_db"),
    ):
        yield


@pytest.fixture
def cache_manager(mock_get_session):
    """Fixture providing a cache manager instance."""
    manager = CacheManager()
    yield manager
    manager.close()


@pytest.fixture(autouse=True)
def clear_cache():
    """Auto-clear online status cache before each test."""
    clear_online_cache()
    yield
    clear_online_cache()


@pytest.mark.asyncio
async def test_is_online_when_server_reachable():
    """Test that is_online returns True when server responds."""
    with patch("jefe.cli.client.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_client.get.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client

        result = await is_online()

        assert result is True
        mock_client.get.assert_called_once_with("/health")


@pytest.mark.asyncio
async def test_is_online_when_server_unreachable():
    """Test that is_online returns False when server is unreachable."""
    with patch("jefe.cli.client.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.RequestError("Connection refused")
        mock_client_class.return_value.__aenter__.return_value = mock_client

        result = await is_online()

        assert result is False


@pytest.mark.asyncio
async def test_is_online_when_timeout():
    """Test that is_online returns False when server times out."""
    with patch("jefe.cli.client.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.TimeoutException("Timeout")
        mock_client_class.return_value.__aenter__.return_value = mock_client

        result = await is_online()

        assert result is False


@pytest.mark.asyncio
async def test_is_online_caches_result():
    """Test that is_online caches its result for 30 seconds."""
    with patch("jefe.cli.client.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_client.get.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # First call
        result1 = await is_online()
        assert result1 is True
        assert mock_client.get.call_count == 1

        # Second call (should use cache)
        result2 = await is_online()
        assert result2 is True
        assert mock_client.get.call_count == 1  # Still 1, cached


@pytest.mark.asyncio
async def test_is_online_cache_expires():
    """Test that the online status cache expires after TTL."""
    with patch("jefe.cli.client.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_client.get.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # Mock datetime to control cache expiration
        with patch("jefe.cli.client.datetime") as mock_datetime:
            now = datetime.now(UTC)
            mock_datetime.now.return_value = now

            # First call
            result1 = await is_online()
            assert result1 is True
            assert mock_client.get.call_count == 1

            # Advance time by 31 seconds (past TTL)
            mock_datetime.now.return_value = now + timedelta(seconds=31)

            # Second call (cache should be expired)
            result2 = await is_online()
            assert result2 is True
            assert mock_client.get.call_count == 2  # New check made


def test_clear_online_cache():
    """Test that clear_online_cache clears the cache."""
    import jefe.cli.client

    # Set a cache value
    jefe.cli.client._online_status_cache = (True, datetime.now(UTC))
    assert jefe.cli.client._online_status_cache is not None

    # Clear it
    clear_online_cache()
    assert jefe.cli.client._online_status_cache is None


def test_cache_stores_project(cache_manager: CacheManager):
    """Test that projects can be cached for offline access."""
    # Cache a project
    project = cache_manager.cache_project(
        server_id=1, name="test-project", description="Test description"
    )

    assert project.server_id == 1
    assert project.name == "test-project"
    assert project.description == "Test description"
    assert project.dirty is False

    # Retrieve from cache
    cached = cache_manager.get_project("test-project")
    assert cached is not None
    assert cached.server_id == 1
    assert cached.name == "test-project"


def test_cache_all_projects(cache_manager: CacheManager):
    """Test that all projects can be retrieved from cache."""
    # Cache multiple projects
    cache_manager.cache_project(server_id=1, name="project1", description="Desc 1")
    cache_manager.cache_project(server_id=2, name="project2", description="Desc 2")
    cache_manager.cache_project(server_id=3, name="project3", description=None)

    # Retrieve all
    all_projects = cache_manager.get_all_projects()
    assert len(all_projects) == 3
    assert {p.name for p in all_projects} == {"project1", "project2", "project3"}


def test_cache_project_freshness(cache_manager: CacheManager):
    """Test that cache freshness is tracked."""
    # Cache a project
    project = cache_manager.cache_project(
        server_id=1, name="test-project", description="Test"
    )

    # Should be fresh immediately
    assert cache_manager.is_project_fresh(project) is True

    # Mock old last_synced to make it stale
    project.last_synced = datetime.now(UTC) - timedelta(seconds=400)
    cache_manager.projects.set(project)

    # Reload from cache
    cached = cache_manager.get_project("test-project")
    assert cached is not None

    # Should be stale
    assert cache_manager.is_project_fresh(cached) is False


def test_offline_mode_uses_cached_data(cache_manager: CacheManager):
    """Test that offline mode can use cached data."""
    # Pre-populate cache
    cache_manager.cache_project(server_id=1, name="cached-project", description="Test")

    # Verify we can retrieve it
    cached = cache_manager.get_project("cached-project")
    assert cached is not None
    assert cached.name == "cached-project"
    assert cached.server_id == 1

    # This simulates what the CLI does in offline mode
    all_cached = cache_manager.get_all_projects()
    assert len(all_cached) == 1
    assert all_cached[0].name == "cached-project"
