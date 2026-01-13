"""Repository for Project model."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from jefe.data.models.project import Project
from jefe.data.repositories.base import BaseRepository


class ProjectRepository(BaseRepository[Project]):
    """Repository for Project model."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Project, session)

    async def create(self, **kwargs: Any) -> Project:
        """Create a new project."""
        return await super().create(**kwargs)

    async def get_by_id(self, id_: int) -> Project | None:
        """Fetch a project by its ID."""
        return await super().get_by_id(id_)

    async def list_all(self, limit: int | None = None, offset: int = 0) -> list[Project]:
        """List projects with optional pagination."""
        return await self.get_all(limit=limit, offset=offset)

    async def update(self, id_: int, **kwargs: Any) -> Project | None:
        """Update a project by ID."""
        return await super().update(id_, **kwargs)

    async def delete(self, id_: int) -> bool:
        """Delete a project by ID."""
        return await super().delete(id_)

    async def get_with_manifestations(self, project_id: int) -> Project | None:
        """Fetch a project with its manifestations pre-loaded."""
        result = await self.session.execute(
            select(Project)
            .options(selectinload(Project.manifestations))
            .where(Project.id == project_id)
        )
        return result.scalar_one_or_none()
