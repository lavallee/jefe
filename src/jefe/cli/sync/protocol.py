"""Sync protocol for CLI-server synchronization.

Implements timestamp-based delta sync with last-write-wins conflict resolution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

import httpx

from jefe.cli.cache.manager import CacheManager
from jefe.cli.cache.models import (
    CachedHarnessConfig,
    CachedInstalledSkill,
    CachedProject,
    CachedSkill,
    ConfigScope,
    InstallScope,
)
from jefe.cli.client import create_client, is_online

if TYPE_CHECKING:
    pass


class ConflictResolution(str, Enum):
    """How a conflict was resolved."""

    LOCAL_WINS = "local_wins"
    SERVER_WINS = "server_wins"


class EntityType(str, Enum):
    """Types of entities that can be synced."""

    PROJECT = "project"
    SKILL = "skill"
    INSTALLED_SKILL = "installed_skill"
    HARNESS_CONFIG = "harness_config"


@dataclass
class SyncConflict:
    """A detected sync conflict."""

    entity_type: EntityType
    local_id: int
    server_id: int
    local_updated_at: datetime
    server_updated_at: datetime
    resolution: ConflictResolution

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API requests."""
        return {
            "entity_type": self.entity_type.value,
            "local_id": self.local_id,
            "server_id": self.server_id,
            "local_updated_at": self.local_updated_at.isoformat(),
            "server_updated_at": self.server_updated_at.isoformat(),
            "resolution": self.resolution.value,
        }


@dataclass
class SyncResult:
    """Result of a sync operation."""

    success: bool
    pushed: int = 0
    pulled: int = 0
    conflicts: list[SyncConflict] = field(default_factory=list)
    error_message: str | None = None

    @property
    def had_conflicts(self) -> bool:
        """Check if there were any conflicts."""
        return len(self.conflicts) > 0


class SyncClient:
    """HTTP client for sync operations."""

    def __init__(self) -> None:
        """Initialize the sync client."""
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> SyncClient:
        """Enter async context manager."""
        self._client = create_client()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Exit async context manager."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def push(self, data: dict[str, Any]) -> dict[str, Any]:
        """Push dirty items to the server.

        Args:
            data: The push request data

        Returns:
            The push response from the server

        Raises:
            httpx.HTTPError: If the request fails
        """
        if not self._client:
            raise RuntimeError("SyncClient not initialized - use as context manager")

        response = await self._client.post("/api/sync/push", json=data)
        response.raise_for_status()
        return response.json()  # type: ignore[no-any-return]

    async def pull(
        self,
        last_synced: datetime | None = None,
        entity_types: list[str] | None = None,
    ) -> dict[str, Any]:
        """Pull changes from the server.

        Args:
            last_synced: Timestamp to get changes since (None = all)
            entity_types: Optional list of entity types to pull (None = all)

        Returns:
            The pull response from the server

        Raises:
            httpx.HTTPError: If the request fails
        """
        if not self._client:
            raise RuntimeError("SyncClient not initialized - use as context manager")

        data: dict[str, Any] = {}
        if last_synced is not None:
            data["last_synced"] = last_synced.isoformat()
        if entity_types:
            data["entity_types"] = entity_types

        response = await self._client.post("/api/sync/pull", json=data)
        response.raise_for_status()
        return response.json()  # type: ignore[no-any-return]


