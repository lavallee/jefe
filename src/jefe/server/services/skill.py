"""Service for managing skills and skill installations."""

import logging
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from jefe.adapters.registry import get_adapter
from jefe.data.models.harness_config import ConfigScope
from jefe.data.models.installed_skill import InstalledSkill, InstallScope
from jefe.data.models.manifestation import ManifestationType
from jefe.data.models.skill import Skill
from jefe.data.repositories.harness import HarnessRepository
from jefe.data.repositories.installed_skill import InstalledSkillRepository
from jefe.data.repositories.project import ProjectRepository
from jefe.data.repositories.skill import SkillRepository

logger = logging.getLogger(__name__)


class SkillInstallError(Exception):
    """Raised when skill installation fails."""

    pass


class SkillService:
    """Service for managing skills and installations."""

    def __init__(self, session: AsyncSession, data_dir: Path | None = None) -> None:
        """
        Initialize the skill service.

        Args:
            session: Database session
            data_dir: Directory for storing skill files (default: ./data/skills)
        """
        self.session = session
        self.skill_repo = SkillRepository(session)
        self.installed_skill_repo = InstalledSkillRepository(session)
        self.harness_repo = HarnessRepository(session)
        self.project_repo = ProjectRepository(session)

        if data_dir is None:
            data_dir = Path.cwd() / "data" / "skills"

        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)

    async def list_skills(
        self,
        source_id: int | None = None,
        name: str | None = None,
        tag: str | None = None,
    ) -> list[Skill]:
        """
        List skills with optional filters.

        Args:
            source_id: Filter by source ID
            name: Filter by skill name
            tag: Filter by tag

        Returns:
            List of skills
        """
        if name is not None:
            return await self.skill_repo.list_by_name(name)
        if tag is not None:
            return await self.skill_repo.search_by_tag(tag)
        return await self.skill_repo.list_all(source_id=source_id)

    async def get_skill(self, skill_id: int) -> Skill | None:
        """
        Get a skill by ID with source loaded.

        Args:
            skill_id: Skill ID

        Returns:
            Skill or None if not found
        """
        return await self.skill_repo.get_with_source(skill_id)

    async def list_installed_skills(
        self,
        project_id: int | None = None,
        harness_id: int | None = None,
    ) -> list[InstalledSkill]:
        """
        List installed skills with optional filters.

        Args:
            project_id: Filter by project ID (includes global if specified)
            harness_id: Filter by harness ID

        Returns:
            List of installed skills
        """
        if project_id is not None:
            return await self.installed_skill_repo.get_by_project(
                project_id=project_id, harness_id=harness_id, include_global=True
            )
        if harness_id is not None:
            return await self.installed_skill_repo.get_by_harness(
                harness_id=harness_id, include_global=True
            )
        return await self.installed_skill_repo.get_global_installs()

    async def _validate_project_scope(
        self, scope: InstallScope, project_id: int | None
    ) -> Path | None:
        """
        Validate project scope and return project path.

        Args:
            scope: Installation scope
            project_id: Project ID (required for project scope)

        Returns:
            Project path or None for global scope

        Raises:
            SkillInstallError: If validation fails
        """
        if scope != InstallScope.PROJECT:
            return None

        if project_id is None:
            raise SkillInstallError("project_id is required for project scope installation")

        project = await self.project_repo.get_with_manifestations(project_id)
        if project is None:
            raise SkillInstallError(f"Project {project_id} not found")

        # Find a local manifestation for the project
        local_manifestations = [
            m for m in project.manifestations if m.type == ManifestationType.LOCAL
        ]
        if not local_manifestations:
            raise SkillInstallError(f"Project {project_id} has no local manifestations")

        return Path(local_manifestations[0].path)

    async def install_skill(
        self,
        skill_id: int,
        harness_id: int,
        scope: InstallScope,
        project_id: int | None = None,
    ) -> InstalledSkill:
        """
        Install a skill to a harness.

        Args:
            skill_id: Skill ID to install
            harness_id: Harness ID to install to
            scope: Installation scope (global or project)
            project_id: Project ID (required for project scope)

        Returns:
            Created InstalledSkill record

        Raises:
            SkillInstallError: If installation fails
        """
        # Validate skill exists
        skill = await self.skill_repo.get_with_source(skill_id)
        if skill is None:
            raise SkillInstallError(f"Skill {skill_id} not found")

        # Validate harness exists
        harness = await self.harness_repo.get_by_id(harness_id)
        if harness is None:
            raise SkillInstallError(f"Harness {harness_id} not found")

        # Get harness adapter
        adapter = get_adapter(harness.name)
        if adapter is None:
            raise SkillInstallError(f"No adapter found for harness {harness.name}")

        # Validate project scope requirements
        project_path = await self._validate_project_scope(scope, project_id)

        # Check if already installed
        existing = await self.installed_skill_repo.get_by_identity(
            skill_id=skill_id,
            harness_id=harness_id,
            scope=scope,
            project_id=project_id,
        )
        if existing:
            raise SkillInstallError(
                f"Skill {skill_id} is already installed for this harness and scope"
            )

        # Get skill source path from data directory
        skill_source_path = (
            Path.cwd() / "data" / "skill_repos" / f"source_{skill.source_id}" / skill.name
        )
        if not skill_source_path.exists():
            raise SkillInstallError(
                f"Skill source not found at {skill_source_path}. "
                f"Ensure the source has been synced."
            )

        # Convert InstallScope to ConfigScope
        config_scope = ConfigScope.GLOBAL if scope == InstallScope.GLOBAL else ConfigScope.PROJECT

        try:
            # Install the skill using the harness adapter
            installed_path = adapter.install_skill(
                skill=skill_source_path,
                scope=config_scope,
                project_path=project_path,
            )

            # Create the installation record
            installed_skill = await self.installed_skill_repo.install(
                skill_id=skill_id,
                harness_id=harness_id,
                scope=scope,
                project_id=project_id,
                installed_path=str(installed_path),
                pinned_version=skill.version,
            )

            await self.session.commit()
            await self.session.refresh(installed_skill)

            logger.info(
                f"Installed skill {skill.name} (ID: {skill_id}) to "
                f"{harness.name} ({scope.value} scope)"
            )

            return installed_skill

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to install skill {skill_id}: {e}")
            raise SkillInstallError(f"Installation failed: {e}") from e

    async def uninstall_skill(self, installed_skill_id: int) -> bool:
        """
        Uninstall a skill.

        Args:
            installed_skill_id: InstalledSkill ID to remove

        Returns:
            True if uninstalled, False if not found

        Raises:
            SkillInstallError: If uninstallation fails
        """
        # Get the installed skill record
        installed_skill = await self.installed_skill_repo.get_by_id(installed_skill_id)
        if not installed_skill:
            return False

        # Get the harness to determine the adapter
        harness = await self.harness_repo.get_by_id(installed_skill.harness_id)
        if harness is None:
            raise SkillInstallError(
                f"Harness {installed_skill.harness_id} not found for installed skill"
            )

        # Get harness adapter
        adapter = get_adapter(harness.name)
        if adapter is None:
            raise SkillInstallError(f"No adapter found for harness {harness.name}")

        try:
            # Remove the skill files using the adapter
            installed_path = Path(installed_skill.installed_path)
            adapter.uninstall_skill(installed_path)

            # Remove the database record
            result = await self.installed_skill_repo.uninstall(installed_skill_id)
            if result:
                await self.session.commit()
                logger.info(
                    f"Uninstalled skill installation {installed_skill_id} from {installed_path}"
                )
            return result

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to uninstall skill {installed_skill_id}: {e}")
            raise SkillInstallError(f"Uninstallation failed: {e}") from e
