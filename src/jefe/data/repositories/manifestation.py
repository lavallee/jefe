"""Repository for Manifestation model."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from jefe.data.models.manifestation import Manifestation
from jefe.data.repositories.base import BaseRepository


class ManifestationRepository(BaseRepository[Manifestation]):
    """Repository for Manifestation model."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Manifestation, session)

    async def create(self, **kwargs: Any) -> Manifestation:
        """Create a new manifestation."""
        return await super().create(**kwargs)

    async def get_by_id(self, id_: int) -> Manifestation | None:
        """Fetch a manifestation by ID."""
        return await super().get_by_id(id_)

    async def list_all(
        self,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Manifestation]:
        """List manifestations with optional pagination."""
        return await self.get_all(limit=limit, offset=offset)

    async def update(self, id_: int, **kwargs: Any) -> Manifestation | None:
        """Update a manifestation by ID."""
        return await super().update(id_, **kwargs)

    async def delete(self, id_: int) -> bool:
        """Delete a manifestation by ID."""
        return await super().delete(id_)
