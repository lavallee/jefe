"""Harness discovery service."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from jefe.adapters import DiscoveredConfig, get_adapter, get_adapters
from jefe.data.models.manifestation import ManifestationType
from jefe.data.models.project import Project


async def discover_all(session: AsyncSession) -> list[DiscoveredConfig]:
    """Discover configs for all harnesses across all projects."""
    results: list[DiscoveredConfig] = []

    for adapter in get_adapters():
        results.extend(adapter.discover_global())

    projects = await _load_projects(session)
    for project in projects:
        for manifestation in project.manifestations:
            if manifestation.type != ManifestationType.LOCAL:
                continue
            project_path = Path(manifestation.path)
            for adapter in get_adapters():
                results.extend(
                    adapter.discover_project(
                        project_path,
                        project_id=project.id,
                        project_name=project.name,
                    )
                )

    return results


async def discover_for_harness(
    session: AsyncSession, harness_name: str, project_id: int | None = None
) -> list[DiscoveredConfig]:
    """Discover configs for a specific harness."""
    adapter = get_adapter(harness_name)
    if adapter is None:
        return []

    results: list[DiscoveredConfig] = []
    results.extend(adapter.discover_global())

    projects = await _load_projects(session, project_id=project_id)
    for project in projects:
        for manifestation in project.manifestations:
            if manifestation.type != ManifestationType.LOCAL:
                continue
            project_path = Path(manifestation.path)
            results.extend(
                adapter.discover_project(
                    project_path,
                    project_id=project.id,
                    project_name=project.name,
                )
            )

    return results


async def discover_for_project(session: AsyncSession, project_id: int) -> list[DiscoveredConfig]:
    """Discover configs for all harnesses within a single project."""
    results: list[DiscoveredConfig] = []

    projects = await _load_projects(session, project_id=project_id)
    for project in projects:
        for manifestation in project.manifestations:
            if manifestation.type != ManifestationType.LOCAL:
                continue
            project_path = Path(manifestation.path)
            for adapter in get_adapters():
                results.extend(
                    adapter.discover_project(
                        project_path,
                        project_id=project.id,
                        project_name=project.name,
                    )
                )

    return results


async def _load_projects(session: AsyncSession, project_id: int | None = None) -> list[Project]:
    query = select(Project).options(selectinload(Project.manifestations))
    if project_id is not None:
        query = query.where(Project.id == project_id)
    result = await session.execute(query)
    return list(result.scalars().all())
