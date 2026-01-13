"""Service for managing skill bundles."""

import logging
from pathlib import Path
from typing import TypedDict

from sqlalchemy.ext.asyncio import AsyncSession

from jefe.data.models.bundle import Bundle
from jefe.data.models.installed_skill import InstallScope
from jefe.data.repositories.bundle import BundleRepository
from jefe.data.repositories.skill import SkillRepository
from jefe.data.repositories.skill_source import SkillSourceRepository
from jefe.server.services.skill import SkillInstallError, SkillService

logger = logging.getLogger(__name__)


class BundleApplyResult(TypedDict):
    """Result of applying a bundle."""

    success: int
    failed: int
    errors: list[str]


class BundleError(Exception):
    """Raised when bundle operations fail."""

    pass


class BundleService:
    """Service for managing skill bundles."""

    def __init__(self, session: AsyncSession, data_dir: Path | None = None) -> None:
        """
        Initialize the bundle service.

        Args:
            session: Database session
            data_dir: Directory for storing skill files
        """
        self.session = session
        self.bundle_repo = BundleRepository(session)
        self.skill_repo = SkillRepository(session)
        self.source_repo = SkillSourceRepository(session)
        self.skill_service = SkillService(session, data_dir)

    async def list_bundles(self) -> list[Bundle]:
        """
        List all bundles.

        Returns:
            List of bundles
        """
        return await self.bundle_repo.list_all()

    async def get_bundle(self, bundle_id: int) -> Bundle | None:
        """
        Get a bundle by ID.

        Args:
            bundle_id: Bundle ID

        Returns:
            Bundle or None if not found
        """
        return await self.bundle_repo.get_by_id(bundle_id)

    async def get_bundle_by_name(self, name: str) -> Bundle | None:
        """
        Get a bundle by name.

        Args:
            name: Bundle name

        Returns:
            Bundle or None if not found
        """
        return await self.bundle_repo.get_by_name(name)

    async def create_bundle(
        self,
        name: str,
        skill_refs: list[dict[str, str]],
        display_name: str | None = None,
        description: str | None = None,
    ) -> Bundle:
        """
        Create a new bundle.

        Args:
            name: Bundle name (unique identifier)
            skill_refs: List of skill references with 'source' and 'name' keys
            display_name: Optional display name
            description: Optional description

        Returns:
            Created Bundle

        Raises:
            BundleError: If creation fails or bundle already exists
        """
        # Check if bundle already exists
        existing = await self.bundle_repo.get_by_name(name)
        if existing:
            raise BundleError(f"Bundle with name '{name}' already exists")

        try:
            import json

            skill_refs_json = json.dumps(skill_refs)

            bundle = await self.bundle_repo.create(
                name=name,
                display_name=display_name,
                description=description,
                skill_refs=skill_refs_json,
            )

            await self.session.commit()
            await self.session.refresh(bundle)

            logger.info(f"Created bundle '{name}' with {len(skill_refs)} skill references")

            return bundle

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to create bundle '{name}': {e}")
            raise BundleError(f"Failed to create bundle: {e}") from e

    async def apply_bundle(  # noqa: C901
        self,
        bundle_id: int,
        harness_id: int,
        scope: InstallScope,
        project_id: int | None = None,
    ) -> BundleApplyResult:
        """
        Apply a bundle by installing all its skills.

        Args:
            bundle_id: Bundle ID to apply
            harness_id: Harness ID to install skills to
            scope: Installation scope (global or project)
            project_id: Project ID (required for project scope)

        Returns:
            BundleApplyResult with 'success' count, 'failed' count, and 'errors' list

        Raises:
            BundleError: If bundle not found or application fails completely
        """
        bundle = await self.bundle_repo.get_by_id(bundle_id)
        if bundle is None:
            raise BundleError(f"Bundle {bundle_id} not found")

        skill_refs = bundle.get_skill_refs_list()
        if not skill_refs:
            logger.warning(f"Bundle {bundle_id} has no skill references")
            return BundleApplyResult(success=0, failed=0, errors=[])

        success_count = 0
        failed_count = 0
        errors = []

        for ref in skill_refs:
            source_name = ref.get("source")
            skill_name = ref.get("name")

            if not source_name or not skill_name:
                error_msg = f"Invalid skill reference: {ref}"
                logger.error(error_msg)
                errors.append(error_msg)
                failed_count += 1
                continue

            try:
                # Find the skill source by name
                source = await self.source_repo.get_by_name(source_name)
                if source is None:
                    error_msg = f"Source '{source_name}' not found for skill '{skill_name}'"
                    logger.error(error_msg)
                    errors.append(error_msg)
                    failed_count += 1
                    continue

                # Find the skill by name and source
                skills = await self.skill_repo.list_by_name(skill_name)
                matching_skill = None
                for skill in skills:
                    if skill.source_id == source.id:
                        matching_skill = skill
                        break

                if matching_skill is None:
                    error_msg = (
                        f"Skill '{skill_name}' not found in source '{source_name}'"
                    )
                    logger.error(error_msg)
                    errors.append(error_msg)
                    failed_count += 1
                    continue

                # Install the skill
                await self.skill_service.install_skill(
                    skill_id=matching_skill.id,
                    harness_id=harness_id,
                    scope=scope,
                    project_id=project_id,
                )

                logger.info(
                    f"Installed skill '{skill_name}' from '{source_name}' (bundle {bundle_id})"
                )
                success_count += 1

            except SkillInstallError as e:
                error_msg = f"Failed to install '{skill_name}' from '{source_name}': {e}"
                logger.error(error_msg)
                errors.append(error_msg)
                failed_count += 1
            except Exception as e:
                error_msg = f"Unexpected error installing '{skill_name}' from '{source_name}': {e}"
                logger.error(error_msg)
                errors.append(error_msg)
                failed_count += 1

        logger.info(
            f"Bundle {bundle_id} application complete: "
            f"{success_count} succeeded, {failed_count} failed"
        )

        return BundleApplyResult(
            success=success_count,
            failed=failed_count,
            errors=errors,
        )