class SyncProtocol:
    """Synchronization protocol between CLI cache and server.

    Implements timestamp-based delta sync with last-write-wins
    conflict resolution.
    """

    def __init__(self, cache_manager: CacheManager | None = None) -> None:
        """Initialize the sync protocol.

        Args:
            cache_manager: Cache manager to use. If None, creates a new one.
        """
        self._cache = cache_manager or CacheManager()
        self._own_cache = cache_manager is None
        self._last_synced: datetime | None = None
        self._conflicts: list[SyncConflict] = []

    def close(self) -> None:
        """Close resources."""
        if self._own_cache:
            self._cache.close()

    @property
    def conflicts(self) -> list[SyncConflict]:
        """Get tracked conflicts from the last sync."""
        return self._conflicts

    def clear_conflicts(self) -> None:
        """Clear tracked conflicts."""
        self._conflicts = []

    def _persist_conflict(
        self, conflict: SyncConflict, local_data: dict[str, Any], server_data: dict[str, Any]
    ) -> None:
        """Persist a conflict to the database.

        Args:
            conflict: The sync conflict to persist
            local_data: Local entity data as dict
            server_data: Server entity data as dict
        """
        import json

        from jefe.cli.cache.models import (
            CachedConflict,
            ConflictEntityType,
            ConflictResolutionType,
        )

        # Map protocol enums to cache model enums
        entity_type_map = {
            EntityType.PROJECT: ConflictEntityType.PROJECT,
            EntityType.SKILL: ConflictEntityType.SKILL,
            EntityType.INSTALLED_SKILL: ConflictEntityType.INSTALLED_SKILL,
            EntityType.HARNESS_CONFIG: ConflictEntityType.HARNESS_CONFIG,
        }

        resolution_map = {
            ConflictResolution.LOCAL_WINS: ConflictResolutionType.LOCAL_WINS,
            ConflictResolution.SERVER_WINS: ConflictResolutionType.SERVER_WINS,
        }

        cached_conflict = CachedConflict(
            entity_type=entity_type_map[conflict.entity_type],
            local_id=conflict.local_id,
            server_id=conflict.server_id,
            local_updated_at=conflict.local_updated_at,
            server_updated_at=conflict.server_updated_at,
            resolution=resolution_map.get(
                conflict.resolution, ConflictResolutionType.UNRESOLVED
            ),
            local_data=json.dumps(local_data),
            server_data=json.dumps(server_data),
        )

        self._cache.conflicts.add(cached_conflict)

    async def sync(self) -> SyncResult:
        """Perform a full sync (push then pull).

        Returns:
            SyncResult with success status, counts, and any conflicts
        """
        # Check if we're online
        if not await is_online():
            return SyncResult(success=False, error_message="Server is not reachable")

        self.clear_conflicts()

        # First push local changes
        push_result = await self.push()
        if not push_result.success:
            return push_result

        # Then pull server changes
        pull_result = await self.pull()

        # Combine results
        return SyncResult(
            success=pull_result.success,
            pushed=push_result.pushed,
            pulled=pull_result.pulled,
            conflicts=push_result.conflicts + pull_result.conflicts,
            error_message=pull_result.error_message,
        )

    async def push(self, entity_types: list[str] | None = None) -> SyncResult:
        """Push local dirty items to the server.

        Args:
            entity_types: Optional list of entity types to push. If None, pushes all.
                Valid types: projects, skills, installed_skills, harness_configs

        Returns:
            SyncResult with success status and counts
        """
        if not await is_online():
            return SyncResult(success=False, error_message="Server is not reachable")

        # Collect dirty items
        dirty_projects, dirty_skills, dirty_installed, dirty_configs = (
            self._cache.get_all_dirty_items()
        )

        # Filter by entity types if specified
        if entity_types:
            if "projects" not in entity_types:
                dirty_projects = []
            if "skills" not in entity_types:
                dirty_skills = []
            if "installed_skills" not in entity_types:
                dirty_installed = []
            if "harness_configs" not in entity_types:
                dirty_configs = []

        # Build push request
        push_data = self._build_push_request(
            dirty_projects, dirty_skills, dirty_installed, dirty_configs
        )

        # Skip if nothing to push
        total_items = (
            len(push_data.get("projects", []))
            + len(push_data.get("skills", []))
            + len(push_data.get("installed_skills", []))
            + len(push_data.get("harness_configs", []))
        )
        if total_items == 0:
            return SyncResult(success=True, pushed=0)

        try:
            async with SyncClient() as client:
                response = await client.push(push_data)

            # Process response
            conflicts = self._process_push_response(response)
            self._conflicts.extend(conflicts)

            # Update server IDs from mappings
            mappings = response.get("server_id_mappings", {})
            self._apply_server_id_mappings(
                mappings, dirty_projects, dirty_skills, dirty_installed, dirty_configs
            )

            # Clear dirty flags on success
            if response.get("success", False):
                self._cache.clear_all_dirty()

            pushed = (
                response.get("projects_synced", 0)
                + response.get("skills_synced", 0)
                + response.get("installed_skills_synced", 0)
                + response.get("harness_configs_synced", 0)
            )

            return SyncResult(success=True, pushed=pushed, conflicts=conflicts)

        except httpx.HTTPError as e:
            return SyncResult(success=False, error_message=str(e))

    async def pull(self, entity_types: list[str] | None = None) -> SyncResult:
        """Pull changes from the server.

        Args:
            entity_types: Optional list of entity types to pull. If None, pulls all.
                Valid types: projects, skills, installed_skills, harness_configs

        Returns:
            SyncResult with success status and counts
        """
        if not await is_online():
            return SyncResult(success=False, error_message="Server is not reachable")

        try:
            async with SyncClient() as client:
                response = await client.pull(self._last_synced, entity_types)

            # Process pulled items (filtered by entity_types if specified)
            conflicts = self._process_pull_response(response, entity_types)
            self._conflicts.extend(conflicts)

            # Update last synced timestamp
            if response.get("server_time"):
                self._last_synced = datetime.fromisoformat(response["server_time"])

            pulled = (
                len(response.get("projects", []))
                + len(response.get("skills", []))
                + len(response.get("installed_skills", []))
                + len(response.get("harness_configs", []))
            )

            return SyncResult(success=True, pulled=pulled, conflicts=conflicts)

        except httpx.HTTPError as e:
            return SyncResult(success=False, error_message=str(e))

    def _build_push_request(
        self,
        projects: list[CachedProject],
        skills: list[CachedSkill],
        installed_skills: list[CachedInstalledSkill],
        harness_configs: list[CachedHarnessConfig],
    ) -> dict[str, Any]:
        """Build the push request data.

        Args:
            projects: Dirty projects to push
            skills: Dirty skills to push
            installed_skills: Dirty installed skills to push
            harness_configs: Dirty harness configs to push

        Returns:
            Dict ready to send as JSON
        """
        return {
            "projects": [self._project_to_dict(p) for p in projects],
            "skills": [self._skill_to_dict(s) for s in skills],
            "installed_skills": [self._installed_skill_to_dict(i) for i in installed_skills],
            "harness_configs": [self._harness_config_to_dict(c) for c in harness_configs],
        }

    def _project_to_dict(self, project: CachedProject) -> dict[str, Any]:
        """Convert a cached project to dict."""
        return {
            "local_id": project.id,
            "server_id": project.server_id,
            "name": project.name,
            "description": project.description,
            "updated_at": project.updated_at.isoformat() if project.updated_at else None,
        }

    def _skill_to_dict(self, skill: CachedSkill) -> dict[str, Any]:
        """Convert a cached skill to dict."""
        return {
            "local_id": skill.id,
            "server_id": skill.server_id,
            "source_id": skill.source_id,
            "name": skill.name,
            "display_name": skill.display_name,
            "description": skill.description,
            "version": skill.version,
            "author": skill.author,
            "tags": skill.get_tags_list(),
            "metadata": skill.get_metadata_dict(),
            "updated_at": skill.updated_at.isoformat() if skill.updated_at else None,
        }

    def _installed_skill_to_dict(self, installed: CachedInstalledSkill) -> dict[str, Any]:
        """Convert a cached installed skill to dict."""
        return {
            "local_id": installed.id,
            "server_id": installed.server_id,
            "skill_id": installed.skill_id,
            "harness_id": installed.harness_id,
            "scope": installed.scope.value if isinstance(installed.scope, Enum) else installed.scope,
            "project_id": installed.project_id,
            "installed_path": installed.installed_path,
            "pinned_version": installed.pinned_version,
            "updated_at": installed.updated_at.isoformat() if installed.updated_at else None,
        }

    def _harness_config_to_dict(self, config: CachedHarnessConfig) -> dict[str, Any]:
        """Convert a cached harness config to dict."""
        return {
            "local_id": config.id,
            "server_id": config.server_id,
            "harness_id": config.harness_id,
            "scope": config.scope.value if isinstance(config.scope, Enum) else config.scope,
            "kind": config.kind,
            "path": config.path,
            "content": config.content,
            "content_hash": config.content_hash,
            "project_id": config.project_id,
            "updated_at": config.updated_at.isoformat() if config.updated_at else None,
        }

    def _process_push_response(self, response: dict[str, Any]) -> list[SyncConflict]:
        """Process the push response and extract conflicts.

        Args:
            response: The push response from the server

        Returns:
            List of sync conflicts
        """
        conflicts = []
        for conflict_data in response.get("conflicts", []):
            conflict = SyncConflict(
                entity_type=EntityType(conflict_data["entity_type"]),
                local_id=conflict_data["local_id"],
                server_id=conflict_data["server_id"],
                local_updated_at=datetime.fromisoformat(conflict_data["local_updated_at"]),
                server_updated_at=datetime.fromisoformat(conflict_data["server_updated_at"]),
                resolution=ConflictResolution(conflict_data["resolution"]),
            )
            conflicts.append(conflict)
        return conflicts

    def _apply_server_id_mappings(
        self,
        mappings: dict[str, Any],
        projects: list[CachedProject],
        skills: list[CachedSkill],
        installed_skills: list[CachedInstalledSkill],
        harness_configs: list[CachedHarnessConfig],
    ) -> None:
        """Apply server ID mappings to local cache items.

        Args:
            mappings: Dict of entity type to local_id -> server_id mappings
            projects: Projects that were pushed
            skills: Skills that were pushed
            installed_skills: Installed skills that were pushed
            harness_configs: Harness configs that were pushed
        """
        # Apply project mappings
        project_mappings = mappings.get("project", {})
        for project in projects:
            local_id = str(project.id)
            if local_id in project_mappings:
                project.server_id = project_mappings[local_id]
                self._cache.projects.set(project)

        # Apply skill mappings
        skill_mappings = mappings.get("skill", {})
        for skill in skills:
            local_id = str(skill.id)
            if local_id in skill_mappings:
                skill.server_id = skill_mappings[local_id]
                self._cache.skills.set(skill)

        # Apply installed skill mappings
        installed_mappings = mappings.get("installed_skill", {})
        for installed in installed_skills:
            local_id = str(installed.id)
            if local_id in installed_mappings:
                installed.server_id = installed_mappings[local_id]
                self._cache.installed_skills.set(installed)

        # Apply harness config mappings
        config_mappings = mappings.get("harness_config", {})
        for config in harness_configs:
            local_id = str(config.id)
            if local_id in config_mappings:
                config.server_id = config_mappings[local_id]
                self._cache.harness_configs.set(config)

    def _process_pull_response(  # noqa: C901
        self, response: dict[str, Any], entity_types: list[str] | None = None
    ) -> list[SyncConflict]:
        """Process the pull response and update local cache.

        Implements last-write-wins conflict resolution.

        Args:
            response: The pull response from the server
            entity_types: Optional list of entity types to process. If None, processes all.

        Returns:
            List of sync conflicts
        """
        conflicts: list[SyncConflict] = []

        # Process projects
        if entity_types is None or "projects" in entity_types:
            for project_data in response.get("projects", []):
                conflict = self._update_project_from_server(project_data)
                if conflict:
                    conflicts.append(conflict)

        # Process skills
        if entity_types is None or "skills" in entity_types:
            for skill_data in response.get("skills", []):
                conflict = self._update_skill_from_server(skill_data)
                if conflict:
                    conflicts.append(conflict)

        # Process installed skills
        if entity_types is None or "installed_skills" in entity_types:
            for installed_data in response.get("installed_skills", []):
                conflict = self._update_installed_skill_from_server(installed_data)
                if conflict:
                    conflicts.append(conflict)

        # Process harness configs
        if entity_types is None or "harness_configs" in entity_types:
            for config_data in response.get("harness_configs", []):
                conflict = self._update_harness_config_from_server(config_data)
                if conflict:
                    conflicts.append(conflict)

        return conflicts

    def _update_project_from_server(
        self, data: dict[str, Any]
    ) -> SyncConflict | None:
        """Update a project from server data.

        Args:
            data: Server project data

        Returns:
            SyncConflict if there was a conflict, None otherwise
        """
        server_id = data["server_id"]
        server_updated = datetime.fromisoformat(data["updated_at"])

        # Check for existing local item
        existing = self._cache.projects.get_by_server_id(server_id)

        if existing and existing.dirty:
            # Conflict detected - use last-write-wins
            local_updated = existing.updated_at or datetime.min.replace(tzinfo=UTC)
            if local_updated.tzinfo is None:
                local_updated = local_updated.replace(tzinfo=UTC)

            # Collect entity data for diff
            local_data = {
                "name": existing.name,
                "description": existing.description,
                "updated_at": existing.updated_at.isoformat() if existing.updated_at else None,
            }
            server_data = {
                "name": data["name"],
                "description": data.get("description"),
                "updated_at": data["updated_at"],
            }

            if server_updated > local_updated:
                # Server wins
                resolution = ConflictResolution.SERVER_WINS
                self._apply_server_project(existing, data)
            else:
                # Local wins - don't update
                resolution = ConflictResolution.LOCAL_WINS

            conflict = SyncConflict(
                entity_type=EntityType.PROJECT,
                local_id=existing.id,
                server_id=server_id,
                local_updated_at=local_updated,
                server_updated_at=server_updated,
                resolution=resolution,
            )

            # Persist conflict for manual review
            self._persist_conflict(conflict, local_data, server_data)

            return conflict
        else:
            # No conflict - update or create
            self._cache.cache_project(
                server_id=server_id,
                name=data["name"],
                description=data.get("description"),
            )
            return None

    def _apply_server_project(
        self, existing: CachedProject, data: dict[str, Any]
    ) -> None:
        """Apply server data to existing project."""
        existing.name = data["name"]
        existing.description = data.get("description")
        existing.dirty = False
        existing.last_synced = datetime.now(UTC)
        self._cache.projects.set(existing)

    def _update_skill_from_server(
        self, data: dict[str, Any]
    ) -> SyncConflict | None:
        """Update a skill from server data.

        Args:
            data: Server skill data

        Returns:
            SyncConflict if there was a conflict, None otherwise
        """
        server_id = data["server_id"]
        server_updated = datetime.fromisoformat(data["updated_at"])

        existing = self._cache.skills.get_by_server_id(server_id)

        if existing and existing.dirty:
            local_updated = existing.updated_at or datetime.min.replace(tzinfo=UTC)
            if local_updated.tzinfo is None:
                local_updated = local_updated.replace(tzinfo=UTC)

            if server_updated > local_updated:
                resolution = ConflictResolution.SERVER_WINS
                self._apply_server_skill(existing, data)
            else:
                resolution = ConflictResolution.LOCAL_WINS

            return SyncConflict(
                entity_type=EntityType.SKILL,
                local_id=existing.id,
                server_id=server_id,
                local_updated_at=local_updated,
                server_updated_at=server_updated,
                resolution=resolution,
            )
        else:
            self._cache.cache_skill(
                server_id=server_id,
                source_id=data.get("source_id"),
                name=data["name"],
                display_name=data.get("display_name"),
                description=data.get("description"),
                version=data.get("version"),
                author=data.get("author"),
                tags=data.get("tags", []),
                metadata=data.get("metadata", {}),
            )
            return None

    def _apply_server_skill(self, existing: CachedSkill, data: dict[str, Any]) -> None:
        """Apply server data to existing skill."""
        existing.source_id = data.get("source_id")
        existing.name = data["name"]
        existing.display_name = data.get("display_name")
        existing.description = data.get("description")
        existing.version = data.get("version")
        existing.author = data.get("author")
        if data.get("tags"):
            existing.set_tags_list(data["tags"])
        if data.get("metadata"):
            existing.set_metadata_dict(data["metadata"])
        existing.dirty = False
        existing.last_synced = datetime.now(UTC)
        self._cache.skills.set(existing)

    def _update_installed_skill_from_server(
        self, data: dict[str, Any]
    ) -> SyncConflict | None:
        """Update an installed skill from server data.

        Args:
            data: Server installed skill data

        Returns:
            SyncConflict if there was a conflict, None otherwise
        """
        server_id = data["server_id"]
        server_updated = datetime.fromisoformat(data["updated_at"])

        existing = self._cache.installed_skills.get_by_server_id(server_id)

        if existing and existing.dirty:
            local_updated = existing.updated_at or datetime.min.replace(tzinfo=UTC)
            if local_updated.tzinfo is None:
                local_updated = local_updated.replace(tzinfo=UTC)

            if server_updated > local_updated:
                resolution = ConflictResolution.SERVER_WINS
                self._apply_server_installed_skill(existing, data)
            else:
                resolution = ConflictResolution.LOCAL_WINS

            return SyncConflict(
                entity_type=EntityType.INSTALLED_SKILL,
                local_id=existing.id,
                server_id=server_id,
                local_updated_at=local_updated,
                server_updated_at=server_updated,
                resolution=resolution,
            )
        else:
            scope = InstallScope(data["scope"])
            self._cache.cache_installed_skill(
                server_id=server_id,
                skill_id=data.get("skill_id"),
                harness_id=data.get("harness_id"),
                scope=scope,
                installed_path=data["installed_path"],
                project_id=data.get("project_id"),
                pinned_version=data.get("pinned_version"),
            )
            return None

    def _apply_server_installed_skill(
        self, existing: CachedInstalledSkill, data: dict[str, Any]
    ) -> None:
        """Apply server data to existing installed skill."""
        existing.skill_id = data.get("skill_id")
        existing.harness_id = data.get("harness_id")
        existing.scope = InstallScope(data["scope"])
        existing.installed_path = data["installed_path"]
        existing.project_id = data.get("project_id")
        existing.pinned_version = data.get("pinned_version")
        existing.dirty = False
        existing.last_synced = datetime.now(UTC)
        self._cache.installed_skills.set(existing)

    def _update_harness_config_from_server(
        self, data: dict[str, Any]
    ) -> SyncConflict | None:
        """Update a harness config from server data.

        Args:
            data: Server harness config data

        Returns:
            SyncConflict if there was a conflict, None otherwise
        """
        server_id = data["server_id"]
        server_updated = datetime.fromisoformat(data["updated_at"])

        existing = self._cache.harness_configs.get_by_server_id(server_id)

        if existing and existing.dirty:
            local_updated = existing.updated_at or datetime.min.replace(tzinfo=UTC)
            if local_updated.tzinfo is None:
                local_updated = local_updated.replace(tzinfo=UTC)

            if server_updated > local_updated:
                resolution = ConflictResolution.SERVER_WINS
                self._apply_server_harness_config(existing, data)
            else:
                resolution = ConflictResolution.LOCAL_WINS

            return SyncConflict(
                entity_type=EntityType.HARNESS_CONFIG,
                local_id=existing.id,
                server_id=server_id,
                local_updated_at=local_updated,
                server_updated_at=server_updated,
                resolution=resolution,
            )
        else:
            scope = ConfigScope(data["scope"])
            self._cache.cache_harness_config(
                server_id=server_id,
                harness_id=data.get("harness_id"),
                scope=scope,
                kind=data["kind"],
                path=data["path"],
                content=data.get("content"),
                content_hash=data.get("content_hash"),
                project_id=data.get("project_id"),
            )
            return None

    def _apply_server_harness_config(
        self, existing: CachedHarnessConfig, data: dict[str, Any]
    ) -> None:
        """Apply server data to existing harness config."""
        existing.harness_id = data.get("harness_id")
        existing.scope = ConfigScope(data["scope"])
        existing.kind = data["kind"]
        existing.path = data["path"]
        existing.content = data.get("content")
        existing.content_hash = data.get("content_hash")
        existing.project_id = data.get("project_id")
        existing.dirty = False
        existing.last_synced = datetime.now(UTC)
        self._cache.harness_configs.set(existing)
