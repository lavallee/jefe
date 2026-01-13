"""Repositories for project registry."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jefe.data.models.project import Manifestation, Project
from jefe.data.repositories.base import BaseRepository


class ProjectRepository(BaseRepository[Project]):
    """Repository for Project model."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Project, session)

    async def get_by_name(self, name: str) -> Project | None:
        """Fetch a project by its unique name."""
        result = await self.session.execute(select(Project).where(Project.name == name))
        return result.scalar_one_or_none()


class ManifestationRepository(BaseRepository[Manifestation]):
    """Repository for Manifestation model."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Manifestation, session)
