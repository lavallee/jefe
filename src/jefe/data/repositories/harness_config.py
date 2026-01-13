"""Repository for HarnessConfig model."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from jefe.data.models.harness_config import ConfigScope, HarnessConfig
from jefe.data.repositories.base import BaseRepository


class HarnessConfigRepository(BaseRepository[HarnessConfig]):
    """Repository for HarnessConfig model."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(HarnessConfig, session)

    async def create(self, **kwargs: Any) -> HarnessConfig:
        """Create a new harness config."""
        return await super().create(**kwargs)

    async def get_by_id(self, id_: int) -> HarnessConfig | None:
        """Fetch a harness config by ID."""
        return await super().get_by_id(id_)

    async def get_by_identity(
        self,
        harness_id: int,
        scope: ConfigScope,
        kind: str,
        path: str,
        project_id: int | None,
    ) -> HarnessConfig | None:
        """Fetch a config by its identity fields."""
        query = select(HarnessConfig).where(
            HarnessConfig.harness_id == harness_id,
            HarnessConfig.scope == scope,
            HarnessConfig.kind == kind,
            HarnessConfig.path == path,
        )
        if project_id is None:
            query = query.where(HarnessConfig.project_id.is_(None))
        else:
            query = query.where(HarnessConfig.project_id == project_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_for_harness(
        self,
        harness_id: int,
        project_id: int | None = None,
    ) -> list[HarnessConfig]:
        """List configs for a harness, optionally filtered by project."""
        query = (
            select(HarnessConfig)
            .where(HarnessConfig.harness_id == harness_id)
            .options(selectinload(HarnessConfig.project))
        )
        if project_id is not None:
            query = query.where(
                (HarnessConfig.project_id == project_id) | HarnessConfig.project_id.is_(None)
            )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def list_all(
        self,
        harness_id: int | None = None,
        project_id: int | None = None,
        include_global: bool = True,
    ) -> list[HarnessConfig]:
        """List configs with optional filters."""
        query = select(HarnessConfig).options(selectinload(HarnessConfig.project))
        if harness_id is not None:
            query = query.where(HarnessConfig.harness_id == harness_id)
        if project_id is not None:
            if include_global:
                query = query.where(
                    (HarnessConfig.project_id == project_id) | HarnessConfig.project_id.is_(None)
                )
            else:
                query = query.where(HarnessConfig.project_id == project_id)
        result = await self.session.execute(query)
        return list(result.scalars().all())
