"""Service for syncing skill sources from Git repositories."""

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError
from sqlalchemy.ext.asyncio import AsyncSession

from jefe.data.models.skill import Skill
from jefe.data.models.skill_source import SkillSource, SourceType, SyncStatus
from jefe.data.repositories.skill import SkillRepository
from jefe.data.repositories.skill_source import SkillSourceRepository
from jefe.server.utils.skill_parser import (
    SkillParseError,
    find_skill_files,
    parse_skill_file,
)

logger = logging.getLogger(__name__)


class SkillSourceSyncError(Exception):
    """Raised when skill source sync fails."""

    pass


class SkillSourceService:
    """Service for syncing skill sources and managing skills."""

    def __init__(
        self,
        session: AsyncSession,
        data_dir: Path | None = None,
    ) -> None:
        """
        Initialize the skill source service.

        Args:
            session: Database session
            data_dir: Directory for storing cloned repositories (default: ./data/skill_repos)
        """
        self.session = session
        self.source_repo = SkillSourceRepository(session)
        self.skill_repo = SkillRepository(session)

        if data_dir is None:
            data_dir = Path.cwd() / "data" / "skill_repos"

        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _get_repo_path(self, source_id: int) -> Path:
        """Get the local path for a cloned repository."""
        return self.data_dir / f"source_{source_id}"

    async def sync_source(self, source_id: int) -> int:
        """
        Sync a skill source by cloning/pulling the repo and indexing SKILL.md files.

        Args:
            source_id: ID of the skill source to sync

        Returns:
            Number of skills created or updated

        Raises:
            SkillSourceSyncError: If sync fails
        """
        # Fetch the source
        source = await self.source_repo.get_by_id(source_id)
        if not source:
            raise SkillSourceSyncError(f"Skill source {source_id} not found")

        # Only sync git sources
        if source.source_type != SourceType.GIT:
            raise SkillSourceSyncError(
                f"Cannot sync source type {source.source_type.value}"
            )

        # Update status to syncing
        await self.source_repo.update(source_id, sync_status=SyncStatus.SYNCING)
        await self.session.commit()

        try:
            # Clone or pull the repository
            repo_path = self._get_repo_path(source_id)
            await self._sync_git_repo(source.url, repo_path)

            # Find and parse SKILL.md files
            skill_files = find_skill_files(repo_path)
            logger.info(f"Found {len(skill_files)} SKILL.md files in source {source_id}")

            # Process each skill file
            skills_updated = 0
            for skill_file in skill_files:
                try:
                    metadata = parse_skill_file(skill_file)
                    await self._create_or_update_skill(source_id, metadata)
                    skills_updated += 1
                except (SkillParseError, ValueError) as e:
                    logger.warning(f"Failed to parse {skill_file}: {e}")
                    continue

            # Update source status to synced
            now = datetime.now(UTC).isoformat()
            await self.source_repo.update(
                source_id,
                sync_status=SyncStatus.SYNCED,
                last_synced_at=now,
            )
            await self.session.commit()

            logger.info(
                f"Successfully synced source {source_id}: {skills_updated} skills updated"
            )
            return skills_updated

        except Exception as e:
            # Update status to error
            await self.source_repo.update(source_id, sync_status=SyncStatus.ERROR)
            await self.session.commit()
            logger.error(f"Failed to sync source {source_id}: {e}")
            raise SkillSourceSyncError(f"Sync failed: {e}") from e

    async def _sync_git_repo(self, url: str, repo_path: Path) -> None:
        """
        Clone or pull a git repository.

        Args:
            url: Git repository URL
            repo_path: Local path for the repository

        Raises:
            SkillSourceSyncError: If git operations fail
        """
        try:
            if repo_path.exists() and (repo_path / ".git").exists():
                # Repository exists, pull updates
                try:
                    repo = Repo(repo_path)
                    origin = repo.remotes.origin
                    origin.pull()
                    logger.info(f"Pulled updates for {url}")
                except InvalidGitRepositoryError:
                    # Directory exists but not a valid repo, remove and clone
                    logger.warning(f"Invalid git repository at {repo_path}, re-cloning")
                    self._remove_repo(repo_path)
                    self._clone_repo(url, repo_path)
            else:
                # Repository doesn't exist, clone it
                self._clone_repo(url, repo_path)

        except GitCommandError as e:
            raise SkillSourceSyncError(f"Git operation failed: {e}") from e

    def _clone_repo(self, url: str, repo_path: Path) -> None:
        """Clone a git repository with shallow clone."""
        logger.info(f"Cloning {url} to {repo_path}")
        Repo.clone_from(url, str(repo_path), depth=1)

    def _remove_repo(self, repo_path: Path) -> None:
        """Remove a repository directory."""
        import shutil

        if repo_path.exists():
            shutil.rmtree(repo_path)

    async def _create_or_update_skill(
        self,
        source_id: int,
        metadata: dict[str, Any],
    ) -> Skill:
        """
        Create or update a skill from parsed metadata.

        Args:
            source_id: ID of the skill source
            metadata: Parsed skill metadata

        Returns:
            Created or updated Skill instance
        """
        # Check if skill already exists for this source
        existing_skills = await self.skill_repo.list_by_source(source_id)
        existing_skill = next(
            (s for s in existing_skills if s.name == metadata["name"]),
            None,
        )

        # Prepare skill data
        skill_data = {
            "source_id": source_id,
            "name": metadata["name"],
            "display_name": metadata.get("display_name"),
            "description": metadata.get("description"),
            "version": metadata.get("version"),
            "author": metadata.get("author"),
        }

        # Handle tags
        tags = metadata.get("tags", [])
        if tags:
            skill_data["tags"] = tags

        # Handle additional metadata
        additional_metadata = metadata.get("metadata")
        if additional_metadata:
            skill_data["metadata_json"] = additional_metadata

        if existing_skill:
            # Update existing skill
            await self.skill_repo.update(existing_skill.id, **skill_data)
            await self.session.flush()
            updated_skill = await self.skill_repo.get_by_id(existing_skill.id)
            if not updated_skill:
                raise SkillSourceSyncError(f"Failed to fetch updated skill {existing_skill.id}")
            logger.debug(f"Updated skill: {metadata['name']}")
            return updated_skill
        else:
            # Create new skill
            skill = await self.skill_repo.create(**skill_data)
            await self.session.flush()
            logger.debug(f"Created skill: {metadata['name']}")
            return skill

    async def list_sources(
        self,
        source_type: SourceType | None = None,
        sync_status: SyncStatus | None = None,
    ) -> list[SkillSource]:
        """
        List all skill sources with optional filters.

        Args:
            source_type: Filter by source type
            sync_status: Filter by sync status

        Returns:
            List of skill sources
        """
        return await self.source_repo.list_all(
            source_type=source_type,
            sync_status=sync_status,
        )

    async def get_source(self, source_id: int) -> SkillSource | None:
        """
        Get a skill source by ID.

        Args:
            source_id: ID of the skill source

        Returns:
            SkillSource or None if not found
        """
        return await self.source_repo.get_by_id(source_id)

    async def list_skills(
        self,
        source_id: int | None = None,
        author: str | None = None,
    ) -> list[Skill]:
        """
        List all skills with optional filters.

        Args:
            source_id: Filter by source ID
            author: Filter by author

        Returns:
            List of skills
        """
        return await self.skill_repo.list_all(
            source_id=source_id,
            author=author,
        )
