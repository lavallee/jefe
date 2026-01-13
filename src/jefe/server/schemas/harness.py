"""Schemas for harness API."""

from pydantic import BaseModel, Field

from jefe.data.models.harness_config import ConfigScope


class HarnessResponse(BaseModel):
    """Harness metadata."""

    id: int = Field(..., description="Harness ID")
    name: str = Field(..., description="Harness identifier")
    display_name: str = Field(..., description="Human readable name")
    version: str = Field(..., description="Adapter version")


class HarnessConfigResponse(BaseModel):
    """Discovered config response."""

    harness: str = Field(..., description="Harness identifier")
    scope: ConfigScope = Field(..., description="Config scope (global or project)")
    kind: str = Field(..., description="Config kind (settings, instructions, skills)")
    path: str = Field(..., description="Config file path")
    content: dict[str, object] | str | None = Field(
        None, description="Config content, parsed if possible"
    )
    content_hash: str | None = Field(None, description="Hash of the raw config content")
    project_id: int | None = Field(None, description="Project id for project configs")
    project_name: str | None = Field(None, description="Project name for project configs")
