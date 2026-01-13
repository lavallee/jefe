"""Schemas for source API."""

from pydantic import BaseModel, Field

from jefe.data.models.skill_source import SourceType, SyncStatus


class SourceCreate(BaseModel):
    """Source create payload."""

    name: str = Field(..., description="Source name")
    source_type: SourceType = Field(..., description="Source type (GIT or MARKETPLACE)")
    url: str = Field(..., description="Source URL")
    description: str | None = Field(None, description="Optional description")


class SourceResponse(BaseModel):
    """Source response payload."""

    id: int = Field(..., description="Source id")
    name: str = Field(..., description="Source name")
    source_type: SourceType = Field(..., description="Source type")
    url: str = Field(..., description="Source URL")
    description: str | None = Field(None, description="Optional description")
    sync_status: SyncStatus = Field(..., description="Sync status")
    last_synced_at: str | None = Field(None, description="Last sync timestamp (ISO 8601)")


class SyncResponse(BaseModel):
    """Sync response payload."""

    message: str = Field(..., description="Sync result message")
    skills_updated: int = Field(..., description="Number of skills created or updated")
