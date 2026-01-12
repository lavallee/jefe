"""Database configuration and session management."""

import os
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

# Database URL from environment or default to SQLite
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./station_chief.db")


def get_engine(database_url: str | None = None, **kwargs: Any) -> AsyncEngine:
    """
    Create and configure async database engine.

    Args:
        database_url: Database URL to connect to. Uses DATABASE_URL env var if not provided.
        **kwargs: Additional arguments passed to create_async_engine.

    Returns:
        Configured AsyncEngine instance.
    """
    url = database_url or DATABASE_URL

    # For SQLite, use NullPool to avoid threading issues
    if url.startswith("sqlite"):
        kwargs.setdefault("poolclass", NullPool)

    # Create async engine
    engine = create_async_engine(url, echo=False, **kwargs)

    return engine


# Global engine instance
engine = get_engine()

# Session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for getting async database sessions.

    Yields:
        AsyncSession instance that is automatically closed after use.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    """
    Initialize the database by creating all tables.

    This should be called on application startup if not using migrations.
    """
    from jefe.data.models.base import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """
    Close database connections.

    This should be called on application shutdown.
    """
    await engine.dispose()
