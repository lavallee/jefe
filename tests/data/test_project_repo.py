"""Tests for project and manifestation repositories."""

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from jefe.data.database import get_engine
from jefe.data.models.base import Base
from jefe.data.models.manifestation import Manifestation, ManifestationType
from jefe.data.models.project import Project
from jefe.data.repositories.manifestation import ManifestationRepository
from jefe.data.repositories.project import ProjectRepository


@pytest.fixture(scope="function")
def test_db_path(tmp_path: Path) -> Path:
    """Create a temporary database file path."""
    return tmp_path / "projects.db"


@pytest.fixture(scope="function")
async def session(test_db_path: Path) -> AsyncSession:
    """Create an async session with project tables."""
    engine = get_engine(f"sqlite+aiosqlite:///{test_db_path}")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        yield session

    await engine.dispose()


async def _create_project_with_manifestation(
    session: AsyncSession,
    name: str = "demo",
) -> tuple[Project, Manifestation]:
    project_repo = ProjectRepository(session)
    manifestation_repo = ManifestationRepository(session)

    project = await project_repo.create(name=name, description="Test project")
    manifestation = await manifestation_repo.create(
        project_id=project.id,
        type=ManifestationType.LOCAL,
        path="/tmp/demo",
    )
    return project, manifestation


class TestProjectRepository:
    """Project repository tests."""

    async def test_create_and_fetch_with_manifestations(self, session: AsyncSession) -> None:
        """Create a project and fetch it with manifestations loaded."""
        project, manifestation = await _create_project_with_manifestation(session)

        repo = ProjectRepository(session)
        fetched = await repo.get_with_manifestations(project.id)

        assert fetched is not None
        assert fetched.id == project.id
        assert len(fetched.manifestations) == 1
        assert fetched.manifestations[0].id == manifestation.id

    async def test_list_all_projects(self, session: AsyncSession) -> None:
        """List all projects via repository helper."""
        repo = ProjectRepository(session)
        await repo.create(name="alpha")
        await repo.create(name="beta")

        projects = await repo.list_all()
        assert len(projects) == 2

    async def test_update_and_delete_project(self, session: AsyncSession) -> None:
        """Update and delete a project."""
        repo = ProjectRepository(session)
        project = await repo.create(name="update-me", description="Old")

        updated = await repo.update(project.id, description="New")
        assert updated is not None
        assert updated.description == "New"

        deleted = await repo.delete(project.id)
        assert deleted is True
        assert await repo.get_by_id(project.id) is None

    async def test_cascade_delete_manifestations(self, session: AsyncSession) -> None:
        """Deleting a project removes its manifestations."""
        project, manifestation = await _create_project_with_manifestation(session, name="cascade")

        repo = ProjectRepository(session)
        deleted = await repo.delete(project.id)
        assert deleted is True

        result = await session.execute(
            select(Manifestation).where(Manifestation.id == manifestation.id)
        )
        assert result.scalar_one_or_none() is None
