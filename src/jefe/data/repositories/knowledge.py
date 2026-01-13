"""Repository for KnowledgeEntry model."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jefe.data.models.knowledge import KnowledgeEntry
from jefe.data.repositories.base import BaseRepository


class KnowledgeRepository(BaseRepository[KnowledgeEntry]):
    """Repository for KnowledgeEntry model."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(KnowledgeEntry, session)

    async def create(self, **kwargs: Any) -> KnowledgeEntry:
        """Create a new knowledge entry."""
        return await super().create(**kwargs)

    async def get_by_id(self, id_: int) -> KnowledgeEntry | None:
        """Fetch a knowledge entry by ID."""
        return await super().get_by_id(id_)

    async def search(
        self,
        query: str | None = None,
        tags: list[str] | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[KnowledgeEntry]:
        """Search knowledge entries by text query and/or tags."""
        stmt = select(KnowledgeEntry)

        # Text search in title, summary, and content
        if query:
            search_pattern = f"%{query}%"
            stmt = stmt.where(
                (KnowledgeEntry.title.like(search_pattern))
                | (KnowledgeEntry.summary.like(search_pattern))
                | (KnowledgeEntry.content.like(search_pattern))
            )

        # Tag filtering (SQLite JSON support is limited, use LIKE)
        if tags:
            for tag in tags:
                stmt = stmt.where(KnowledgeEntry.tags.like(f'%"{tag}"%'))

        # Order by most recently ingested first
        stmt = stmt.order_by(KnowledgeEntry.created_at.desc())

        # Pagination
        if offset > 0:
            stmt = stmt.offset(offset)
        if limit is not None:
            stmt = stmt.limit(limit)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_url(self, source_url: str) -> KnowledgeEntry | None:
        """Fetch a knowledge entry by source URL."""
        result = await self.session.execute(
            select(KnowledgeEntry).where(KnowledgeEntry.source_url == source_url)
        )
        return result.scalar_one_or_none()

    async def list_by_tag(self, tag: str) -> list[KnowledgeEntry]:
        """List all knowledge entries with a specific tag."""
        result = await self.session.execute(
            select(KnowledgeEntry)
            .where(KnowledgeEntry.tags.like(f'%"{tag}"%'))
            .order_by(KnowledgeEntry.created_at.desc())
        )
        return list(result.scalars().all())
