"""Repository for Harness model."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jefe.data.models.harness import Harness
from jefe.data.repositories.base import BaseRepository


class HarnessRepository(BaseRepository[Harness]):
    """Repository for Harness model."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Harness, session)

    async def create(self, **kwargs: Any) -> Harness:
        """Create a new harness."""
        return await super().create(**kwargs)

    async def get_by_id(self, id_: int) -> Harness | None:
        """Fetch a harness by ID."""
        return await super().get_by_id(id_)

    async def get_by_name(self, name: str) -> Harness | None:
        """Fetch a harness by name."""
        result = await self.session.execute(select(Harness).where(Harness.name == name))
        return result.scalar_one_or_none()

    async def list_all(self, limit: int | None = None, offset: int = 0) -> list[Harness]:
        """List harnesses with optional pagination."""
        return await self.get_all(limit=limit, offset=offset)

    async def update(self, id_: int, **kwargs: Any) -> Harness | None:
        """Update a harness by ID."""
        return await super().update(id_, **kwargs)

    async def delete(self, id_: int) -> bool:
        """Delete a harness by ID."""
        return await super().delete(id_)
