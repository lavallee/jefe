"""Schemas for project API."""

from datetime import datetime

from pydantic import BaseModel, Field

from jefe.data.models.project import ManifestationType
from jefe.server.schemas.harnesses import HarnessConfigResponse


class ManifestationCreate(BaseModel):
    """Manifestation create payload."""

    type: ManifestationType = Field(..., description="Manifestation type")
    path: str = Field(..., description="Filesystem path or remote URL")
    machine_id: str | None = Field(None, description="Machine identifier")


class ManifestationResponse(BaseModel):
    """Manifestation response payload."""

    id: int = Field(..., description="Manifestation id")
    type: ManifestationType = Field(..., description="Manifestation type")
    path: str = Field(..., description="Filesystem path or remote URL")
    machine_id: str | None = Field(None, description="Machine identifier")
    last_seen: datetime | None = Field(None, description="Last seen timestamp")


class ProjectCreate(BaseModel):
    """Project create payload."""

    name: str = Field(..., description="Project name")
    description: str | None = Field(None, description="Optional description")
    path: str | None = Field(None, description="Local path for the project")


class ProjectResponse(BaseModel):
    """Project response payload."""

    id: int = Field(..., description="Project id")
    name: str = Field(..., description="Project name")
    description: str | None = Field(None, description="Optional description")
    manifestations: list[ManifestationResponse] = Field(
        default_factory=list, description="Manifestations for the project"
    )


class ProjectDetailResponse(ProjectResponse):
    """Project detail response payload."""

    configs: list[HarnessConfigResponse] = Field(
        default_factory=list, description="Discovered configs for the project"
    )
