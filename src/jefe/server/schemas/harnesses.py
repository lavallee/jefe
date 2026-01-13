"""Schemas for harness discovery and configs."""

from pydantic import BaseModel, Field


class HarnessInfo(BaseModel):
    """Harness metadata."""

    name: str = Field(..., description="Harness identifier")
    display_name: str = Field(..., description="Human readable name")
    version: str = Field(..., description="Adapter version")


class HarnessConfigResponse(BaseModel):
    """Discovered config response."""

    harness: str = Field(..., description="Harness identifier")
    scope: str = Field(..., description="Config scope (global or project)")
    kind: str = Field(..., description="Config kind (settings, instructions, skills)")
    path: str = Field(..., description="Config file path")
    content: dict[str, object] | str | None = Field(
        None, description="Config content, parsed if possible"
    )
    project_id: int | None = Field(None, description="Project id for project configs")
    project_name: str | None = Field(None, description="Project name for project configs")
