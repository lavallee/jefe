"""Schemas for bundle API."""

from pydantic import BaseModel, Field

from jefe.data.models.installed_skill import InstallScope


class SkillRef(BaseModel):
    """Reference to a skill in a bundle."""

    source: str = Field(..., description="Source name")
    name: str = Field(..., description="Skill name")


class BundleResponse(BaseModel):
    """Bundle response payload."""

    id: int = Field(..., description="Bundle ID")
    name: str = Field(..., description="Bundle name")
    display_name: str | None = Field(None, description="Display name")
    description: str | None = Field(None, description="Description")
    skill_refs: list[SkillRef] = Field(
        default_factory=list, description="Skill references"
    )


class BundleCreateRequest(BaseModel):
    """Request to create a bundle."""

    name: str = Field(..., description="Bundle name (unique identifier)")
    display_name: str | None = Field(None, description="Display name")
    description: str | None = Field(None, description="Description")
    skill_refs: list[SkillRef] = Field(
        ..., description="List of skill references (source and name)"
    )


class BundleApplyRequest(BaseModel):
    """Request to apply a bundle."""

    harness_id: int = Field(..., description="Harness ID to install skills to")
    scope: InstallScope = Field(..., description="Installation scope (global or project)")
    project_id: int | None = Field(None, description="Project ID (required for project scope)")


class BundleApplyResponse(BaseModel):
    """Response from applying a bundle."""

    success: int = Field(..., description="Number of skills successfully installed")
    failed: int = Field(..., description="Number of skills that failed to install")
    errors: list[str] = Field(
        default_factory=list, description="List of error messages for failed installations"
    )
