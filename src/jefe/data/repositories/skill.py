"""Repository for Skill model."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from jefe.data.models.skill import Skill
from jefe.data.repositories.base import BaseRepository


class SkillRepository(BaseRepository[Skill]):
    """Repository for Skill model."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Skill, session)

    async def create(self, **kwargs: Any) -> Skill:
        """Create a new skill."""
        return await super().create(**kwargs)

    async def get_by_id(self, id_: int) -> Skill | None:
        """Fetch a skill by ID."""
        return await super().get_by_id(id_)

    async def get_by_name(self, name: str) -> Skill | None:
        """Fetch a skill by name (returns first match if multiple exist)."""
        result = await self.session.execute(select(Skill).where(Skill.name == name))
        return result.scalar_one_or_none()

    async def list_by_source(self, source_id: int) -> list[Skill]:
        """List all skills from a specific source."""
        result = await self.session.execute(
            select(Skill)
            .where(Skill.source_id == source_id)
            .options(selectinload(Skill.source))
        )
        return list(result.scalars().all())

    async def list_by_name(self, name: str) -> list[Skill]:
        """List all skills matching a specific name."""
        result = await self.session.execute(
            select(Skill).where(Skill.name == name).options(selectinload(Skill.source))
        )
        return list(result.scalars().all())

    async def search_by_tag(self, tag: str) -> list[Skill]:
        """Search skills by tag (searches within JSON tags field)."""
        # SQLite JSON support is limited, so we use LIKE for substring search
        result = await self.session.execute(
            select(Skill)
            .where(Skill.tags.like(f'%"{tag}"%'))
            .options(selectinload(Skill.source))
        )
        return list(result.scalars().all())

    async def list_by_author(self, author: str) -> list[Skill]:
        """List all skills by a specific author."""
        result = await self.session.execute(
            select(Skill).where(Skill.author == author).options(selectinload(Skill.source))
        )
        return list(result.scalars().all())

    async def get_with_source(self, id_: int) -> Skill | None:
        """Fetch a skill by ID with source eagerly loaded."""
        result = await self.session.execute(
            select(Skill).where(Skill.id == id_).options(selectinload(Skill.source))
        )
        return result.scalar_one_or_none()

    async def list_all(
        self,
        source_id: int | None = None,
        author: str | None = None,
    ) -> list[Skill]:
        """List all skills with optional filters."""
        query = select(Skill).options(selectinload(Skill.source))
        if source_id is not None:
            query = query.where(Skill.source_id == source_id)
        if author is not None:
            query = query.where(Skill.author == author)
        result = await self.session.execute(query)
        return list(result.scalars().all())
