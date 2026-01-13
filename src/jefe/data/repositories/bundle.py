"""Repository for Bundle model."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jefe.data.models.bundle import Bundle
from jefe.data.repositories.base import BaseRepository


class BundleRepository(BaseRepository[Bundle]):
    """Repository for Bundle model."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Bundle, session)

    async def get_by_id(self, id_: int) -> Bundle | None:
        """Fetch a bundle by ID."""
        return await super().get_by_id(id_)

    async def get_by_name(self, name: str) -> Bundle | None:
        """Fetch a bundle by name."""
        result = await self.session.execute(select(Bundle).where(Bundle.name == name))
        return result.scalar_one_or_none()

    async def list_all(self) -> list[Bundle]:
        """List all bundles."""
        result = await self.session.execute(select(Bundle))
        return list(result.scalars().all())
