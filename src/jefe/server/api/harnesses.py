"""Harness discovery API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from jefe.adapters import DiscoveredConfig, get_adapter, get_adapters
from jefe.data.database import get_session
from jefe.server.auth import APIKey
from jefe.server.schemas.harnesses import HarnessConfigResponse, HarnessInfo
from jefe.server.services.discovery import discover_all, discover_for_harness

router = APIRouter()


def _configs_to_response(configs: list[DiscoveredConfig]) -> list[HarnessConfigResponse]:
    return [
        HarnessConfigResponse(
            harness=config.harness,
            scope=config.scope,
            kind=config.kind,
            path=str(config.path),
            content=config.content,
            project_id=config.project_id,
            project_name=config.project_name,
        )
        for config in configs
    ]


@router.get("/api/harnesses", response_model=list[HarnessInfo])
async def list_harnesses(_api_key: APIKey) -> list[HarnessInfo]:
    """List available harness adapters."""
    return [
        HarnessInfo(name=adapter.name, display_name=adapter.display_name, version=adapter.version)
        for adapter in get_adapters()
    ]


@router.post("/api/harnesses/discover", response_model=list[HarnessConfigResponse])
async def discover_harnesses(
    _api_key: APIKey, session: AsyncSession = Depends(get_session)
) -> list[HarnessConfigResponse]:
    """Discover configs for all harnesses."""
    configs = await discover_all(session)
    return _configs_to_response(configs)


@router.get("/api/harnesses/{harness_name}/configs", response_model=list[HarnessConfigResponse])
async def list_harness_configs(
    harness_name: str,
    _api_key: APIKey,
    project_id: int | None = None,
    session: AsyncSession = Depends(get_session),
) -> list[HarnessConfigResponse]:
    """List configs for a specific harness."""
    adapter = get_adapter(harness_name)
    if adapter is None:
        raise HTTPException(status_code=404, detail="Harness not found")

    configs = await discover_for_harness(session, harness_name, project_id=project_id)
    return _configs_to_response(configs)
