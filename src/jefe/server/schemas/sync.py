"""Schemas for sync API."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class EntityType(str, Enum):
    """Types of entities that can be synced."""

    PROJECT = "project"
    SKILL = "skill"
    INSTALLED_SKILL = "installed_skill"
    HARNESS_CONFIG = "harness_config"


class ConflictResolution(str, Enum):
    """How a conflict was resolved."""

    LOCAL_WINS = "local_wins"
    SERVER_WINS = "server_wins"


# Push schemas


class SyncProjectItem(BaseModel):
    """A project item to sync to the server."""

    local_id: int = Field(..., description="Local cache ID")
    server_id: int | None = Field(None, description="Server ID if known")
    name: str = Field(..., description="Project name")
    description: str | None = Field(None, description="Project description")
    updated_at: datetime = Field(..., description="When the item was last modified locally")


class SyncSkillItem(BaseModel):
    """A skill item to sync to the server."""

    local_id: int = Field(..., description="Local cache ID")
    server_id: int | None = Field(None, description="Server ID if known")
    source_id: int | None = Field(None, description="Source ID")
    name: str = Field(..., description="Skill name")
    display_name: str | None = Field(None, description="Display name")
    description: str | None = Field(None, description="Description")
    version: str | None = Field(None, description="Version")
    author: str | None = Field(None, description="Author")
    tags: list[str] = Field(default_factory=list, description="Tags")
    metadata: dict[str, object] = Field(default_factory=dict, description="Metadata")
    updated_at: datetime = Field(..., description="When the item was last modified locally")


class SyncInstalledSkillItem(BaseModel):
    """An installed skill item to sync to the server."""

    local_id: int = Field(..., description="Local cache ID")
    server_id: int | None = Field(None, description="Server ID if known")
    skill_id: int | None = Field(None, description="Skill ID")
    harness_id: int | None = Field(None, description="Harness ID")
    scope: str = Field(..., description="Installation scope (global or project)")
    project_id: int | None = Field(None, description="Project ID for project scope")
    installed_path: str = Field(..., description="Path where skill is installed")
    pinned_version: str | None = Field(None, description="Pinned version")
    updated_at: datetime = Field(..., description="When the item was last modified locally")


class SyncHarnessConfigItem(BaseModel):
    """A harness config item to sync to the server."""

    local_id: int = Field(..., description="Local cache ID")
    server_id: int | None = Field(None, description="Server ID if known")
    harness_id: int | None = Field(None, description="Harness ID")
    scope: str = Field(..., description="Configuration scope (global or project)")
    kind: str = Field(..., description="Config kind")
    path: str = Field(..., description="Config path")
    content: str | None = Field(None, description="Config content")
    content_hash: str | None = Field(None, description="Content hash")
    project_id: int | None = Field(None, description="Project ID for project scope")
    updated_at: datetime = Field(..., description="When the item was last modified locally")


class SyncPushRequest(BaseModel):
    """Request to push local changes to the server."""

    projects: list[SyncProjectItem] = Field(
        default_factory=list, description="Dirty projects to push"
    )
    skills: list[SyncSkillItem] = Field(default_factory=list, description="Dirty skills to push")
    installed_skills: list[SyncInstalledSkillItem] = Field(
        default_factory=list, description="Dirty installed skills to push"
    )
    harness_configs: list[SyncHarnessConfigItem] = Field(
        default_factory=list, description="Dirty harness configs to push"
    )


class SyncConflictInfo(BaseModel):
    """Information about a sync conflict."""

    entity_type: EntityType = Field(..., description="Type of entity with conflict")
    local_id: int = Field(..., description="Local cache ID")
    server_id: int = Field(..., description="Server ID")
    local_updated_at: datetime = Field(..., description="Local modification time")
    server_updated_at: datetime = Field(..., description="Server modification time")
    resolution: ConflictResolution = Field(..., description="How conflict was resolved")


class SyncPushResponse(BaseModel):
    """Response after pushing local changes."""

    success: bool = Field(..., description="Whether push succeeded")
    projects_synced: int = Field(0, description="Number of projects synced")
    skills_synced: int = Field(0, description="Number of skills synced")
    installed_skills_synced: int = Field(0, description="Number of installed skills synced")
    harness_configs_synced: int = Field(0, description="Number of harness configs synced")
    conflicts: list[SyncConflictInfo] = Field(
        default_factory=list, description="Conflicts that occurred"
    )
    server_id_mappings: dict[str, dict[int, int]] = Field(
        default_factory=dict,
        description="Mapping of local IDs to server IDs by entity type",
    )


# Pull schemas


class SyncPullRequest(BaseModel):
    """Request to pull server changes."""

    last_synced: datetime | None = Field(
        None, description="Last sync timestamp (ISO 8601) to get changes since"
    )
    entity_types: list[EntityType] | None = Field(
        None, description="Specific entity types to pull (None = all)"
    )


class ServerProjectItem(BaseModel):
    """A project item from the server."""

    server_id: int = Field(..., description="Server ID")
    name: str = Field(..., description="Project name")
    description: str | None = Field(None, description="Project description")
    updated_at: datetime = Field(..., description="Server modification time")


class ServerSkillItem(BaseModel):
    """A skill item from the server."""

    server_id: int = Field(..., description="Server ID")
    source_id: int | None = Field(None, description="Source ID")
    name: str = Field(..., description="Skill name")
    display_name: str | None = Field(None, description="Display name")
    description: str | None = Field(None, description="Description")
    version: str | None = Field(None, description="Version")
    author: str | None = Field(None, description="Author")
    tags: list[str] = Field(default_factory=list, description="Tags")
    metadata: dict[str, object] = Field(default_factory=dict, description="Metadata")
    updated_at: datetime = Field(..., description="Server modification time")


class ServerInstalledSkillItem(BaseModel):
    """An installed skill item from the server."""

    server_id: int = Field(..., description="Server ID")
    skill_id: int | None = Field(None, description="Skill ID")
    harness_id: int | None = Field(None, description="Harness ID")
    scope: str = Field(..., description="Installation scope")
    project_id: int | None = Field(None, description="Project ID")
    installed_path: str = Field(..., description="Installed path")
    pinned_version: str | None = Field(None, description="Pinned version")
    updated_at: datetime = Field(..., description="Server modification time")


class ServerHarnessConfigItem(BaseModel):
    """A harness config item from the server."""

    server_id: int = Field(..., description="Server ID")
    harness_id: int | None = Field(None, description="Harness ID")
    scope: str = Field(..., description="Config scope")
    kind: str = Field(..., description="Config kind")
    path: str = Field(..., description="Config path")
    content: str | None = Field(None, description="Config content")
    content_hash: str | None = Field(None, description="Content hash")
    project_id: int | None = Field(None, description="Project ID")
    updated_at: datetime = Field(..., description="Server modification time")


class SyncPullResponse(BaseModel):
    """Response with server changes to pull."""

    success: bool = Field(..., description="Whether pull succeeded")
    server_time: datetime = Field(..., description="Current server time")
    projects: list[ServerProjectItem] = Field(
        default_factory=list, description="Changed projects"
    )
    skills: list[ServerSkillItem] = Field(default_factory=list, description="Changed skills")
    installed_skills: list[ServerInstalledSkillItem] = Field(
        default_factory=list, description="Changed installed skills"
    )
    harness_configs: list[ServerHarnessConfigItem] = Field(
        default_factory=list, description="Changed harness configs"
    )
