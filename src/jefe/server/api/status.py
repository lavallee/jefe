"""Status API endpoint."""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from jefe.adapters import get_adapters
from jefe.data.database import get_session
from jefe.data.models.project import Manifestation, Project
from jefe.server.auth import APIKey
from jefe.server.schemas.status import StatusResponse
from jefe.server.services.discovery import discover_all

router = APIRouter()


@router.get("/api/status", response_model=StatusResponse)
async def get_status(
    _api_key: APIKey, session: AsyncSession = Depends(get_session)
) -> StatusResponse:
    """Return counts for the current registry."""
    projects_count = await session.scalar(select(func.count(Project.id)))
    manifestations_count = await session.scalar(select(func.count(Manifestation.id)))
    configs = await discover_all(session)
    harnesses_count = len(get_adapters())

    return StatusResponse(
        projects=projects_count or 0,
        manifestations=manifestations_count or 0,
        configs=len(configs),
        harnesses=harnesses_count,
    )
