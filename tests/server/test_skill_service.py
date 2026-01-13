"""Tests for skill installation service."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from jefe.adapters.claude_code import ClaudeCodeAdapter
from jefe.data.models.harness import Harness
from jefe.data.models.installed_skill import InstalledSkill, InstallScope
from jefe.data.models.manifestation import Manifestation, ManifestationType
from jefe.data.models.project import Project
from jefe.data.models.skill import Skill
from jefe.data.models.skill_source import SkillSource, SourceType
from jefe.data.repositories.harness import HarnessRepository
from jefe.data.repositories.installed_skill import InstalledSkillRepository
from jefe.data.repositories.project import ProjectRepository
from jefe.data.repositories.skill import SkillRepository
from jefe.server.services.skill import SkillInstallError, SkillService


@pytest.fixture
def mock_session() -> AsyncSession:
    """Create a mock async session."""
    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    return session  # type: ignore


@pytest.fixture
def skill_service(mock_session: AsyncSession, tmp_path: Path) -> SkillService:
    """Create a SkillService instance with a temporary data directory."""
    return SkillService(mock_session, data_dir=tmp_path / "skills")


@pytest.fixture
def mock_skill_source() -> SkillSource:
    """Create a mock skill source."""
    source = MagicMock(spec=SkillSource)
    source.id = 1
    source.name = "test-source"
    source.source_type = SourceType.GIT
    source.url = "https://github.com/test/skills"
    return source


@pytest.fixture
def mock_skill(mock_skill_source: SkillSource) -> Skill:
    """Create a mock skill."""
    skill = MagicMock(spec=Skill)
    skill.id = 1
    skill.source_id = mock_skill_source.id
    skill.name = "test-skill"
    skill.display_name = "Test Skill"
    skill.version = "1.0.0"
    skill.source = mock_skill_source
    return skill


@pytest.fixture
def mock_harness() -> Harness:
    """Create a mock harness."""
    harness = MagicMock(spec=Harness)
    harness.id = 1
    harness.name = "claude-code"
    harness.display_name = "Claude Code"
    return harness


@pytest.fixture
def mock_project(tmp_path: Path) -> Project:
    """Create a mock project with a local manifestation."""
    project = MagicMock(spec=Project)
    project.id = 1
    project.name = "test-project"

    manifestation = MagicMock(spec=Manifestation)
    manifestation.type = ManifestationType.LOCAL
    manifestation.path = str(tmp_path / "project")

    project.manifestations = [manifestation]
    return project


@pytest.fixture
def skill_source_dir(tmp_path: Path, mock_skill: Skill) -> Path:
    """Create a mock skill source directory with files."""
    skill_dir = tmp_path / "data" / "skill_repos" / f"source_{mock_skill.source_id}" / mock_skill.name
    skill_dir.mkdir(parents=True)

    # Create SKILL.md file
    (skill_dir / "SKILL.md").write_text("""---
name: test-skill
display_name: Test Skill
version: 1.0.0
---

# Test Skill
This is a test skill.
""")

    # Create skill.py file
    (skill_dir / "skill.py").write_text("""
def run():
    print("Test skill running")
