"""Tests for InstalledSkill repository."""

from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from jefe.data.database import get_engine
from jefe.data.models.base import Base
from jefe.data.models.harness import Harness
from jefe.data.models.installed_skill import InstallScope
from jefe.data.models.project import Project
from jefe.data.models.skill import Skill
from jefe.data.models.skill_source import SkillSource, SourceType, SyncStatus
from jefe.data.repositories.harness import HarnessRepository
from jefe.data.repositories.installed_skill import InstalledSkillRepository
from jefe.data.repositories.project import ProjectRepository
from jefe.data.repositories.skill import SkillRepository
from jefe.data.repositories.skill_source import SkillSourceRepository


@pytest.fixture(scope="function")
def test_db_path(tmp_path: Path) -> Path:
    """Create a temporary database file path."""
    return tmp_path / "installed_skills.db"


@pytest.fixture(scope="function")
async def session(test_db_path: Path) -> AsyncSession:
    """Create an async session with all tables."""
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


async def _create_test_data(
    session: AsyncSession,
) -> tuple[SkillSource, Skill, Harness, Project]:
    """Create test skill source, skill, harness, and project."""
    source_repo = SkillSourceRepository(session)
    skill_repo = SkillRepository(session)
    harness_repo = HarnessRepository(session)
    project_repo = ProjectRepository(session)

    source = await source_repo.create(
        name="test-source",
        source_type=SourceType.GIT,
        url="https://github.com/example/skills",
        sync_status=SyncStatus.SYNCED,
    )

    skill = await skill_repo.create(
        source_id=source.id,
        name="test-skill",
        display_name="Test Skill",
        version="1.0.0",
    )

    harness = await harness_repo.create(
        name="test-harness",
        display_name="Test Harness",
        version="1.0.0",
    )

    project = await project_repo.create(
        name="test-project",
        description="Test project",
    )

    return source, skill, harness, project


