"""Repository for InstalledSkill model."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from jefe.data.models.installed_skill import InstalledSkill, InstallScope
from jefe.data.repositories.base import BaseRepository


class InstalledSkillRepository(BaseRepository[InstalledSkill]):
    """Repository for InstalledSkill model."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(InstalledSkill, session)

    async def install(self, **kwargs: Any) -> InstalledSkill:
        """Install a skill (create a new installation record)."""
        return await super().create(**kwargs)

    async def uninstall(self, id_: int) -> bool:
        """Uninstall a skill (delete the installation record)."""
        return await super().delete(id_)

    async def get_by_identity(
        self,
        skill_id: int,
        harness_id: int,
        scope: InstallScope,
        project_id: int | None,
    ) -> InstalledSkill | None:
        """Fetch an installation by its identity fields."""
        query = select(InstalledSkill).where(
            InstalledSkill.skill_id == skill_id,
            InstalledSkill.harness_id == harness_id,
            InstalledSkill.scope == scope,
        )
        if project_id is None:
            query = query.where(InstalledSkill.project_id.is_(None))
        else:
            query = query.where(InstalledSkill.project_id == project_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_project(
        self,
        project_id: int,
        harness_id: int | None = None,
        include_global: bool = True,
    ) -> list[InstalledSkill]:
        """Get all skills installed for a project."""
        query = select(InstalledSkill).options(
            selectinload(InstalledSkill.skill),
            selectinload(InstalledSkill.harness),
            selectinload(InstalledSkill.project),
        )
        if include_global:
            query = query.where(
                (InstalledSkill.project_id == project_id)
                | InstalledSkill.project_id.is_(None)
            )
        else:
            query = query.where(InstalledSkill.project_id == project_id)
        if harness_id is not None:
            query = query.where(InstalledSkill.harness_id == harness_id)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_by_harness(
        self,
        harness_id: int,
        project_id: int | None = None,
        include_global: bool = True,
    ) -> list[InstalledSkill]:
        """Get all skills installed for a harness."""
        query = (
            select(InstalledSkill)
            .where(InstalledSkill.harness_id == harness_id)
            .options(
                selectinload(InstalledSkill.skill),
                selectinload(InstalledSkill.harness),
                selectinload(InstalledSkill.project),
            )
        )
        if project_id is not None:
            if include_global:
                query = query.where(
                    (InstalledSkill.project_id == project_id)
                    | InstalledSkill.project_id.is_(None)
                )
            else:
                query = query.where(InstalledSkill.project_id == project_id)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_global_installs(
        self, harness_id: int | None = None
    ) -> list[InstalledSkill]:
        """Get all globally installed skills."""
        query = (
            select(InstalledSkill)
            .where(InstalledSkill.scope == InstallScope.GLOBAL)
            .options(
                selectinload(InstalledSkill.skill),
                selectinload(InstalledSkill.harness),
            )
        )
        if harness_id is not None:
            query = query.where(InstalledSkill.harness_id == harness_id)
        result = await self.session.execute(query)
        return list(result.scalars().all())
