"""Tests for skill and skill source repositories."""

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from jefe.data.database import get_engine
from jefe.data.models.base import Base
from jefe.data.models.skill import Skill
from jefe.data.models.skill_source import SkillSource, SourceType, SyncStatus
from jefe.data.repositories.skill import SkillRepository
from jefe.data.repositories.skill_source import SkillSourceRepository


@pytest.fixture(scope="function")
def test_db_path(tmp_path: Path) -> Path:
    """Create a temporary database file path."""
    return tmp_path / "skills.db"


@pytest.fixture(scope="function")
async def session(test_db_path: Path) -> AsyncSession:
    """Create an async session with skill tables."""
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


async def _create_source_with_skill(
    session: AsyncSession,
    source_name: str = "example-repo",
    skill_name: str = "test-skill",
) -> tuple[SkillSource, Skill]:
    source_repo = SkillSourceRepository(session)
    skill_repo = SkillRepository(session)

    source = await source_repo.create(
        name=source_name,
        source_type=SourceType.GIT,
        url="https://github.com/example/skills",
        description="Test skills repository",
        sync_status=SyncStatus.SYNCED,
    )
    skill = await skill_repo.create(
        source_id=source.id,
        name=skill_name,
        display_name="Test Skill",
        description="A test skill",
        version="1.0.0",
        author="Test Author",
        tags='["testing", "example"]',
        metadata_json='{"key": "value"}',
    )
    return source, skill


class TestSkillSourceRepository:
    """SkillSource repository tests."""

    async def test_create_and_fetch_by_id(self, session: AsyncSession) -> None:
        """Create a skill source and fetch it by ID."""
        repo = SkillSourceRepository(session)
        source = await repo.create(
            name="test-source",
            source_type=SourceType.GIT,
            url="https://github.com/test/repo",
            description="Test repository",
            sync_status=SyncStatus.PENDING,
        )

        fetched = await repo.get_by_id(source.id)
        assert fetched is not None
        assert fetched.id == source.id
        assert fetched.name == "test-source"
        assert fetched.source_type == SourceType.GIT
        assert fetched.url == "https://github.com/test/repo"
        assert fetched.sync_status == SyncStatus.PENDING

    async def test_get_by_name(self, session: AsyncSession) -> None:
        """Fetch a skill source by name."""
        repo = SkillSourceRepository(session)
        await repo.create(
            name="unique-name",
            source_type=SourceType.MARKETPLACE,
            url="https://marketplace.example.com",
            sync_status=SyncStatus.SYNCED,
        )

        fetched = await repo.get_by_name("unique-name")
        assert fetched is not None
        assert fetched.name == "unique-name"
        assert fetched.source_type == SourceType.MARKETPLACE

    async def test_list_by_type(self, session: AsyncSession) -> None:
        """List skill sources by type."""
        repo = SkillSourceRepository(session)
        await repo.create(
            name="git-source-1",
            source_type=SourceType.GIT,
            url="https://github.com/example/repo1",
            sync_status=SyncStatus.SYNCED,
        )
        await repo.create(
            name="git-source-2",
            source_type=SourceType.GIT,
            url="https://github.com/example/repo2",
            sync_status=SyncStatus.SYNCED,
        )
        await repo.create(
            name="marketplace-source",
            source_type=SourceType.MARKETPLACE,
            url="https://marketplace.example.com",
            sync_status=SyncStatus.SYNCED,
        )

        git_sources = await repo.list_by_type(SourceType.GIT)
        assert len(git_sources) == 2

        marketplace_sources = await repo.list_by_type(SourceType.MARKETPLACE)
        assert len(marketplace_sources) == 1

    async def test_list_by_status(self, session: AsyncSession) -> None:
        """List skill sources by sync status."""
        repo = SkillSourceRepository(session)
        await repo.create(
            name="synced-source",
            source_type=SourceType.GIT,
            url="https://github.com/example/repo",
            sync_status=SyncStatus.SYNCED,
        )
        await repo.create(
            name="pending-source",
            source_type=SourceType.GIT,
            url="https://github.com/example/repo2",
            sync_status=SyncStatus.PENDING,
        )
        await repo.create(
            name="error-source",
            source_type=SourceType.GIT,
            url="https://github.com/example/repo3",
            sync_status=SyncStatus.ERROR,
        )

        synced_sources = await repo.list_by_status(SyncStatus.SYNCED)
        assert len(synced_sources) == 1

        error_sources = await repo.list_by_status(SyncStatus.ERROR)
        assert len(error_sources) == 1

    async def test_get_with_skills(self, session: AsyncSession) -> None:
        """Fetch a skill source with skills eagerly loaded."""
        source, skill = await _create_source_with_skill(session)

        repo = SkillSourceRepository(session)
        fetched = await repo.get_with_skills(source.id)

        assert fetched is not None
        assert fetched.id == source.id
        assert len(fetched.skills) == 1
        assert fetched.skills[0].id == skill.id

    async def test_list_all_with_filters(self, session: AsyncSession) -> None:
        """List all skill sources with optional filters."""
        repo = SkillSourceRepository(session)
        await repo.create(
            name="git-synced",
            source_type=SourceType.GIT,
            url="https://github.com/example/repo",
            sync_status=SyncStatus.SYNCED,
        )
        await repo.create(
            name="git-pending",
            source_type=SourceType.GIT,
            url="https://github.com/example/repo2",
            sync_status=SyncStatus.PENDING,
        )
        await repo.create(
            name="marketplace-synced",
            source_type=SourceType.MARKETPLACE,
            url="https://marketplace.example.com",
            sync_status=SyncStatus.SYNCED,
        )

        # No filters
        all_sources = await repo.list_all()
        assert len(all_sources) == 3

        # Filter by type
        git_sources = await repo.list_all(source_type=SourceType.GIT)
        assert len(git_sources) == 2

        # Filter by status
        synced_sources = await repo.list_all(sync_status=SyncStatus.SYNCED)
        assert len(synced_sources) == 2

        # Filter by both
        git_synced = await repo.list_all(
            source_type=SourceType.GIT, sync_status=SyncStatus.SYNCED
        )
        assert len(git_synced) == 1

    async def test_update_and_delete(self, session: AsyncSession) -> None:
        """Update and delete a skill source."""
        repo = SkillSourceRepository(session)
        source = await repo.create(
            name="update-me",
            source_type=SourceType.GIT,
            url="https://github.com/example/old",
            sync_status=SyncStatus.PENDING,
        )

        updated = await repo.update(
            source.id, url="https://github.com/example/new", sync_status=SyncStatus.SYNCED
        )
        assert updated is not None
        assert updated.url == "https://github.com/example/new"
        assert updated.sync_status == SyncStatus.SYNCED

        deleted = await repo.delete(source.id)
        assert deleted is True
        assert await repo.get_by_id(source.id) is None

    async def test_cascade_delete_skills(self, session: AsyncSession) -> None:
        """Deleting a skill source removes its skills."""
        source, skill = await _create_source_with_skill(session, source_name="cascade")

        repo = SkillSourceRepository(session)
        deleted = await repo.delete(source.id)
        assert deleted is True

        result = await session.execute(select(Skill).where(Skill.id == skill.id))
        assert result.scalar_one_or_none() is None