class TestInstalledSkillRepository:
    """InstalledSkill repository tests."""

    async def test_install_and_fetch_by_id(self, session: AsyncSession) -> None:
        """Install a skill and fetch it by ID."""
        source, skill, harness, project = await _create_test_data(session)

        repo = InstalledSkillRepository(session)
        installation = await repo.install(
            skill_id=skill.id,
            harness_id=harness.id,
            scope=InstallScope.PROJECT,
            project_id=project.id,
            installed_path="/path/to/skill",
            pinned_version="1.0.0",
        )

        fetched = await repo.get_by_id(installation.id)
        assert fetched is not None
        assert fetched.id == installation.id
        assert fetched.skill_id == skill.id
        assert fetched.harness_id == harness.id
        assert fetched.scope == InstallScope.PROJECT
        assert fetched.project_id == project.id
        assert fetched.installed_path == "/path/to/skill"
        assert fetched.pinned_version == "1.0.0"

    async def test_global_installation(self, session: AsyncSession) -> None:
        """Install a skill globally."""
        source, skill, harness, project = await _create_test_data(session)

        repo = InstalledSkillRepository(session)
        installation = await repo.install(
            skill_id=skill.id,
            harness_id=harness.id,
            scope=InstallScope.GLOBAL,
            project_id=None,
            installed_path="/global/path/to/skill",
        )

        fetched = await repo.get_by_id(installation.id)
        assert fetched is not None
        assert fetched.scope == InstallScope.GLOBAL
        assert fetched.project_id is None

    async def test_get_by_identity(self, session: AsyncSession) -> None:
        """Fetch an installation by its identity fields."""
        source, skill, harness, project = await _create_test_data(session)

        repo = InstalledSkillRepository(session)
        installation = await repo.install(
            skill_id=skill.id,
            harness_id=harness.id,
            scope=InstallScope.PROJECT,
            project_id=project.id,
            installed_path="/path/to/skill",
        )

        fetched = await repo.get_by_identity(
            skill_id=skill.id,
            harness_id=harness.id,
            scope=InstallScope.PROJECT,
            project_id=project.id,
        )
        assert fetched is not None
        assert fetched.id == installation.id

    async def test_get_by_project(self, session: AsyncSession) -> None:
        """Get all skills installed for a project."""
        source, skill, harness, project = await _create_test_data(session)

        repo = InstalledSkillRepository(session)

        # Install project-level skill
        await repo.install(
            skill_id=skill.id,
            harness_id=harness.id,
            scope=InstallScope.PROJECT,
            project_id=project.id,
            installed_path="/project/path",
        )

        # Install global skill
        skill_repo = SkillRepository(session)
        global_skill = await skill_repo.create(
            source_id=source.id,
            name="global-skill",
            display_name="Global Skill",
            version="1.0.0",
        )
        await repo.install(
            skill_id=global_skill.id,
            harness_id=harness.id,
            scope=InstallScope.GLOBAL,
            project_id=None,
            installed_path="/global/path",
        )

        # Get project skills (including global)
        project_skills = await repo.get_by_project(project.id, include_global=True)
        assert len(project_skills) == 2

        # Get only project-specific skills
        project_only = await repo.get_by_project(project.id, include_global=False)
        assert len(project_only) == 1
        assert project_only[0].scope == InstallScope.PROJECT

    async def test_get_by_harness(self, session: AsyncSession) -> None:
        """Get all skills installed for a harness."""
        source, skill, harness, project = await _create_test_data(session)

        repo = InstalledSkillRepository(session)
        await repo.install(
            skill_id=skill.id,
            harness_id=harness.id,
            scope=InstallScope.GLOBAL,
            project_id=None,
            installed_path="/harness/path",
        )

        harness_skills = await repo.get_by_harness(harness.id)
        assert len(harness_skills) == 1
        assert harness_skills[0].harness_id == harness.id

    async def test_get_global_installs(self, session: AsyncSession) -> None:
        """Get all globally installed skills."""
        source, skill, harness, project = await _create_test_data(session)

        repo = InstalledSkillRepository(session)

        # Install global skill
        await repo.install(
            skill_id=skill.id,
            harness_id=harness.id,
            scope=InstallScope.GLOBAL,
            project_id=None,
            installed_path="/global/path",
        )

        # Install project skill
        skill_repo = SkillRepository(session)
        project_skill = await skill_repo.create(
            source_id=source.id,
            name="project-skill",
            display_name="Project Skill",
            version="1.0.0",
        )
        await repo.install(
            skill_id=project_skill.id,
            harness_id=harness.id,
            scope=InstallScope.PROJECT,
            project_id=project.id,
            installed_path="/project/path",
        )

        global_skills = await repo.get_global_installs()
        assert len(global_skills) == 1
        assert global_skills[0].scope == InstallScope.GLOBAL

    async def test_uninstall(self, session: AsyncSession) -> None:
        """Uninstall a skill."""
        source, skill, harness, project = await _create_test_data(session)

        repo = InstalledSkillRepository(session)
        installation = await repo.install(
            skill_id=skill.id,
            harness_id=harness.id,
            scope=InstallScope.PROJECT,
            project_id=project.id,
            installed_path="/path/to/skill",
        )

        deleted = await repo.uninstall(installation.id)
        assert deleted is True
        assert await repo.get_by_id(installation.id) is None

    async def test_unique_constraint(self, session: AsyncSession) -> None:
        """Test unique constraint on installation identity."""
        source, skill, harness, project = await _create_test_data(session)

        repo = InstalledSkillRepository(session)
        await repo.install(
            skill_id=skill.id,
            harness_id=harness.id,
            scope=InstallScope.PROJECT,
            project_id=project.id,
            installed_path="/path/to/skill",
        )

        # Try to install the same skill again - should raise an exception due to unique constraint
        with pytest.raises(IntegrityError):
            await repo.install(
                skill_id=skill.id,
                harness_id=harness.id,
                scope=InstallScope.PROJECT,
                project_id=project.id,
                installed_path="/different/path",
            )

    async def test_relationship_loading(self, session: AsyncSession) -> None:
        """Test eager loading of relationships."""
        source, skill, harness, project = await _create_test_data(session)

        repo = InstalledSkillRepository(session)
        await repo.install(
            skill_id=skill.id,
            harness_id=harness.id,
            scope=InstallScope.PROJECT,
            project_id=project.id,
            installed_path="/path/to/skill",
        )

        installs = await repo.get_by_project(project.id)
        assert len(installs) == 1
        install = installs[0]

        # Check relationships are loaded
        assert install.skill.name == "test-skill"
        assert install.harness.name == "test-harness"
        assert install.project is not None
        assert install.project.name == "test-project"
