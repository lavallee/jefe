"""Schemas for status endpoint."""

from pydantic import BaseModel, Field


class StatusResponse(BaseModel):
    """Service status response."""

    projects: int = Field(..., description="Number of projects")
    manifestations: int = Field(..., description="Number of manifestations")
    configs: int = Field(..., description="Number of discovered configs")
    harnesses: int = Field(..., description="Number of registered harnesses")
