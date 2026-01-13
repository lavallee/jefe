"""Repository for TranslationLog model."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jefe.data.models.translation_log import TranslationLog, TranslationType
from jefe.data.repositories.base import BaseRepository


class TranslationLogRepository(BaseRepository[TranslationLog]):
    """Repository for TranslationLog model."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(TranslationLog, session)

    async def create(self, **kwargs: Any) -> TranslationLog:
        """Create a new translation log."""
        return await super().create(**kwargs)

    async def get_by_id(self, id_: int) -> TranslationLog | None:
        """Fetch a translation log by ID."""
        return await super().get_by_id(id_)

    async def list_all(
        self,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[TranslationLog]:
        """List translation logs with optional pagination."""
        return await self.get_all(limit=limit, offset=offset)

    async def list_by_type(
        self,
        translation_type: TranslationType,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[TranslationLog]:
        """List translation logs filtered by translation type."""
        query = select(TranslationLog).where(
            TranslationLog.translation_type == translation_type
        )
        if limit:
            query = query.limit(limit)
        if offset:
            query = query.offset(offset)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def list_by_project(
        self,
        project_id: int,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[TranslationLog]:
        """List translation logs filtered by project ID."""
        query = select(TranslationLog).where(
            TranslationLog.project_id == project_id
        )
        if limit:
            query = query.limit(limit)
        if offset:
            query = query.offset(offset)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update(self, id_: int, **kwargs: Any) -> TranslationLog | None:
        """Update a translation log by ID."""
        return await super().update(id_, **kwargs)

    async def delete(self, id_: int) -> bool:
        """Delete a translation log by ID."""
        return await super().delete(id_)
