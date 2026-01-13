"""Schemas for skill API."""

from pydantic import BaseModel, Field

from jefe.data.models.installed_skill import InstallScope


class SkillResponse(BaseModel):
    """Skill response payload."""

    id: int = Field(..., description="Skill ID")
    source_id: int = Field(..., description="Source ID")
    name: str = Field(..., description="Skill name")
    display_name: str | None = Field(None, description="Display name")
    description: str | None = Field(None, description="Description")
    version: str | None = Field(None, description="Version")
    author: str | None = Field(None, description="Author")
    tags: list[str] = Field(default_factory=list, description="Tags")
    metadata: dict[str, object] = Field(default_factory=dict, description="Additional metadata")


class InstalledSkillResponse(BaseModel):
    """Installed skill response payload."""

    id: int = Field(..., description="Installation ID")
    skill_id: int = Field(..., description="Skill ID")
    harness_id: int = Field(..., description="Harness ID")
    scope: InstallScope = Field(..., description="Installation scope (global or project)")
    project_id: int | None = Field(None, description="Project ID (if project scope)")
    installed_path: str = Field(..., description="Installed path")
    pinned_version: str | None = Field(None, description="Pinned version")
    skill: SkillResponse = Field(..., description="Skill details")


class SkillInstallRequest(BaseModel):
    """Request to install a skill."""

    skill_id: int = Field(..., description="Skill ID to install")
    harness_id: int = Field(..., description="Harness ID to install to")
    scope: InstallScope = Field(..., description="Installation scope (global or project)")
    project_id: int | None = Field(None, description="Project ID (required for project scope)")
