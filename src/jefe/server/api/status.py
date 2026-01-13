"""Status API endpoint."""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from jefe.data.database import get_session
from jefe.data.models.harness import Harness
from jefe.data.models.harness_config import HarnessConfig
from jefe.data.models.manifestation import Manifestation
from jefe.data.models.project import Project
from jefe.server.auth import APIKey
from jefe.server.schemas.status import StatusResponse

router = APIRouter()


@router.get("/api/status", response_model=StatusResponse)
async def get_status(
    _api_key: APIKey, session: AsyncSession = Depends(get_session)
) -> StatusResponse:
    """Return counts for the current registry."""
    projects_count = await session.scalar(select(func.count(Project.id)))
    manifestations_count = await session.scalar(select(func.count(Manifestation.id)))
    configs_count = await session.scalar(select(func.count(HarnessConfig.id)))
    harnesses_count = await session.scalar(select(func.count(Harness.id)))

    return StatusResponse(
        projects=projects_count or 0,
        manifestations=manifestations_count or 0,
        configs=configs_count or 0,
        harnesses=harnesses_count or 0,
    )
