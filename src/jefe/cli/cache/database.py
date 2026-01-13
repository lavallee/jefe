"""Local SQLite database management for CLI cache."""

from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from jefe.cli.cache.models import CacheBase
from jefe.cli.config import get_config_dir


def get_cache_db_path() -> Path:
    """Get path to the local cache database.

    Returns:
        Path to ~/.config/jefe/cache.db
    """
    return get_config_dir() / "cache.db"


def get_cache_engine() -> Engine:
    """Get SQLAlchemy engine for the cache database.

    Returns:
        SQLAlchemy Engine instance for cache.db
    """
    db_path = get_cache_db_path()
    db_url = f"sqlite:///{db_path}"
    return create_engine(db_url, echo=False)


def init_cache_db() -> None:
    """Initialize the cache database.

    Creates all tables if they don't exist.
    This is called on first use to set up the cache database.
    """
    engine = get_cache_engine()
    CacheBase.metadata.create_all(engine)


def get_cache_session() -> Session:
    """Get a database session for the cache.

    Returns:
        SQLAlchemy Session instance for cache operations.
    """
    engine = get_cache_engine()
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()
