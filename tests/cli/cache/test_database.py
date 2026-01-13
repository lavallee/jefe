"""Tests for cache database management."""

from pathlib import Path
from unittest.mock import patch

import pytest

from jefe.cli.cache.database import (
    get_cache_db_path,
    get_cache_engine,
    get_cache_session,
    init_cache_db,
)
from jefe.cli.cache.models import CachedProject


@pytest.fixture
def mock_config_dir(tmp_path: Path):
    """Mock the config directory to use a temporary path."""
    with patch("jefe.cli.cache.database.get_config_dir", return_value=tmp_path):
        yield tmp_path


def test_get_cache_db_path(mock_config_dir: Path):
    """Test getting the cache database path."""
    db_path = get_cache_db_path()
    assert db_path == mock_config_dir / "cache.db"
    assert db_path.parent == mock_config_dir


def test_get_cache_engine(mock_config_dir: Path):
    """Test getting a cache database engine."""
    engine = get_cache_engine()
    assert engine is not None
    assert "sqlite" in str(engine.url)


def test_init_cache_db(mock_config_dir: Path):
    """Test initializing the cache database."""
    db_path = get_cache_db_path()
    assert not db_path.exists()

    init_cache_db()

    # Database file should now exist
    assert db_path.exists()
    assert db_path.is_file()

    # Verify we can connect and query
    session = get_cache_session()
    result = session.query(CachedProject).all()
    assert result == []
    session.close()


def test_get_cache_session(mock_config_dir: Path):
    """Test getting a cache session."""
    init_cache_db()
    session = get_cache_session()

    assert session is not None

    # Test we can use the session
    project = CachedProject(name="test-session", server_id=1)
    session.add(project)
    session.commit()

    result = session.query(CachedProject).filter_by(name="test-session").first()
    assert result is not None
    assert result.name == "test-session"

    session.close()


def test_cache_db_persistence(mock_config_dir: Path):
    """Test that data persists across sessions."""
    init_cache_db()

    # Create and save a project
    session1 = get_cache_session()
    project = CachedProject(name="persistent", description="Test persistence", server_id=99)
    session1.add(project)
    session1.commit()
    session1.close()

    # Open a new session and verify data is still there
    session2 = get_cache_session()
    result = session2.query(CachedProject).filter_by(name="persistent").first()
    assert result is not None
    assert result.name == "persistent"
    assert result.description == "Test persistence"
    assert result.server_id == 99
    session2.close()


def test_init_cache_db_idempotent(mock_config_dir: Path):
    """Test that initializing the cache database multiple times is safe."""
    init_cache_db()
    db_path = get_cache_db_path()
    assert db_path.exists()

    # Add some data
    session = get_cache_session()
    project = CachedProject(name="idempotent-test", server_id=1)
    session.add(project)
    session.commit()
    session.close()

    # Initialize again
    init_cache_db()

    # Data should still be there
    session2 = get_cache_session()
    result = session2.query(CachedProject).filter_by(name="idempotent-test").first()
    assert result is not None
    session2.close()
