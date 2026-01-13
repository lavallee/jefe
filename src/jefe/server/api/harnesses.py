"""Harness API endpoints."""

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jefe.data.database import get_session
from jefe.data.models.harness import Harness
from jefe.data.models.harness_config import HarnessConfig
from jefe.data.models.project import Project
from jefe.server.auth import APIKey
from jefe.server.schemas.harness import HarnessConfigResponse, HarnessResponse
from jefe.server.services.harness import HarnessService

router = APIRouter()


async def _configs_to_response(
    session: AsyncSession, configs: list[HarnessConfig]
) -> list[HarnessConfigResponse]:
    harnesses = await HarnessService(session).list_harnesses()
    harness_by_id = {harness.id: harness for harness in harnesses}

    result = await session.execute(select(Project))
    project_by_id = {project.id: project.name for project in result.scalars().all()}

    return [
        HarnessConfigResponse(
            harness=_get_harness_name(harness_by_id, config.harness_id),
            scope=config.scope,
            kind=config.kind,
            path=str(config.path),
            content=_parse_config_content(config.path, config.content),
            content_hash=config.content_hash,
            project_id=config.project_id,
            project_name=_get_project_name(project_by_id, config.project_id),
        )
        for config in configs
    ]


def _parse_config_content(path: str, content: str | None) -> dict[str, object] | str | None:
    if content is None:
        return None
    if path.lower().endswith(".json"):
        try:
            data = json.loads(content)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            return content
    return content


def _get_harness_name(harness_by_id: dict[int, Harness], harness_id: int | None) -> str:
    if harness_id is None:
        return "unknown"
    harness = harness_by_id.get(harness_id)
    if harness is None:
        return "unknown"
    return harness.name


def _get_project_name(project_by_id: dict[int, str], project_id: int | None) -> str | None:
    if project_id is None:
        return None
    return project_by_id.get(project_id)


@router.get("/api/harnesses", response_model=list[HarnessResponse])
async def list_harnesses(
    _api_key: APIKey, session: AsyncSession = Depends(get_session)
) -> list[HarnessResponse]:
    """List available harnesses."""
    harnesses = await HarnessService(session).list_harnesses()
    return [
        HarnessResponse(
            id=harness.id,
            name=harness.name,
            display_name=harness.display_name,
            version=harness.version,
        )
        for harness in harnesses
    ]


@router.get("/api/harnesses/{harness_name}", response_model=HarnessResponse)
async def get_harness(
    harness_name: str,
    _api_key: APIKey,
    session: AsyncSession = Depends(get_session),
) -> HarnessResponse:
    """Get a single harness."""
    harness = await HarnessService(session).get_harness(harness_name)
    if harness is None:
        raise HTTPException(status_code=404, detail="Harness not found")
    return HarnessResponse(
        id=harness.id,
        name=harness.name,
        display_name=harness.display_name,
        version=harness.version,
    )


@router.post("/api/harnesses/discover", response_model=list[HarnessConfigResponse])
async def discover_harnesses(
    _api_key: APIKey,
    project_id: int | None = None,
    session: AsyncSession = Depends(get_session),
) -> list[HarnessConfigResponse]:
    """Discover configs for all harnesses."""
    configs = await HarnessService(session).discover(project_id=project_id)
    return await _configs_to_response(session, configs)


@router.get("/api/harnesses/{harness_name}/configs", response_model=list[HarnessConfigResponse])
async def list_harness_configs(
    harness_name: str,
    _api_key: APIKey,
    project_id: int | None = None,
    session: AsyncSession = Depends(get_session),
) -> list[HarnessConfigResponse]:
    """List configs for a specific harness."""
    harness = await HarnessService(session).get_harness(harness_name)
    if harness is None:
        raise HTTPException(status_code=404, detail="Harness not found")

    configs = await HarnessService(session).list_configs(
        harness_name=harness_name, project_id=project_id
    )
    return await _configs_to_response(session, configs)