""")

    return skill_dir


class TestSkillService:
    """Tests for SkillService."""

    async def test_list_skills(self, skill_service: SkillService) -> None:
        """Test listing all skills."""
        mock_skills = [MagicMock(spec=Skill), MagicMock(spec=Skill)]

        with patch.object(
            SkillRepository,
            "list_all",
            return_value=mock_skills,
        ):
            skills = await skill_service.list_skills()
            assert len(skills) == 2

    async def test_list_skills_by_source(self, skill_service: SkillService) -> None:
        """Test filtering skills by source ID."""
        mock_skills = [MagicMock(spec=Skill)]

        with patch.object(
            SkillRepository,
            "list_all",
            return_value=mock_skills,
        ):
            skills = await skill_service.list_skills(source_id=1)
            assert len(skills) == 1

    async def test_list_skills_by_name(self, skill_service: SkillService) -> None:
        """Test filtering skills by name."""
        mock_skills = [MagicMock(spec=Skill)]

        with patch.object(
            SkillRepository,
            "list_by_name",
            return_value=mock_skills,
        ):
            skills = await skill_service.list_skills(name="test-skill")
            assert len(skills) == 1

    async def test_list_skills_by_tag(self, skill_service: SkillService) -> None:
        """Test filtering skills by tag."""
        mock_skills = [MagicMock(spec=Skill)]

        with patch.object(
            SkillRepository,
            "search_by_tag",
            return_value=mock_skills,
        ):
            skills = await skill_service.list_skills(tag="test")
            assert len(skills) == 1

    async def test_get_skill(self, skill_service: SkillService, mock_skill: Skill) -> None:
        """Test getting a skill by ID."""
        with patch.object(
            SkillRepository,
            "get_with_source",
            return_value=mock_skill,
        ):
            skill = await skill_service.get_skill(1)
            assert skill is not None
            assert skill.id == 1

    async def test_install_skill_global(
        self,
        skill_service: SkillService,
        mock_skill: Skill,
        mock_harness: Harness,
        skill_source_dir: Path,
        tmp_path: Path,
    ) -> None:
        """Test installing a skill globally."""
        # Change cwd to tmp_path so skill source path resolves correctly
        original_cwd = Path.cwd()
        import os
        os.chdir(tmp_path)

        try:
            global_skills_path = tmp_path / "home" / ".claude" / "skills" / "test-skill"
            mock_installed = MagicMock(spec=InstalledSkill)
            mock_installed.id = 1
            mock_installed.skill_id = mock_skill.id
            mock_installed.harness_id = mock_harness.id
            mock_installed.scope = InstallScope.GLOBAL
            mock_installed.installed_path = str(global_skills_path)

            with (
                patch.object(SkillRepository, "get_with_source", return_value=mock_skill),
                patch.object(HarnessRepository, "get_by_id", return_value=mock_harness),
                patch.object(InstalledSkillRepository, "get_by_identity", return_value=None),
                patch.object(InstalledSkillRepository, "install", return_value=mock_installed),
                patch("jefe.server.services.skill.get_adapter") as mock_get_adapter,
                patch("jefe.adapters.claude_code.Path.home", return_value=tmp_path / "home"),
            ):
                # Setup adapter mock
                adapter = ClaudeCodeAdapter()
                mock_get_adapter.return_value = adapter

                # Install the skill
                result = await skill_service.install_skill(
                    skill_id=1,
                    harness_id=1,
                    scope=InstallScope.GLOBAL,
                )

                # Verify installation
                assert result.skill_id == 1
                assert result.harness_id == 1
                assert result.scope == InstallScope.GLOBAL

                # Verify files were copied to mocked home directory
                assert global_skills_path.exists()
                assert (global_skills_path / "SKILL.md").exists()
                assert (global_skills_path / "skill.py").exists()
        finally:
            os.chdir(original_cwd)

    async def test_install_skill_project(
        self,
        skill_service: SkillService,
        mock_skill: Skill,
        mock_harness: Harness,
        mock_project: Project,
        skill_source_dir: Path,
        tmp_path: Path,
    ) -> None:
        """Test installing a skill to a project."""
        # Change cwd to tmp_path so skill source path resolves correctly
        original_cwd = Path.cwd()
        import os
        os.chdir(tmp_path)

        try:
            project_path = Path(mock_project.manifestations[0].path)
            project_path.mkdir(parents=True, exist_ok=True)

            mock_installed = MagicMock(spec=InstalledSkill)
            mock_installed.id = 2
            mock_installed.skill_id = mock_skill.id
            mock_installed.harness_id = mock_harness.id
            mock_installed.scope = InstallScope.PROJECT
            mock_installed.project_id = mock_project.id
            mock_installed.installed_path = str(project_path / ".claude" / "skills" / "test-skill")

            with (
                patch.object(SkillRepository, "get_with_source", return_value=mock_skill),
                patch.object(HarnessRepository, "get_by_id", return_value=mock_harness),
                patch.object(ProjectRepository, "get_with_manifestations", return_value=mock_project),
                patch.object(InstalledSkillRepository, "get_by_identity", return_value=None),
                patch.object(InstalledSkillRepository, "install", return_value=mock_installed),
                patch("jefe.server.services.skill.get_adapter") as mock_get_adapter,
            ):
                # Setup adapter mock
                adapter = ClaudeCodeAdapter()
                mock_get_adapter.return_value = adapter

                # Install the skill
                result = await skill_service.install_skill(
                    skill_id=1,
                    harness_id=1,
                    scope=InstallScope.PROJECT,
                    project_id=1,
                )

                # Verify installation
                assert result.skill_id == 1
                assert result.harness_id == 1
                assert result.scope == InstallScope.PROJECT
                assert result.project_id == 1

                # Verify files were copied
                installed_path = project_path / ".claude" / "skills" / "test-skill"
                assert installed_path.exists()
                assert (installed_path / "SKILL.md").exists()
                assert (installed_path / "skill.py").exists()
        finally:
            os.chdir(original_cwd)

    async def test_install_skill_already_installed(
        self,
        skill_service: SkillService,
        mock_skill: Skill,
        mock_harness: Harness,
    ) -> None:
        """Test installing a skill that's already installed."""
        mock_existing = MagicMock(spec=InstalledSkill)

        with (
            patch.object(SkillRepository, "get_with_source", return_value=mock_skill),
            patch.object(HarnessRepository, "get_by_id", return_value=mock_harness),
            patch.object(InstalledSkillRepository, "get_by_identity", return_value=mock_existing),
            pytest.raises(SkillInstallError, match="already installed"),
        ):
            await skill_service.install_skill(
                skill_id=1,
                harness_id=1,
                scope=InstallScope.GLOBAL,
            )

    async def test_install_skill_not_found(self, skill_service: SkillService) -> None:
        """Test installing a non-existent skill."""
        with (
            patch.object(SkillRepository, "get_with_source", return_value=None),
            pytest.raises(SkillInstallError, match="not found"),
        ):
            await skill_service.install_skill(
                skill_id=999,
                harness_id=1,
                scope=InstallScope.GLOBAL,
            )

    async def test_install_skill_harness_not_found(
        self,
        skill_service: SkillService,
        mock_skill: Skill,
    ) -> None:
        """Test installing to a non-existent harness."""
        with (
            patch.object(SkillRepository, "get_with_source", return_value=mock_skill),
            patch.object(HarnessRepository, "get_by_id", return_value=None),
            pytest.raises(SkillInstallError, match="not found"),
        ):
            await skill_service.install_skill(
                skill_id=1,
                harness_id=999,
                scope=InstallScope.GLOBAL,
            )

    async def test_install_skill_source_not_synced(
        self,
        skill_service: SkillService,
        mock_skill: Skill,
        mock_harness: Harness,
        tmp_path: Path,
    ) -> None:
        """Test installing a skill whose source hasn't been synced."""
        # Change cwd to tmp_path
        original_cwd = Path.cwd()
        import os
        os.chdir(tmp_path)

        try:
            with (
                patch.object(SkillRepository, "get_with_source", return_value=mock_skill),
                patch.object(HarnessRepository, "get_by_id", return_value=mock_harness),
                patch.object(InstalledSkillRepository, "get_by_identity", return_value=None),
                pytest.raises(SkillInstallError, match="Skill source not found"),
            ):
                await skill_service.install_skill(
                    skill_id=1,
                    harness_id=1,
                    scope=InstallScope.GLOBAL,
                )
        finally:
            os.chdir(original_cwd)

    async def test_install_skill_project_scope_without_project_id(
        self,
        skill_service: SkillService,
        mock_skill: Skill,
        mock_harness: Harness,
    ) -> None:
        """Test project scope installation without providing project_id."""
        with (
            patch.object(SkillRepository, "get_with_source", return_value=mock_skill),
            patch.object(HarnessRepository, "get_by_id", return_value=mock_harness),
            pytest.raises(SkillInstallError, match="project_id is required"),
        ):
            await skill_service.install_skill(
                skill_id=1,
                harness_id=1,
                scope=InstallScope.PROJECT,
            )

    async def test_install_skill_project_not_found(
        self,
        skill_service: SkillService,
        mock_skill: Skill,
        mock_harness: Harness,
    ) -> None:
        """Test project scope installation with non-existent project."""
        with (
            patch.object(SkillRepository, "get_with_source", return_value=mock_skill),
            patch.object(HarnessRepository, "get_by_id", return_value=mock_harness),
            patch.object(ProjectRepository, "get_with_manifestations", return_value=None),
            pytest.raises(SkillInstallError, match="not found"),
        ):
            await skill_service.install_skill(
                skill_id=1,
                harness_id=1,
                scope=InstallScope.PROJECT,
                project_id=999,
            )

    async def test_install_skill_update_existing(
        self,
        skill_service: SkillService,
        mock_skill: Skill,
        mock_harness: Harness,
        skill_source_dir: Path,
        tmp_path: Path,
    ) -> None:
        """Test that installing over an existing skill updates it."""
        original_cwd = Path.cwd()
        import os
        os.chdir(tmp_path)

        try:
            # Create existing installation directory
            installed_path = tmp_path / "home" / ".claude" / "skills" / "test-skill"
            installed_path.mkdir(parents=True)
            (installed_path / "old_file.txt").write_text("old content")

            mock_installed = MagicMock(spec=InstalledSkill)
            mock_installed.id = 1
            mock_installed.skill_id = mock_skill.id
            mock_installed.harness_id = mock_harness.id
            mock_installed.scope = InstallScope.GLOBAL
            mock_installed.installed_path = str(installed_path)

            with (
                patch.object(SkillRepository, "get_with_source", return_value=mock_skill),
                patch.object(HarnessRepository, "get_by_id", return_value=mock_harness),
                patch.object(InstalledSkillRepository, "get_by_identity", return_value=None),
                patch.object(InstalledSkillRepository, "install", return_value=mock_installed),
                patch("jefe.server.services.skill.get_adapter") as mock_get_adapter,
                patch("jefe.adapters.claude_code.Path.home", return_value=tmp_path / "home"),
            ):
                adapter = ClaudeCodeAdapter()
                mock_get_adapter.return_value = adapter

                # Install should overwrite
                await skill_service.install_skill(
                    skill_id=1,
                    harness_id=1,
                    scope=InstallScope.GLOBAL,
                )

                # Old file should be gone, new files present
                assert not (installed_path / "old_file.txt").exists()
                assert (installed_path / "SKILL.md").exists()
                assert (installed_path / "skill.py").exists()
        finally:
            os.chdir(original_cwd)

    async def test_uninstall_skill(
        self,
        skill_service: SkillService,
        mock_harness: Harness,
        tmp_path: Path,
    ) -> None:
        """Test uninstalling a skill."""
        # Create installed skill directory
        installed_path = tmp_path / ".claude" / "skills" / "test-skill"
        installed_path.mkdir(parents=True)
        (installed_path / "SKILL.md").write_text("test")

        mock_installed = MagicMock(spec=InstalledSkill)
        mock_installed.id = 1
        mock_installed.harness_id = mock_harness.id
        mock_installed.installed_path = str(installed_path)

        with (
            patch.object(InstalledSkillRepository, "get_by_id", return_value=mock_installed),
            patch.object(HarnessRepository, "get_by_id", return_value=mock_harness),
            patch.object(InstalledSkillRepository, "uninstall", return_value=True),
            patch("jefe.server.services.skill.get_adapter") as mock_get_adapter,
        ):
            adapter = ClaudeCodeAdapter()
            mock_get_adapter.return_value = adapter

            result = await skill_service.uninstall_skill(1)

            assert result is True
            assert not installed_path.exists()

    async def test_uninstall_skill_not_found(self, skill_service: SkillService) -> None:
        """Test uninstalling a non-existent skill."""
        with patch.object(InstalledSkillRepository, "get_by_id", return_value=None):
            result = await skill_service.uninstall_skill(999)
            assert result is False

    async def test_uninstall_skill_path_already_removed(
        self,
        skill_service: SkillService,
        mock_harness: Harness,
        tmp_path: Path,
    ) -> None:
        """Test uninstalling a skill when files are already gone."""
        # Don't create the directory - simulate already removed
        installed_path = tmp_path / ".claude" / "skills" / "test-skill"

        mock_installed = MagicMock(spec=InstalledSkill)
        mock_installed.id = 1
        mock_installed.harness_id = mock_harness.id
        mock_installed.installed_path = str(installed_path)

        with (
            patch.object(InstalledSkillRepository, "get_by_id", return_value=mock_installed),
            patch.object(HarnessRepository, "get_by_id", return_value=mock_harness),
            patch.object(InstalledSkillRepository, "uninstall", return_value=True),
            patch("jefe.server.services.skill.get_adapter") as mock_get_adapter,
        ):
            adapter = ClaudeCodeAdapter()
            mock_get_adapter.return_value = adapter

            # Should not raise error even if path doesn't exist
            result = await skill_service.uninstall_skill(1)
            assert result is True
