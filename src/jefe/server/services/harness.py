"""Harness persistence and discovery service."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from jefe.adapters import DiscoveredConfig, get_adapter, get_adapters
from jefe.adapters.base import HarnessAdapter
from jefe.data.models.harness import Harness
from jefe.data.models.harness_config import HarnessConfig
from jefe.data.models.manifestation import ManifestationType
from jefe.data.models.project import Project
from jefe.data.repositories.harness import HarnessRepository
from jefe.data.repositories.harness_config import HarnessConfigRepository


class HarnessService:
    """Service for harness persistence and config discovery."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.harness_repo = HarnessRepository(session)
        self.config_repo = HarnessConfigRepository(session)

    async def seed_harnesses(self) -> None:
        """Ensure all registered adapters are present in the harness table."""
        for adapter in get_adapters():
            await self._ensure_harness(adapter.name, adapter.display_name, adapter.version)

    async def list_harnesses(self) -> list[Harness]:
        """List all harnesses."""
        return await self.harness_repo.list_all()

    async def get_harness(self, name: str) -> Harness | None:
        """Fetch a harness by name."""
        return await self.harness_repo.get_by_name(name)

    async def list_configs(
        self,
        harness_name: str | None = None,
        project_id: int | None = None,
        include_global: bool = True,
    ) -> list[HarnessConfig]:
        """List stored harness configs with optional filters."""
        harness_id: int | None = None
        if harness_name is not None:
            harness = await self.harness_repo.get_by_name(harness_name)
            if harness is None:
                return []
            harness_id = harness.id

        return await self.config_repo.list_all(
            harness_id=harness_id,
            project_id=project_id,
            include_global=include_global,
        )

    async def discover(
        self,
        harness_name: str | None = None,
        project_id: int | None = None,
    ) -> list[HarnessConfig]:
        """Discover configs via adapters and persist updates."""
        adapters = self._select_adapters(harness_name)
        if not adapters:
            return []

        await self.seed_harnesses()

        configs: list[HarnessConfig] = []
        global_configs = self._discover_global(adapters)
        configs.extend(await self._store_configs(global_configs))

        project_configs = await self._discover_project_configs(adapters, project_id=project_id)
        configs.extend(await self._store_configs(project_configs))

        return configs

    async def _ensure_harness(self, name: str, display_name: str, version: str) -> Harness:
        harness = await self.harness_repo.get_by_name(name)
        if harness is None:
            return await self.harness_repo.create(
                name=name,
                display_name=display_name,
                version=version,
            )

        updates: dict[str, str] = {}
        if harness.display_name != display_name:
            updates["display_name"] = display_name
        if harness.version != version:
            updates["version"] = version

        if updates:
            harness = await self.harness_repo.update(harness.id, **updates) or harness
        return harness

    def _select_adapters(self, harness_name: str | None) -> list[HarnessAdapter]:
        if harness_name is None:
            return list(get_adapters())

        adapter = get_adapter(harness_name)
        if adapter is None:
            return []
        return [adapter]

    def _discover_global(self, adapters: Iterable[HarnessAdapter]) -> list[DiscoveredConfig]:
        results: list[DiscoveredConfig] = []
        for adapter in adapters:
            results.extend(adapter.discover_global())
        return results

    async def _discover_project_configs(
        self,
        adapters: Iterable[HarnessAdapter],
        project_id: int | None = None,
    ) -> list[DiscoveredConfig]:
        results: list[DiscoveredConfig] = []
        projects = await self._load_projects(project_id=project_id)
        for project in projects:
            for manifestation in project.manifestations:
                if manifestation.type != ManifestationType.LOCAL:
                    continue
                project_path = Path(manifestation.path)
                for adapter in adapters:
                    results.extend(
                        adapter.discover_project(
                            project_path,
                            project_id=project.id,
                            project_name=project.name,
                        )
                    )
        return results

    async def _load_projects(self, project_id: int | None = None) -> list[Project]:
        query = select(Project).options(selectinload(Project.manifestations))
        if project_id is not None:
            query = query.where(Project.id == project_id)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def _store_configs(self, configs: list[DiscoveredConfig]) -> list[HarnessConfig]:
        stored: list[HarnessConfig] = []
        for config in configs:
            harness = await self.harness_repo.get_by_name(config.harness)
            if harness is None:
                continue
            raw_content = _extract_raw_content(config)
            content_hash = _hash_content(raw_content)
            existing = await self.config_repo.get_by_identity(
                harness_id=harness.id,
                scope=config.scope,
                kind=config.kind,
                path=str(config.path),
                project_id=config.project_id,
            )
            if existing is None:
                stored.append(
                    await self.config_repo.create(
                        harness_id=harness.id,
                        scope=config.scope,
                        kind=config.kind,
                        path=str(config.path),
                        content=raw_content,
                        content_hash=content_hash,
                        project_id=config.project_id,
                    )
                )
                continue

            if existing.content_hash != content_hash:
                existing.content = raw_content
                existing.content_hash = content_hash
                await self.session.commit()
                await self.session.refresh(existing)

            stored.append(existing)

        return stored


def _extract_raw_content(config: DiscoveredConfig) -> str | None:
    path = config.path
    if path.exists() and path.is_file():
        return path.read_text()

    if isinstance(config.content, str):
        return config.content

    if isinstance(config.content, dict):
        return json.dumps(config.content, sort_keys=True)

    return None


def _hash_content(content: str | None) -> str | None:
    if content is None:
        return None
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
