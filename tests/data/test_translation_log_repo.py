"""Tests for TranslationLog repository."""

from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from jefe.data.database import get_engine
from jefe.data.models.base import Base
from jefe.data.models.project import Project
from jefe.data.models.translation_log import TranslationLog, TranslationType
from jefe.data.repositories.project import ProjectRepository
from jefe.data.repositories.translation_log import TranslationLogRepository


@pytest.fixture(scope="function")
def test_db_path(tmp_path: Path) -> Path:
    """Create a temporary database file path."""
    return tmp_path / "translation_logs.db"


@pytest.fixture(scope="function")
async def session(test_db_path: Path) -> AsyncSession:
    """Create an async session with translation_logs tables."""
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


async def _create_project(session: AsyncSession, name: str = "test-project") -> Project:
    """Helper to create a test project."""
    project_repo = ProjectRepository(session)
    return await project_repo.create(name=name, description="Test project")


class TestTranslationLogRepository:
    """TranslationLog repository tests."""

    async def test_create_and_fetch(self, session: AsyncSession) -> None:
        """Create a translation log and fetch it by ID."""
        repo = TranslationLogRepository(session)
        log = await repo.create(
            input_text="SELECT * FROM users",
            output_text="SELECT id, name, email FROM users",
            translation_type=TranslationType.SYNTAX,
            model_name="gpt-4",
        )

        assert log.id is not None
        assert log.input_text == "SELECT * FROM users"
        assert log.output_text == "SELECT id, name, email FROM users"
        assert log.translation_type == TranslationType.SYNTAX
        assert log.model_name == "gpt-4"
        assert log.project_id is None

        fetched = await repo.get_by_id(log.id)
        assert fetched is not None
        assert fetched.id == log.id
        assert fetched.translation_type == TranslationType.SYNTAX

    async def test_create_with_project(self, session: AsyncSession) -> None:
        """Create a translation log associated with a project."""
        project = await _create_project(session, "my-project")
        repo = TranslationLogRepository(session)

        log = await repo.create(
            input_text="function add(a, b) { return a + b }",
            output_text="const add = (a, b) => a + b",
            translation_type=TranslationType.SEMANTIC,
            model_name="claude-3",
            project_id=project.id,
        )

        assert log.project_id == project.id
        assert log.translation_type == TranslationType.SEMANTIC

    async def test_list_all(self, session: AsyncSession) -> None:
        """List all translation logs."""
        repo = TranslationLogRepository(session)

        await repo.create(
            input_text="input1",
            output_text="output1",
            translation_type=TranslationType.SYNTAX,
            model_name="model1",
        )
        await repo.create(
            input_text="input2",
            output_text="output2",
            translation_type=TranslationType.SEMANTIC,
            model_name="model2",
        )

        logs = await repo.list_all()
        assert len(logs) == 2

    async def test_list_all_with_pagination(self, session: AsyncSession) -> None:
        """List translation logs with pagination."""
        repo = TranslationLogRepository(session)

        for i in range(5):
            await repo.create(
                input_text=f"input{i}",
                output_text=f"output{i}",
                translation_type=TranslationType.SYNTAX,
                model_name="model",
            )

        # Get first 2
        logs = await repo.list_all(limit=2, offset=0)
        assert len(logs) == 2

        # Get next 2
        logs = await repo.list_all(limit=2, offset=2)
        assert len(logs) == 2

    async def test_list_by_type(self, session: AsyncSession) -> None:
        """Filter translation logs by translation type."""
        repo = TranslationLogRepository(session)

        await repo.create(
            input_text="syntax1",
            output_text="syntax_out1",
            translation_type=TranslationType.SYNTAX,
            model_name="model",
        )
        await repo.create(
            input_text="semantic1",
            output_text="semantic_out1",
            translation_type=TranslationType.SEMANTIC,
            model_name="model",
        )
        await repo.create(
            input_text="syntax2",
            output_text="syntax_out2",
            translation_type=TranslationType.SYNTAX,
            model_name="model",
        )

        syntax_logs = await repo.list_by_type(TranslationType.SYNTAX)
        assert len(syntax_logs) == 2
        assert all(log.translation_type == TranslationType.SYNTAX for log in syntax_logs)

        semantic_logs = await repo.list_by_type(TranslationType.SEMANTIC)
        assert len(semantic_logs) == 1
        assert semantic_logs[0].translation_type == TranslationType.SEMANTIC

    async def test_list_by_project(self, session: AsyncSession) -> None:
        """Filter translation logs by project ID."""
        project1 = await _create_project(session, "project1")
        project2 = await _create_project(session, "project2")
        repo = TranslationLogRepository(session)

        await repo.create(
            input_text="proj1_input",
            output_text="proj1_output",
            translation_type=TranslationType.SYNTAX,
            model_name="model",
            project_id=project1.id,
        )
        await repo.create(
            input_text="proj2_input",
            output_text="proj2_output",
            translation_type=TranslationType.SEMANTIC,
            model_name="model",
            project_id=project2.id,
        )
        await repo.create(
            input_text="no_project",
            output_text="no_project_out",
            translation_type=TranslationType.SYNTAX,
            model_name="model",
        )

        proj1_logs = await repo.list_by_project(project1.id)
        assert len(proj1_logs) == 1
        assert proj1_logs[0].project_id == project1.id

        proj2_logs = await repo.list_by_project(project2.id)
        assert len(proj2_logs) == 1
        assert proj2_logs[0].project_id == project2.id

    async def test_update_translation_log(self, session: AsyncSession) -> None:
        """Update a translation log."""
        repo = TranslationLogRepository(session)
        log = await repo.create(
            input_text="original",
            output_text="original_output",
            translation_type=TranslationType.SYNTAX,
            model_name="old-model",
        )

        updated = await repo.update(log.id, model_name="new-model")
        assert updated is not None
        assert updated.model_name == "new-model"
        assert updated.input_text == "original"

    async def test_delete_translation_log(self, session: AsyncSession) -> None:
        """Delete a translation log."""
        repo = TranslationLogRepository(session)
        log = await repo.create(
            input_text="to_delete",
            output_text="to_delete_output",
            translation_type=TranslationType.SEMANTIC,
            model_name="model",
        )

        deleted = await repo.delete(log.id)
        assert deleted is True

        fetched = await repo.get_by_id(log.id)
        assert fetched is None

    async def test_cascade_delete_with_project(self, session: AsyncSession) -> None:
        """Verify that translation logs are deleted when project is deleted."""
        project = await _create_project(session, "cascade-test")
        repo = TranslationLogRepository(session)
        project_repo = ProjectRepository(session)

        log = await repo.create(
            input_text="input",
            output_text="output",
            translation_type=TranslationType.SYNTAX,
            model_name="model",
            project_id=project.id,
        )

        await project_repo.delete(project.id)

        # Log should be cascade deleted
        fetched = await repo.get_by_id(log.id)
        assert fetched is None
