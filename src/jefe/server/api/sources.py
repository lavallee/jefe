"""Source API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jefe.data.database import get_session
from jefe.data.models.skill_source import SkillSource
from jefe.server.auth import APIKey
from jefe.server.schemas.source import SourceCreate, SourceResponse, SyncResponse
from jefe.server.services.skill_source import SkillSourceService, SkillSourceSyncError

router = APIRouter()


def _source_to_response(source: SkillSource) -> SourceResponse:
    """Convert a SkillSource model to a response schema."""
    return SourceResponse(
        id=source.id,
        name=source.name,
        source_type=source.source_type,
        url=source.url,
        description=source.description,
        sync_status=source.sync_status,
        last_synced_at=source.last_synced_at,
    )


@router.get("/api/sources", response_model=list[SourceResponse])
async def list_sources(
    _api_key: APIKey,
    session: AsyncSession = Depends(get_session),
) -> list[SourceResponse]:
    """List all skill sources."""
    service = SkillSourceService(session)
    sources = await service.list_sources()
    return [_source_to_response(source) for source in sources]


@router.post("/api/sources", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
async def create_source(
    payload: SourceCreate,
    _api_key: APIKey,
    session: AsyncSession = Depends(get_session),
) -> SourceResponse:
    """Create a new skill source."""
    # Check if name already exists
    existing = await session.execute(
        select(SkillSource).where(SkillSource.name == payload.name)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=400, detail="Source name already exists")

    # Create the source
    source = SkillSource(
        name=payload.name,
        source_type=payload.source_type,
        url=payload.url,
        description=payload.description,
    )
    session.add(source)
    await session.commit()
    await session.refresh(source)

    return _source_to_response(source)


@router.get("/api/sources/{source_id}", response_model=SourceResponse)
async def get_source(
    source_id: int,
    _api_key: APIKey,
    session: AsyncSession = Depends(get_session),
) -> SourceResponse:
    """Get a skill source by ID."""
    service = SkillSourceService(session)
    source = await service.get_source(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")

    return _source_to_response(source)


@router.delete("/api/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    source_id: int,
    _api_key: APIKey,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Delete a skill source."""
    result = await session.execute(
        select(SkillSource).where(SkillSource.id == source_id)
    )
    source = result.scalar_one_or_none()
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")

    await session.delete(source)
    await session.commit()


@router.post("/api/sources/{source_id}/sync", response_model=SyncResponse)
async def sync_source(
    source_id: int,
    _api_key: APIKey,
    session: AsyncSession = Depends(get_session),
) -> SyncResponse:
    """Trigger a sync for a skill source."""
    service = SkillSourceService(session)

    try:
        skills_updated = await service.sync_source(source_id)
        return SyncResponse(
            message=f"Successfully synced source {source_id}",
            skills_updated=skills_updated,
        )
    except SkillSourceSyncError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
