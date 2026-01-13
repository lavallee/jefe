"""Repository pattern for cache operations."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from jefe.cli.cache.database import get_cache_session, init_cache_db
from jefe.cli.cache.models import (
    CachedConflict,
    CachedHarness,
    CachedHarnessConfig,
    CachedInstalledSkill,
    CachedProject,
    CachedSkill,
    CachedSource,
    ConfigScope,
    ConflictResolutionType,
    InstallScope,
    SyncMixin,
)

# Type variable for cache entities
T = TypeVar("T", bound=SyncMixin)

# Default cache TTL in seconds (5 minutes)
DEFAULT_TTL = 300


class CacheRepository(Generic[T]):
    """Base repository for cache operations with TTL and dirty tracking."""

    def __init__(self, model_class: type[T], ttl_seconds: int = DEFAULT_TTL):
        """Initialize the cache repository.

        Args:
            model_class: The SQLAlchemy model class for this repository
            ttl_seconds: Time-to-live in seconds for cache freshness (default: 300)
        """
        self.model_class = model_class
        self.ttl_seconds = ttl_seconds
        self._session: Session | None = None

    def _get_session(self) -> Session:
        """Get or create a database session."""
        if self._session is None:
            init_cache_db()  # Ensure DB is initialized
            self._session = get_cache_session()
        return self._session

    def close(self) -> None:
        """Close the database session."""
        if self._session:
            self._session.close()
            self._session = None

    def get_by_server_id(self, server_id: int) -> T | None:
        """Get a cached item by server ID.

        Args:
            server_id: The server ID to look up

        Returns:
            The cached item or None if not found
        """
        session = self._get_session()
        stmt = select(self.model_class).where(self.model_class.server_id == server_id)
        return session.execute(stmt).scalar_one_or_none()

    def get_all(self) -> list[T]:
        """Get all cached items.

        Returns:
            List of all cached items
        """
        session = self._get_session()
        stmt = select(self.model_class)
        return list(session.execute(stmt).scalars().all())

    def is_fresh(self, item: T) -> bool:
        """Check if a cached item is still fresh based on TTL.

        Args:
            item: The cached item to check

        Returns:
            True if the item is within the TTL window, False otherwise
        """
        if item.last_synced is None:
            return False

        now = datetime.now(UTC)
        # Ensure last_synced is timezone-aware
        last_synced = item.last_synced
        if last_synced.tzinfo is None:
            last_synced = last_synced.replace(tzinfo=UTC)

        age = now - last_synced
        return age < timedelta(seconds=self.ttl_seconds)

    def set(self, item: T) -> None:
        """Save or update a cached item.

        Args:
            item: The item to save
        """
        session = self._get_session()
        session.add(item)
        session.commit()

    def set_many(self, items: list[T]) -> None:
        """Save or update multiple cached items.

        Args:
            items: The items to save
        """
        session = self._get_session()
        session.add_all(items)
        session.commit()

    def mark_dirty(self, item: T) -> None:
        """Mark an item as dirty (locally modified).

        Args:
            item: The item to mark dirty
        """
        item.dirty = True
        session = self._get_session()
        session.add(item)
        session.commit()

    def get_dirty(self) -> list[T]:
        """Get all dirty (locally modified) items.

        Returns:
            List of all items marked as dirty
        """
        session = self._get_session()
        stmt = select(self.model_class).where(self.model_class.dirty == True)  # noqa: E712
        return list(session.execute(stmt).scalars().all())

    def clear_dirty(self, item: T) -> None:
        """Clear the dirty flag on an item.

        Args:
            item: The item to clear dirty flag from
        """
        item.dirty = False
        item.last_synced = datetime.now(UTC)
        session = self._get_session()
        session.add(item)
        session.commit()

    def clear_all_dirty(self) -> None:
        """Clear dirty flags on all items and update last_synced."""
        session = self._get_session()
        dirty_items = self.get_dirty()
        now = datetime.now(UTC)
        for item in dirty_items:
            item.dirty = False
            item.last_synced = now
        session.commit()

    def delete(self, item: T) -> None:
        """Delete an item from the cache.

        Args:
            item: The item to delete
        """
        session = self._get_session()
        session.delete(item)
        session.commit()


class ProjectRepository(CacheRepository[CachedProject]):
    """Repository for cached projects."""

    def __init__(self, ttl_seconds: int = DEFAULT_TTL):
        """Initialize the project repository."""
        super().__init__(CachedProject, ttl_seconds)

    def get_by_name(self, name: str) -> CachedProject | None:
        """Get a cached project by name.

        Args:
            name: The project name to look up

        Returns:
            The cached project or None if not found
        """
        session = self._get_session()
        stmt = select(CachedProject).where(CachedProject.name == name)
        return session.execute(stmt).scalar_one_or_none()


class SkillRepository(CacheRepository[CachedSkill]):
    """Repository for cached skills."""

    def __init__(self, ttl_seconds: int = DEFAULT_TTL):
        """Initialize the skill repository."""
        super().__init__(CachedSkill, ttl_seconds)

    def get_by_name(self, name: str) -> CachedSkill | None:
        """Get a cached skill by name.

        Args:
            name: The skill name to look up

        Returns:
            The cached skill or None if not found
        """
        session = self._get_session()
        stmt = select(CachedSkill).where(CachedSkill.name == name)
        return session.execute(stmt).scalar_one_or_none()

    def get_by_source(self, source_id: int) -> list[CachedSkill]:
        """Get all cached skills from a specific source.

        Args:
            source_id: The source ID to filter by

        Returns:
            List of cached skills from the source
        """
        session = self._get_session()
        stmt = select(CachedSkill).where(CachedSkill.source_id == source_id)
        return list(session.execute(stmt).scalars().all())


class InstalledSkillRepository(CacheRepository[CachedInstalledSkill]):
    """Repository for cached installed skills."""

    def __init__(self, ttl_seconds: int = DEFAULT_TTL):
        """Initialize the installed skill repository."""
        super().__init__(CachedInstalledSkill, ttl_seconds)

    def get_by_skill_id(self, skill_id: int) -> list[CachedInstalledSkill]:
        """Get all installations of a specific skill.

        Args:
            skill_id: The skill ID to look up

        Returns:
            List of all installations of the skill
        """
        session = self._get_session()
        stmt = select(CachedInstalledSkill).where(
            CachedInstalledSkill.skill_id == skill_id
        )
        return list(session.execute(stmt).scalars().all())

    def get_by_scope(
        self, scope: InstallScope, project_id: int | None = None
    ) -> list[CachedInstalledSkill]:
        """Get installed skills by scope.

        Args:
            scope: The installation scope (GLOBAL or PROJECT)
            project_id: The project ID (required for PROJECT scope)

        Returns:
            List of installed skills matching the scope
        """
        session = self._get_session()
        stmt = select(CachedInstalledSkill).where(
            CachedInstalledSkill.scope == scope
        )
        if scope == InstallScope.PROJECT and project_id is not None:
            stmt = stmt.where(CachedInstalledSkill.project_id == project_id)
        return list(session.execute(stmt).scalars().all())


class HarnessConfigRepository(CacheRepository[CachedHarnessConfig]):
    """Repository for cached harness configurations."""

    def __init__(self, ttl_seconds: int = DEFAULT_TTL):
        """Initialize the harness config repository."""
        super().__init__(CachedHarnessConfig, ttl_seconds)

    def get_by_harness_id(self, harness_id: int) -> list[CachedHarnessConfig]:
        """Get all configs for a specific harness.

        Args:
            harness_id: The harness ID to look up

        Returns:
            List of all configs for the harness
        """
        session = self._get_session()
        stmt = select(CachedHarnessConfig).where(
            CachedHarnessConfig.harness_id == harness_id
        )
        return list(session.execute(stmt).scalars().all())

    def get_by_scope(
        self, scope: ConfigScope, project_id: int | None = None
    ) -> list[CachedHarnessConfig]:
        """Get harness configs by scope.

        Args:
            scope: The configuration scope (GLOBAL or PROJECT)
            project_id: The project ID (required for PROJECT scope)

        Returns:
            List of configs matching the scope
        """
        session = self._get_session()
        stmt = select(CachedHarnessConfig).where(CachedHarnessConfig.scope == scope)
        if scope == ConfigScope.PROJECT and project_id is not None:
            stmt = stmt.where(CachedHarnessConfig.project_id == project_id)
        return list(session.execute(stmt).scalars().all())

    def get_by_path(self, path: str) -> CachedHarnessConfig | None:
        """Get a config by its path.

        Args:
            path: The config path to look up

        Returns:
            The cached config or None if not found
        """
        session = self._get_session()
        stmt = select(CachedHarnessConfig).where(CachedHarnessConfig.path == path)
        return session.execute(stmt).scalar_one_or_none()


class SourceRepository(CacheRepository[CachedSource]):
    """Repository for cached skill sources."""

    def __init__(self, ttl_seconds: int = DEFAULT_TTL):
        """Initialize the source repository."""
        super().__init__(CachedSource, ttl_seconds)

    def get_by_name(self, name: str) -> CachedSource | None:
        """Get a cached source by name.

        Args:
            name: The source name to look up

        Returns:
            The cached source or None if not found
        """
        session = self._get_session()
        stmt = select(CachedSource).where(CachedSource.name == name)
        return session.execute(stmt).scalar_one_or_none()

    def get_by_url(self, url: str) -> CachedSource | None:
        """Get a cached source by URL.

        Args:
            url: The source URL to look up

        Returns:
            The cached source or None if not found
        """
        session = self._get_session()
        stmt = select(CachedSource).where(CachedSource.url == url)
        return session.execute(stmt).scalar_one_or_none()


class HarnessRepository(CacheRepository[CachedHarness]):
    """Repository for cached harnesses."""

    def __init__(self, ttl_seconds: int = DEFAULT_TTL):
        """Initialize the harness repository."""
        super().__init__(CachedHarness, ttl_seconds)

    def get_by_name(self, name: str) -> CachedHarness | None:
        """Get a cached harness by name.

        Args:
            name: The harness name to look up

        Returns:
            The cached harness or None if not found
        """
        session = self._get_session()
        stmt = select(CachedHarness).where(CachedHarness.name == name)
        return session.execute(stmt).scalar_one_or_none()


class ConflictRepository:
    """Repository for sync conflicts."""

    def __init__(self) -> None:
        """Initialize the conflict repository."""
        self._session: Session | None = None

    def _get_session(self) -> Session:
        """Get or create a database session."""
        if self._session is None:
            init_cache_db()
            self._session = get_cache_session()
        return self._session

    def close(self) -> None:
        """Close the database session."""
        if self._session:
            self._session.close()
            self._session = None

    def get_by_id(self, conflict_id: int) -> CachedConflict | None:
        """Get a conflict by ID.

        Args:
            conflict_id: The conflict ID to look up

        Returns:
            The conflict or None if not found
        """
        session = self._get_session()
        stmt = select(CachedConflict).where(CachedConflict.id == conflict_id)
        return session.execute(stmt).scalar_one_or_none()

    def get_unresolved(self) -> list[CachedConflict]:
        """Get all unresolved conflicts.

        Returns:
            List of all unresolved conflicts
        """
        session = self._get_session()
        stmt = select(CachedConflict).where(
            CachedConflict.resolution == ConflictResolutionType.UNRESOLVED
        )
        return list(session.execute(stmt).scalars().all())

    def get_all(self) -> list[CachedConflict]:
        """Get all conflicts.

        Returns:
            List of all conflicts
        """
        session = self._get_session()
        stmt = select(CachedConflict)
        return list(session.execute(stmt).scalars().all())

    def add(self, conflict: CachedConflict) -> None:
        """Add a new conflict.

        Args:
            conflict: The conflict to add
        """
        session = self._get_session()
        session.add(conflict)
        session.commit()

    def resolve(
        self, conflict_id: int, resolution: ConflictResolutionType
    ) -> CachedConflict | None:
        """Resolve a conflict.

        Args:
            conflict_id: The conflict ID to resolve
            resolution: The resolution to apply

        Returns:
            The resolved conflict or None if not found
        """
        conflict = self.get_by_id(conflict_id)
        if conflict:
            conflict.resolution = resolution
            conflict.resolved_at = datetime.now(UTC)
            session = self._get_session()
            session.add(conflict)
            session.commit()
        return conflict

    def delete(self, conflict_id: int) -> bool:
        """Delete a conflict.

        Args:
            conflict_id: The conflict ID to delete

        Returns:
            True if deleted, False if not found
        """
        conflict = self.get_by_id(conflict_id)
        if conflict:
            session = self._get_session()
            session.delete(conflict)
            session.commit()
            return True
        return False

    def clear_resolved(self) -> int:
        """Clear all resolved conflicts.

        Returns:
            Number of conflicts cleared
        """
        session = self._get_session()
        stmt = select(CachedConflict).where(
            CachedConflict.resolution != ConflictResolutionType.UNRESOLVED
        )
        resolved = list(session.execute(stmt).scalars().all())
        for conflict in resolved:
            session.delete(conflict)
        session.commit()
        return len(resolved)
