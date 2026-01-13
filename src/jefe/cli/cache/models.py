"""Local cache models for offline CLI operation."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, ClassVar

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class CacheBase(DeclarativeBase):
    """Base class for all cache SQLAlchemy models."""

    # Type annotation map for common types
    type_annotation_map: ClassVar[dict[type, Any]] = {
        datetime: DateTime(timezone=True),
    }


class SyncMixin:
    """Mixin that adds sync metadata columns."""

    last_synced: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    dirty: Mapped[bool] = mapped_column(default=False, nullable=False)
    server_id: Mapped[int | None] = mapped_column(nullable=True)


class CachedProject(CacheBase, SyncMixin):
    """Cached project entry."""

    __tablename__ = "cached_projects"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Mirror Project model fields
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class CachedSkill(CacheBase, SyncMixin):
    """Cached skill metadata."""

    __tablename__ = "cached_skills"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Mirror Skill model fields
    source_id: Mapped[int | None] = mapped_column(
        nullable=True
    )  # Nullable in cache (may not have source cached)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tags: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array as string
    metadata_json: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # JSON object as string

    def get_tags_list(self) -> list[str]:
        """Parse tags JSON string to list."""
        import json

        if self.tags:
            try:
                result = json.loads(self.tags)
                return result if isinstance(result, list) else []
            except json.JSONDecodeError:
                return []
        return []

    def set_tags_list(self, tags: list[str]) -> None:
        """Convert tags list to JSON string."""
        import json

        self.tags = json.dumps(tags)

    def get_metadata_dict(self) -> dict[str, Any]:
        """Parse metadata JSON string to dict."""
        import json

        if self.metadata_json:
            try:
                result = json.loads(self.metadata_json)
                return result if isinstance(result, dict) else {}
            except json.JSONDecodeError:
                return {}
        return {}

    def set_metadata_dict(self, metadata: dict[str, Any]) -> None:
        """Convert metadata dict to JSON string."""
        import json

        self.metadata_json = json.dumps(metadata)


class InstallScope(str, Enum):
    """Scope of a skill installation."""

    GLOBAL = "global"
    PROJECT = "project"


class CachedInstalledSkill(CacheBase, SyncMixin):
    """Cached record of installed skills."""

    __tablename__ = "cached_installed_skills"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Mirror InstalledSkill model fields
    skill_id: Mapped[int | None] = mapped_column(nullable=True)
    harness_id: Mapped[int | None] = mapped_column(nullable=True)
    scope: Mapped[InstallScope] = mapped_column(
        SqlEnum(
            InstallScope,
            name="install_scope",
            values_callable=lambda obj: [item.value for item in obj],
        ),
        nullable=False,
    )
    project_id: Mapped[int | None] = mapped_column(nullable=True)
    installed_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    pinned_version: Mapped[str | None] = mapped_column(String(50), nullable=True)


class ConfigScope(str, Enum):
    """Scope of a harness configuration."""

    GLOBAL = "global"
    PROJECT = "project"


class CachedHarnessConfig(CacheBase, SyncMixin):
    """Cached harness configuration entry."""

    __tablename__ = "cached_harness_configs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Mirror HarnessConfig model fields
    harness_id: Mapped[int | None] = mapped_column(nullable=True)
    scope: Mapped[ConfigScope] = mapped_column(
        SqlEnum(
            ConfigScope,
            name="config_scope",
            values_callable=lambda obj: [item.value for item in obj],
        ),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    path: Mapped[str] = mapped_column(String(1024), nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    project_id: Mapped[int | None] = mapped_column(nullable=True)


class CachedSource(CacheBase, SyncMixin):
    """Cached skill source entry."""

    __tablename__ = "cached_sources"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Mirror SkillSource model fields
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, default="git")
    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sync_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class CachedHarness(CacheBase, SyncMixin):
    """Cached harness entry."""

    __tablename__ = "cached_harnesses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Mirror Harness model fields
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    version: Mapped[str | None] = mapped_column(String(50), nullable=True)


class ConflictResolutionType(str, Enum):
    """How a conflict was or should be resolved."""

    LOCAL_WINS = "local_wins"
    SERVER_WINS = "server_wins"
    UNRESOLVED = "unresolved"


class ConflictEntityType(str, Enum):
    """Types of entities that can have conflicts."""

    PROJECT = "project"
    SKILL = "skill"
    INSTALLED_SKILL = "installed_skill"
    HARNESS_CONFIG = "harness_config"


class CachedConflict(CacheBase):
    """Cached sync conflict for manual resolution."""

    __tablename__ = "cached_conflicts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Conflict details
    entity_type: Mapped[ConflictEntityType] = mapped_column(
        SqlEnum(
            ConflictEntityType,
            name="conflict_entity_type",
            values_callable=lambda obj: [item.value for item in obj],
        ),
        nullable=False,
    )
    local_id: Mapped[int] = mapped_column(nullable=False)
    server_id: Mapped[int] = mapped_column(nullable=False)
    local_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    server_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # Resolution status
    resolution: Mapped[ConflictResolutionType] = mapped_column(
        SqlEnum(
            ConflictResolutionType,
            name="conflict_resolution_type",
            values_callable=lambda obj: [item.value for item in obj],
        ),
        nullable=False,
        default=ConflictResolutionType.UNRESOLVED,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Store entity data for diff display
    local_data: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    server_data: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
