"""Sync API endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from jefe.data.database import get_session
from jefe.server.auth import APIKey
from jefe.server.schemas.sync import (
    SyncPullRequest,
    SyncPullResponse,
    SyncPushRequest,
    SyncPushResponse,
)
from jefe.server.services.sync import SyncService

router = APIRouter()


@router.post("/api/sync/push", response_model=SyncPushResponse)
async def sync_push(
    request: SyncPushRequest,
    _api_key: APIKey,
    session: AsyncSession = Depends(get_session),
) -> SyncPushResponse:
    """Push local changes to the server.

    Accepts dirty items from the client and applies them to the server
    using last-write-wins conflict resolution.
    """
    service = SyncService(session)
    return await service.push(request)


@router.post("/api/sync/pull", response_model=SyncPullResponse)
async def sync_pull(
    request: SyncPullRequest,
    _api_key: APIKey,
    session: AsyncSession = Depends(get_session),
) -> SyncPullResponse:
    """Pull server changes to the client.

    Returns all items changed since the provided timestamp,
    or all items if no timestamp is provided.
    """
    service = SyncService(session)
    return await service.pull(request)
