"""Common Pydantic schemas used across the API."""

from pydantic import BaseModel, Field


class MessageResponse(BaseModel):
    """Standard message response schema."""

    message: str = Field(..., description="Response message")


class ErrorResponse(BaseModel):
    """Standard error response schema."""

    error: str = Field(..., description="Error type or category")
    message: str = Field(..., description="Detailed error message")
    details: dict[str, object] | list[object] | None = Field(
        None, description="Additional error details"
    )


class HealthResponse(BaseModel):
    """Health check response schema."""

    status: str = Field(..., description="Service status (healthy/unhealthy)")
    version: str = Field(..., description="Application version")
