"""Tests for database configuration and operations."""

import os
from pathlib import Path

import pytest
from sqlalchemy import String, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from jefe.data.database import get_engine
from jefe.data.models.base import BaseModel
from jefe.data.repositories.base import BaseRepository


# Test model for repository operations
class User(BaseModel):
    """Test user model."""

    __tablename__ = "test_users"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)


@pytest.fixture(scope="function")
def test_db_path(tmp_path: Path) -> Path:
    """Create a temporary database file path."""
    return tmp_path / "test.db"


class TestDatabaseConnection:
    """Test database connection and session management."""

    async def test_get_engine_creates_engine(self) -> None:
        """Test that get_engine creates a valid engine."""
        engine = get_engine("sqlite+aiosqlite:///:memory:")
        assert engine is not None
        await engine.dispose()

    async def test_get_engine_uses_default_url(self) -> None:
        """Test that get_engine uses default DATABASE_URL."""
        os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
        engine = get_engine()
        assert engine is not None
        await engine.dispose()


class TestDatabaseOperations:
    """Test database operations with a file-based database."""

    async def test_create_tables_and_session(self, test_db_path: Path) -> None:
        """Test creating tables and using sessions."""
        # Create engine with file-based database
        engine = get_engine(f"sqlite+aiosqlite:///{test_db_path}")

        # Create tables
        async with engine.begin() as conn:
            await conn.run_sync(User.metadata.create_all)

        # Verify tables were created
        async with engine.connect() as conn:
            result = await conn.execute(select(User))
            assert result is not None

        await engine.dispose()


class TestBaseRepository:
    """Test base repository CRUD operations."""

    async def test_crud_operations(self, test_db_path: Path) -> None:
        """Test complete CRUD cycle."""
        # Create engine and tables
        engine = get_engine(f"sqlite+aiosqlite:///{test_db_path}")

        async with engine.begin() as conn:
            await conn.run_sync(User.metadata.create_all)

        #Create session
        from sqlalchemy.ext.asyncio import async_sessionmaker

        async_session = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        async with async_session() as session:
            repo = BaseRepository(User, session)

            # Test create
            user = await repo.create(name="John Doe", email="john@example.com")
            assert user.id is not None
            assert user.name == "John Doe"
            assert user.email == "john@example.com"
            assert user.created_at is not None
            assert user.updated_at is not None

            # Test get_by_id
            retrieved_user = await repo.get_by_id(user.id)
            assert retrieved_user is not None
            assert retrieved_user.id == user.id
            assert retrieved_user.name == "John Doe"

            # Test get_all
            await repo.create(name="Jane Doe", email="jane@example.com")
            users = await repo.get_all()
            assert len(users) == 2

            # Test update
            updated_user = await repo.update(user.id, name="Updated Name")
            assert updated_user is not None
            assert updated_user.name == "Updated Name"

            # Test count
            count = await repo.count()
            assert count == 2

            # Test delete
            result = await repo.delete(user.id)
            assert result is True

            deleted_user = await repo.get_by_id(user.id)
            assert deleted_user is None

        await engine.dispose()


class TestBaseModel:
    """Test BaseModel functionality."""

    async def test_to_dict_and_repr(self, test_db_path: Path) -> None:
        """Test model utility methods."""
        # Create engine and tables
        engine = get_engine(f"sqlite+aiosqlite:///{test_db_path}")

        async with engine.begin() as conn:
            await conn.run_sync(User.metadata.create_all)

        from sqlalchemy.ext.asyncio import async_sessionmaker

        async_session = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        async with async_session() as session:
            repo = BaseRepository(User, session)
            user = await repo.create(name="Test User", email="test@example.com")

            # Test to_dict
            user_dict = user.to_dict()
            assert user_dict["id"] == user.id
            assert user_dict["name"] == "Test User"
            assert user_dict["email"] == "test@example.com"
            assert "created_at" in user_dict
            assert "updated_at" in user_dict

            # Test __repr__
            repr_str = repr(user)
            assert "User" in repr_str
            assert "id=" in repr_str
            assert "name='Test User'" in repr_str

        await engine.dispose()
