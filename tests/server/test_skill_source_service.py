"""Tests for skill source sync service."""

import shutil
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from git import Repo
from sqlalchemy.ext.asyncio import AsyncSession

from jefe.data.models.skill_source import SourceType
from jefe.data.repositories.skill import SkillRepository
from jefe.data.repositories.skill_source import SkillSourceRepository
from jefe.server.services.skill_source import (
    SkillSourceService,
    SkillSourceSyncError,
)


@pytest.fixture
def mock_session() -> AsyncSession:
    """Create a mock async session."""
    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    return session  # type: ignore


@pytest.fixture
def skill_source_service(mock_session: AsyncSession, tmp_path: Path) -> SkillSourceService:
    """Create a SkillSourceService instance with a temporary data directory."""
    return SkillSourceService(mock_session, data_dir=tmp_path / "repos")


class TestSkillSourceService:
    """Tests for SkillSourceService."""

    async def test_get_repo_path(
        self,
        skill_source_service: SkillSourceService,
        tmp_path: Path,
    ) -> None:
        """Test getting repository path for a source."""
        repo_path = skill_source_service._get_repo_path(123)
        assert repo_path == tmp_path / "repos" / "source_123"

    async def test_data_dir_creation(self, mock_session: AsyncSession, tmp_path: Path) -> None:
        """Test that data directory is created if it doesn't exist."""
        data_dir = tmp_path / "new_repos"
        assert not data_dir.exists()

        service = SkillSourceService(mock_session, data_dir=data_dir)
        assert data_dir.exists()
        assert service.data_dir == data_dir

    async def test_sync_source_not_found(
        self,
        skill_source_service: SkillSourceService,
    ) -> None:
        """Test syncing a non-existent source."""
        with (
            patch.object(
                SkillSourceRepository,
                "get_by_id",
                return_value=None,
            ),
            pytest.raises(SkillSourceSyncError, match="not found"),
        ):
            await skill_source_service.sync_source(999)

    async def test_sync_source_invalid_type(
        self,
        skill_source_service: SkillSourceService,
    ) -> None:
        """Test syncing a non-git source."""
        mock_source = MagicMock()
        mock_source.source_type = SourceType.MARKETPLACE

        with (
            patch.object(
                SkillSourceRepository,
                "get_by_id",
                return_value=mock_source,
            ),
            pytest.raises(SkillSourceSyncError, match="Cannot sync source type"),
        ):
            await skill_source_service.sync_source(1)

    async def test_clone_repo(
        self,
        skill_source_service: SkillSourceService,
        tmp_path: Path,
    ) -> None:
        """Test cloning a git repository."""
        # Create a mock git repo to clone from
        source_repo = tmp_path / "source"
        source_repo.mkdir()
        Repo.init(source_repo)

        # Add a file to the source repo
        (source_repo / "test.txt").write_text("test content")
        repo = Repo(source_repo)
        repo.index.add(["test.txt"])
        repo.index.commit("Initial commit")

        # Clone the repo
        dest_repo = tmp_path / "dest"
        skill_source_service._clone_repo(str(source_repo), dest_repo)

        # Verify clone
        assert dest_repo.exists()
        assert (dest_repo / ".git").exists()
        assert (dest_repo / "test.txt").exists()

    async def test_remove_repo(
        self,
        skill_source_service: SkillSourceService,
        tmp_path: Path,
    ) -> None:
        """Test removing a repository directory."""
        repo_dir = tmp_path / "test_repo"
        repo_dir.mkdir()
        (repo_dir / "file.txt").write_text("test")

        skill_source_service._remove_repo(repo_dir)
        assert not repo_dir.exists()

    async def test_sync_git_repo_clone(
        self,
        skill_source_service: SkillSourceService,
        tmp_path: Path,
    ) -> None:
        """Test syncing a git repo when it doesn't exist locally."""
        source_repo = tmp_path / "source"
        source_repo.mkdir()
        Repo.init(source_repo)
        (source_repo / "README.md").write_text("# Test Repo")
        repo = Repo(source_repo)
        repo.index.add(["README.md"])
        repo.index.commit("Initial commit")

        dest_repo = tmp_path / "dest"
        await skill_source_service._sync_git_repo(str(source_repo), dest_repo)

        assert dest_repo.exists()
        assert (dest_repo / ".git").exists()
        assert (dest_repo / "README.md").exists()

    async def test_sync_git_repo_pull(
        self,
        skill_source_service: SkillSourceService,
        tmp_path: Path,
    ) -> None:
        """Test syncing a git repo when it already exists locally."""
        # Create source repo
        source_repo = tmp_path / "source"
        source_repo.mkdir()
        Repo.init(source_repo, bare=True)

        # Create a working clone
        working_clone = tmp_path / "working"
        working_clone.mkdir()
        working_git = Repo.init(working_clone, initial_branch="main")

        # Add a file and push to bare repo
        (working_clone / "file1.txt").write_text("content 1")
        working_git.index.add(["file1.txt"])
        working_git.index.commit("First commit")
        working_git.create_remote("origin", str(source_repo))
        working_git.remotes.origin.push("main:main")

        # Clone to destination
        dest_repo = tmp_path / "dest"
        Repo.clone_from(str(source_repo), str(dest_repo))

        # Add another file to source
        (working_clone / "file2.txt").write_text("content 2")
        working_git.index.add(["file2.txt"])
        working_git.index.commit("Second commit")
        working_git.remotes.origin.push("main:main")

        # Pull updates
        await skill_source_service._sync_git_repo(str(source_repo), dest_repo)

        assert (dest_repo / "file1.txt").exists()
        assert (dest_repo / "file2.txt").exists()

    async def test_create_or_update_skill_new(
        self,
        skill_source_service: SkillSourceService,
    ) -> None:
        """Test creating a new skill from metadata."""
        metadata = {
            "name": "test-skill",
            "display_name": "Test Skill",
            "description": "A test skill",
            "version": "1.0.0",
            "author": "Test Author",
            "tags": ["test"],
            "metadata": {"key": "value"},
        }

        mock_skill = MagicMock()
        mock_skill.id = 1
        mock_skill.name = "test-skill"

        with (
            patch.object(
                SkillRepository,
                "list_by_source",
                return_value=[],
            ),
            patch.object(
                SkillRepository,
                "create",
                return_value=mock_skill,
            ),
        ):
            skill = await skill_source_service._create_or_update_skill(1, metadata)
            assert skill.name == "test-skill"

    async def test_create_or_update_skill_update(
        self,
        skill_source_service: SkillSourceService,
    ) -> None:
        """Test updating an existing skill from metadata."""
        metadata = {
            "name": "test-skill",
            "display_name": "Updated Test Skill",
            "description": "Updated description",
            "version": "2.0.0",
            "author": "Test Author",
            "tags": ["test", "updated"],
        }

        existing_skill = MagicMock()
        existing_skill.id = 1
        existing_skill.name = "test-skill"

        updated_skill = MagicMock()
        updated_skill.id = 1
        updated_skill.name = "test-skill"
        updated_skill.display_name = "Updated Test Skill"

        with (
            patch.object(
                SkillRepository,
                "list_by_source",
                return_value=[existing_skill],
            ),
            patch.object(
                SkillRepository,
                "update",
                return_value=None,
            ),
            patch.object(
                SkillRepository,
                "get_by_id",
                return_value=updated_skill,
            ),
        ):
            skill = await skill_source_service._create_or_update_skill(1, metadata)
            assert skill.display_name == "Updated Test Skill"

    async def test_sync_source_success(
        self,
        skill_source_service: SkillSourceService,
        tmp_path: Path,
    ) -> None:
        """Test successful source sync."""
        # Create a mock source repo with SKILL.md files
        source_repo_path = tmp_path / "source_repo"
        source_repo_path.mkdir()

        # Initialize git repo
        git_repo = Repo.init(source_repo_path)
        (source_repo_path / "README.md").write_text("# Test")
        git_repo.index.add(["README.md"])
        git_repo.index.commit("Initial commit")

        # Copy sample skills to source repo
        sample_repo = Path("tests/fixtures/sample_skills_repo")
        shutil.copytree(sample_repo, source_repo_path / "skills")
        git_repo.index.add(["skills"])
        git_repo.index.commit("Add skills")

        # Mock source
        mock_source = MagicMock()
        mock_source.id = 1
        mock_source.source_type = SourceType.GIT
        mock_source.url = str(source_repo_path)

        mock_skill = MagicMock()
        mock_skill.id = 1

        with (
            patch.object(
                SkillSourceRepository,
                "get_by_id",
                return_value=mock_source,
            ),
            patch.object(SkillSourceRepository, "update", return_value=None),
            patch.object(
                SkillRepository,
                "list_by_source",
                return_value=[],
            ),
            patch.object(
                SkillRepository,
                "create",
                return_value=mock_skill,
            ),
        ):
            skills_updated = await skill_source_service.sync_source(1)
            assert skills_updated == 2  # Two SKILL.md files in fixtures

    async def test_list_sources(
        self,
        skill_source_service: SkillSourceService,
    ) -> None:
        """Test listing skill sources."""
        mock_sources = [MagicMock(), MagicMock()]

        with patch.object(
            SkillSourceRepository,
            "list_all",
            return_value=mock_sources,
        ):
            sources = await skill_source_service.list_sources()
            assert len(sources) == 2

    async def test_get_source(
        self,
        skill_source_service: SkillSourceService,
    ) -> None:
        """Test getting a skill source by ID."""
        mock_source = MagicMock()
        mock_source.id = 1

        with patch.object(
            SkillSourceRepository,
            "get_by_id",
            return_value=mock_source,
        ):
            source = await skill_source_service.get_source(1)
            assert source is not None
            assert source.id == 1

    async def test_list_skills(
        self,
        skill_source_service: SkillSourceService,
    ) -> None:
        """Test listing skills."""
        mock_skills = [MagicMock(), MagicMock(), MagicMock()]

        with patch.object(
            SkillRepository,
            "list_all",
            return_value=mock_skills,
        ):
            skills = await skill_source_service.list_skills()
            assert len(skills) == 3
