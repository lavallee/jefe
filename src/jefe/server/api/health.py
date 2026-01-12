"""Health check endpoints."""

from fastapi import APIRouter

from jefe import __version__
from jefe.server.schemas.common import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check endpoint.

    Returns current service status and version information.
    """
    return HealthResponse(status="healthy", version=__version__)