class TestSkillRepository:
    """Skill repository tests."""

    async def test_create_and_fetch_by_id(self, session: AsyncSession) -> None:
        """Create a skill and fetch it by ID."""
        source, skill = await _create_source_with_skill(session)

        repo = SkillRepository(session)
        fetched = await repo.get_by_id(skill.id)

        assert fetched is not None
        assert fetched.id == skill.id
        assert fetched.name == "test-skill"
        assert fetched.display_name == "Test Skill"
        assert fetched.source_id == source.id

    async def test_get_by_name(self, session: AsyncSession) -> None:
        """Fetch a skill by name."""
        _source, _skill = await _create_source_with_skill(session, skill_name="unique-skill")

        repo = SkillRepository(session)
        fetched = await repo.get_by_name("unique-skill")

        assert fetched is not None
        assert fetched.name == "unique-skill"

    async def test_list_by_source(self, session: AsyncSession) -> None:
        """List all skills from a specific source."""
        source, _skill1 = await _create_source_with_skill(session, skill_name="skill-1")

        skill_repo = SkillRepository(session)
        await skill_repo.create(
            source_id=source.id,
            name="skill-2",
            display_name="Skill 2",
            description="Another skill",
        )

        skills = await skill_repo.list_by_source(source.id)
        assert len(skills) == 2
        assert skills[0].source.id == source.id

    async def test_list_by_name(self, session: AsyncSession) -> None:
        """List all skills matching a specific name."""
        _source1, _skill1 = await _create_source_with_skill(
            session, source_name="source-1", skill_name="duplicate"
        )

        source_repo = SkillSourceRepository(session)
        source2 = await source_repo.create(
            name="source-2",
            source_type=SourceType.GIT,
            url="https://github.com/other/repo",
            sync_status=SyncStatus.SYNCED,
        )

        skill_repo = SkillRepository(session)
        await skill_repo.create(
            source_id=source2.id,
            name="duplicate",
            display_name="Duplicate Skill",
        )

        skills = await skill_repo.list_by_name("duplicate")
        assert len(skills) == 2

    async def test_search_by_tag(self, session: AsyncSession) -> None:
        """Search skills by tag."""
        _source, skill = await _create_source_with_skill(session)

        repo = SkillRepository(session)
        skills = await repo.search_by_tag("testing")
        assert len(skills) == 1
        assert skills[0].id == skill.id

        skills = await repo.search_by_tag("example")
        assert len(skills) == 1

        skills = await repo.search_by_tag("nonexistent")
        assert len(skills) == 0

    async def test_list_by_author(self, session: AsyncSession) -> None:
        """List all skills by a specific author."""
        source, _skill1 = await _create_source_with_skill(session, skill_name="skill-1")

        skill_repo = SkillRepository(session)
        await skill_repo.create(
            source_id=source.id,
            name="skill-2",
            author="Test Author",
        )
        await skill_repo.create(
            source_id=source.id,
            name="skill-3",
            author="Other Author",
        )

        skills = await skill_repo.list_by_author("Test Author")
        assert len(skills) == 2

        skills = await skill_repo.list_by_author("Other Author")
        assert len(skills) == 1

    async def test_get_with_source(self, session: AsyncSession) -> None:
        """Fetch a skill with source eagerly loaded."""
        source, skill = await _create_source_with_skill(session)

        repo = SkillRepository(session)
        fetched = await repo.get_with_source(skill.id)

        assert fetched is not None
        assert fetched.id == skill.id
        assert fetched.source.id == source.id
        assert fetched.source.name == "example-repo"

    async def test_list_all_with_filters(self, session: AsyncSession) -> None:
        """List all skills with optional filters."""
        source1, _skill1 = await _create_source_with_skill(
            session, source_name="source-1", skill_name="skill-1"
        )

        source_repo = SkillSourceRepository(session)
        source2 = await source_repo.create(
            name="source-2",
            source_type=SourceType.GIT,
            url="https://github.com/other/repo",
            sync_status=SyncStatus.SYNCED,
        )

        skill_repo = SkillRepository(session)
        await skill_repo.create(
            source_id=source2.id,
            name="skill-2",
            author="Author A",
        )
        await skill_repo.create(
            source_id=source2.id,
            name="skill-3",
            author="Author B",
        )

        # No filters
        all_skills = await skill_repo.list_all()
        assert len(all_skills) == 3

        # Filter by source
        source1_skills = await skill_repo.list_all(source_id=source1.id)
        assert len(source1_skills) == 1

        # Filter by author
        author_a_skills = await skill_repo.list_all(author="Author A")
        assert len(author_a_skills) == 1

        # Filter by both
        source2_author_b = await skill_repo.list_all(source_id=source2.id, author="Author B")
        assert len(source2_author_b) == 1

    async def test_skill_json_helpers(self, session: AsyncSession) -> None:
        """Test skill JSON helper methods."""
        _source, skill = await _create_source_with_skill(session)

        # Test tags
        tags = skill.get_tags_list()
        assert tags == ["testing", "example"]

        skill.set_tags_list(["new", "tags"])
        assert '"new"' in skill.tags
        assert '"tags"' in skill.tags

        # Test metadata
        metadata = skill.get_metadata_dict()
        assert metadata == {"key": "value"}

        skill.set_metadata_dict({"new_key": "new_value"})
        assert '"new_key"' in skill.metadata_json
        assert '"new_value"' in skill.metadata_json

    async def test_update_and_delete_skill(self, session: AsyncSession) -> None:
        """Update and delete a skill."""
        _source, skill = await _create_source_with_skill(session)

        repo = SkillRepository(session)
        updated = await repo.update(skill.id, version="2.0.0", author="New Author")
        assert updated is not None
        assert updated.version == "2.0.0"
        assert updated.author == "New Author"

        deleted = await repo.delete(skill.id)
        assert deleted is True
        assert await repo.get_by_id(skill.id) is None
