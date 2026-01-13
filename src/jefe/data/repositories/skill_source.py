"""Repository for SkillSource model."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from jefe.data.models.skill_source import SkillSource, SourceType, SyncStatus
from jefe.data.repositories.base import BaseRepository


class SkillSourceRepository(BaseRepository[SkillSource]):
    """Repository for SkillSource model."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(SkillSource, session)

    async def create(self, **kwargs: Any) -> SkillSource:
        """Create a new skill source."""
        return await super().create(**kwargs)

    async def get_by_id(self, id_: int) -> SkillSource | None:
        """Fetch a skill source by ID."""
        return await super().get_by_id(id_)

    async def get_by_name(self, name: str) -> SkillSource | None:
        """Fetch a skill source by name."""
        result = await self.session.execute(select(SkillSource).where(SkillSource.name == name))
        return result.scalar_one_or_none()

    async def list_by_type(self, source_type: SourceType) -> list[SkillSource]:
        """List all skill sources of a specific type."""
        result = await self.session.execute(
            select(SkillSource).where(SkillSource.source_type == source_type)
        )
        return list(result.scalars().all())

    async def list_by_status(self, sync_status: SyncStatus) -> list[SkillSource]:
        """List all skill sources with a specific sync status."""
        result = await self.session.execute(
            select(SkillSource).where(SkillSource.sync_status == sync_status)
        )
        return list(result.scalars().all())

    async def get_with_skills(self, id_: int) -> SkillSource | None:
        """Fetch a skill source by ID with skills eagerly loaded."""
        result = await self.session.execute(
            select(SkillSource)
            .where(SkillSource.id == id_)
            .options(selectinload(SkillSource.skills))
        )
        return result.scalar_one_or_none()

    async def list_all(
        self,
        source_type: SourceType | None = None,
        sync_status: SyncStatus | None = None,
    ) -> list[SkillSource]:
        """List all skill sources with optional filters."""
        query = select(SkillSource)
        if source_type is not None:
            query = query.where(SkillSource.source_type == source_type)
        if sync_status is not None:
            query = query.where(SkillSource.sync_status == sync_status)
        result = await self.session.execute(query)
        return list(result.scalars().all())
