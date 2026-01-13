"""Cache manager facade for CLI operations."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from jefe.cli.cache.models import (
    CachedHarnessConfig,
    CachedInstalledSkill,
    CachedProject,
    CachedSkill,
    ConfigScope,
    InstallScope,
)
from jefe.cli.cache.repositories import (
    ConflictRepository,
    HarnessConfigRepository,
    InstalledSkillRepository,
    ProjectRepository,
    SkillRepository,
)


class CacheManager:
    """Facade for all cache operations.

    Provides a clean interface for caching server responses,
    tracking local modifications, and managing cache freshness.
    """

    def __init__(self, ttl_seconds: int = 300):
        """Initialize the cache manager.

        Args:
            ttl_seconds: Time-to-live in seconds for cache freshness (default: 300)
        """
        self.projects = ProjectRepository(ttl_seconds)
        self.skills = SkillRepository(ttl_seconds)
        self.installed_skills = InstalledSkillRepository(ttl_seconds)
        self.harness_configs = HarnessConfigRepository(ttl_seconds)
        self.conflicts = ConflictRepository()
        self.ttl_seconds = ttl_seconds

    def close(self) -> None:
        """Close all repository sessions."""
        self.projects.close()
        self.skills.close()
        self.installed_skills.close()
        self.harness_configs.close()
        self.conflicts.close()

    # Project operations
    def cache_project(
        self, server_id: int, name: str, description: str | None = None
    ) -> CachedProject:
        """Cache a project from server response.

        Args:
            server_id: The server ID of the project
            name: Project name
            description: Optional project description

        Returns:
            The cached project
        """
        # Check if already exists
        existing = self.projects.get_by_server_id(server_id)
        if existing:
            existing.name = name
            existing.description = description
            existing.last_synced = datetime.now(UTC)
            existing.dirty = False
            self.projects.set(existing)
            return existing

        # Create new
        project = CachedProject(
            server_id=server_id,
            name=name,
            description=description,
            last_synced=datetime.now(UTC),
            dirty=False,
        )
        self.projects.set(project)
        return project

    def get_project(self, name: str) -> CachedProject | None:
        """Get a cached project by name.

        Args:
            name: The project name

        Returns:
            The cached project or None if not found
        """
        return self.projects.get_by_name(name)

    def get_all_projects(self) -> list[CachedProject]:
        """Get all cached projects.

        Returns:
            List of all cached projects
        """
        return self.projects.get_all()

    def mark_project_dirty(self, project: CachedProject) -> None:
        """Mark a project as locally modified.

        Args:
            project: The project to mark dirty
        """
        self.projects.mark_dirty(project)

    def is_project_fresh(self, project: CachedProject) -> bool:
        """Check if a project cache is still fresh.

        Args:
            project: The project to check

        Returns:
            True if the project is within TTL, False otherwise
        """
        return self.projects.is_fresh(project)

    # Skill operations
    def cache_skill(
        self,
        server_id: int,
        source_id: int | None,
        name: str,
        display_name: str | None = None,
        description: str | None = None,
        version: str | None = None,
        author: str | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CachedSkill:
        """Cache a skill from server response.

        Args:
            server_id: The server ID of the skill
            source_id: The source ID the skill belongs to
            name: Skill name
            display_name: Optional display name
            description: Optional description
            version: Optional version
            author: Optional author
            tags: Optional list of tags
            metadata: Optional metadata dict

        Returns:
            The cached skill
        """
        # Check if already exists
        existing = self.skills.get_by_server_id(server_id)
        if existing:
            existing.source_id = source_id
            existing.name = name
            existing.display_name = display_name
            existing.description = description
            existing.version = version
            existing.author = author
            if tags:
                existing.set_tags_list(tags)
            if metadata:
                existing.set_metadata_dict(metadata)
            existing.last_synced = datetime.now(UTC)
            existing.dirty = False
            self.skills.set(existing)
            return existing

        # Create new
        skill = CachedSkill(
            server_id=server_id,
            source_id=source_id,
            name=name,
            display_name=display_name,
            description=description,
            version=version,
            author=author,
            last_synced=datetime.now(UTC),
            dirty=False,
        )
        if tags:
            skill.set_tags_list(tags)
        if metadata:
            skill.set_metadata_dict(metadata)
        self.skills.set(skill)
        return skill

    def get_skill(self, name: str) -> CachedSkill | None:
        """Get a cached skill by name.

        Args:
            name: The skill name

        Returns:
            The cached skill or None if not found
        """
        return self.skills.get_by_name(name)

    def get_all_skills(self) -> list[CachedSkill]:
        """Get all cached skills.

        Returns:
            List of all cached skills
        """
        return self.skills.get_all()

    def mark_skill_dirty(self, skill: CachedSkill) -> None:
        """Mark a skill as locally modified.

        Args:
            skill: The skill to mark dirty
        """
        self.skills.mark_dirty(skill)

    def is_skill_fresh(self, skill: CachedSkill) -> bool:
        """Check if a skill cache is still fresh.

        Args:
            skill: The skill to check

        Returns:
            True if the skill is within TTL, False otherwise
        """
        return self.skills.is_fresh(skill)

    # Installed skill operations
    def cache_installed_skill(
        self,
        server_id: int,
        skill_id: int | None,
        harness_id: int | None,
        scope: InstallScope,
        installed_path: str,
        project_id: int | None = None,
        pinned_version: str | None = None,
    ) -> CachedInstalledSkill:
        """Cache an installed skill from server response.

        Args:
            server_id: The server ID of the installation
            skill_id: The skill ID
            harness_id: The harness ID
            scope: Installation scope
            installed_path: Path where skill is installed
            project_id: Optional project ID for project scope
            pinned_version: Optional pinned version

        Returns:
            The cached installed skill
        """
        # Check if already exists
        existing = self.installed_skills.get_by_server_id(server_id)
        if existing:
            existing.skill_id = skill_id
            existing.harness_id = harness_id
            existing.scope = scope
            existing.installed_path = installed_path
            existing.project_id = project_id
            existing.pinned_version = pinned_version
            existing.last_synced = datetime.now(UTC)
            existing.dirty = False
            self.installed_skills.set(existing)
            return existing

        # Create new
        installed = CachedInstalledSkill(
            server_id=server_id,
            skill_id=skill_id,
            harness_id=harness_id,
            scope=scope,
            installed_path=installed_path,
            project_id=project_id,
            pinned_version=pinned_version,
            last_synced=datetime.now(UTC),
            dirty=False,
        )
        self.installed_skills.set(installed)
        return installed

    def get_installed_skills_by_scope(
        self, scope: InstallScope, project_id: int | None = None
    ) -> list[CachedInstalledSkill]:
        """Get installed skills by scope.

        Args:
            scope: The installation scope
            project_id: Optional project ID for project scope

        Returns:
            List of installed skills matching the scope
        """
        return self.installed_skills.get_by_scope(scope, project_id)

    def mark_installed_skill_dirty(self, installed: CachedInstalledSkill) -> None:
        """Mark an installed skill as locally modified.

        Args:
            installed: The installed skill to mark dirty
        """
        self.installed_skills.mark_dirty(installed)

    # Harness config operations
    def cache_harness_config(
        self,
        server_id: int,
        harness_id: int | None,
        scope: ConfigScope,
        kind: str,
        path: str,
        content: str | None = None,
        content_hash: str | None = None,
        project_id: int | None = None,
    ) -> CachedHarnessConfig:
        """Cache a harness config from server response.

        Args:
            server_id: The server ID of the config
            harness_id: The harness ID
            scope: Configuration scope
            kind: Config kind
            path: Config path
            content: Optional content
            content_hash: Optional content hash
            project_id: Optional project ID for project scope

        Returns:
            The cached harness config
        """
        # Check if already exists
        existing = self.harness_configs.get_by_server_id(server_id)
        if existing:
            existing.harness_id = harness_id
            existing.scope = scope
            existing.kind = kind
            existing.path = path
            existing.content = content
            existing.content_hash = content_hash
            existing.project_id = project_id
            existing.last_synced = datetime.now(UTC)
            existing.dirty = False
            self.harness_configs.set(existing)
            return existing

        # Create new
        config = CachedHarnessConfig(
            server_id=server_id,
            harness_id=harness_id,
            scope=scope,
            kind=kind,
            path=path,
            content=content,
            content_hash=content_hash,
            project_id=project_id,
            last_synced=datetime.now(UTC),
            dirty=False,
        )
        self.harness_configs.set(config)
        return config

    def get_harness_configs_by_scope(
        self, scope: ConfigScope, project_id: int | None = None
    ) -> list[CachedHarnessConfig]:
        """Get harness configs by scope.

        Args:
            scope: The configuration scope
            project_id: Optional project ID for project scope

        Returns:
            List of configs matching the scope
        """
        return self.harness_configs.get_by_scope(scope, project_id)

    def mark_harness_config_dirty(self, config: CachedHarnessConfig) -> None:
        """Mark a harness config as locally modified.

        Args:
            config: The config to mark dirty
        """
        self.harness_configs.mark_dirty(config)

    # Sync operations
    def get_all_dirty_items(
        self,
    ) -> tuple[
        list[CachedProject],
        list[CachedSkill],
        list[CachedInstalledSkill],
        list[CachedHarnessConfig],
    ]:
        """Get all dirty items across all entity types.

        Returns:
            Tuple of (dirty_projects, dirty_skills, dirty_installed_skills, dirty_configs)
        """
        return (
            self.projects.get_dirty(),
            self.skills.get_dirty(),
            self.installed_skills.get_dirty(),
            self.harness_configs.get_dirty(),
        )

    def clear_all_dirty(self) -> None:
        """Clear all dirty flags and update last_synced timestamps."""
        self.projects.clear_all_dirty()
        self.skills.clear_all_dirty()
        self.installed_skills.clear_all_dirty()
        self.harness_configs.clear_all_dirty()
