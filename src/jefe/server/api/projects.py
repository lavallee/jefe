"""Project API endpoints."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from jefe.adapters import DiscoveredConfig
from jefe.data.database import get_session
from jefe.data.models.manifestation import Manifestation, ManifestationType
from jefe.data.models.project import Project
from jefe.server.auth import APIKey
from jefe.server.schemas.harnesses import HarnessConfigResponse
from jefe.server.schemas.projects import (
    ManifestationCreate,
    ManifestationResponse,
    ProjectCreate,
    ProjectDetailResponse,
    ProjectResponse,
)
from jefe.server.services.discovery import discover_for_project

router = APIRouter()


def _manifestation_to_response(manifestation: Manifestation) -> ManifestationResponse:
    return ManifestationResponse(
        id=manifestation.id,
        type=manifestation.type,
        path=manifestation.path,
        machine_id=manifestation.machine_id,
        last_seen=manifestation.last_seen,
    )


def _project_to_response(project: Project) -> ProjectResponse:
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        manifestations=[_manifestation_to_response(m) for m in project.manifestations],
    )


def _configs_to_response(configs: list[DiscoveredConfig]) -> list[HarnessConfigResponse]:
    return [
        HarnessConfigResponse(
            harness=config.harness,
            scope=config.scope,
            kind=config.kind,
            path=str(config.path),
            content=config.content,
            project_id=config.project_id,
            project_name=config.project_name,
        )
        for config in configs
    ]


@router.get("/api/projects", response_model=list[ProjectResponse])
async def list_projects(
    _api_key: APIKey, session: AsyncSession = Depends(get_session)
) -> list[ProjectResponse]:
    """List all registered projects."""
    result = await session.execute(
        select(Project).options(selectinload(Project.manifestations))
    )
    projects = list(result.scalars().all())
    return [_project_to_response(project) for project in projects]


@router.post("/api/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate,
    _api_key: APIKey,
    session: AsyncSession = Depends(get_session),
) -> ProjectResponse:
    """Create a new project, optionally with a local manifestation."""
    existing = await session.execute(select(Project).where(Project.name == payload.name))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=400, detail="Project name already exists")

    project_path: Path | None = None
    if payload.path:
        project_path = Path(payload.path).expanduser()
        if not project_path.exists():
            raise HTTPException(status_code=400, detail="Project path does not exist")

    project = Project(name=payload.name, description=payload.description)
    session.add(project)
    await session.flush()

    if project_path is not None:
        manifestation = Manifestation(
            project_id=project.id,
            type=ManifestationType.LOCAL,
            path=str(project_path.resolve()),
        )
        session.add(manifestation)

    await session.commit()

    result = await session.execute(
        select(Project)
        .where(Project.id == project.id)
        .options(selectinload(Project.manifestations))
    )
    project = result.scalar_one()
    return _project_to_response(project)


@router.get("/api/projects/{project_id}", response_model=ProjectDetailResponse)
async def get_project(
    project_id: int,
    _api_key: APIKey,
    session: AsyncSession = Depends(get_session),
) -> ProjectDetailResponse:
    """Get a project with manifestations and discovered configs."""
    result = await session.execute(
        select(Project)
        .where(Project.id == project_id)
        .options(selectinload(Project.manifestations))
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    configs = await discover_for_project(session, project_id=project.id)
    return ProjectDetailResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        manifestations=[_manifestation_to_response(m) for m in project.manifestations],
        configs=_configs_to_response(configs),
    )


@router.post(
    "/api/projects/{project_id}/manifestations",
    response_model=ManifestationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_manifestation(
    project_id: int,
    payload: ManifestationCreate,
    _api_key: APIKey,
    session: AsyncSession = Depends(get_session),
) -> ManifestationResponse:
    """Add a manifestation to a project."""
    result = await session.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    if payload.type == ManifestationType.LOCAL:
        path = Path(payload.path).expanduser()
        if not path.exists():
            raise HTTPException(status_code=400, detail="Manifestation path does not exist")
        path_value = str(path.resolve())
    else:
        path_value = payload.path

    manifestation = Manifestation(
        project_id=project.id,
        type=payload.type,
        path=path_value,
        machine_id=payload.machine_id,
    )
    session.add(manifestation)
    await session.commit()
    await session.refresh(manifestation)
    return _manifestation_to_response(manifestation)


@router.delete(
    "/api/projects/{project_id}/manifestations/{manifestation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_manifestation(
    project_id: int,
    manifestation_id: int,
    _api_key: APIKey,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Delete a manifestation from a project."""
    result = await session.execute(
        select(Manifestation).where(
            Manifestation.id == manifestation_id,
            Manifestation.project_id == project_id,
        )
    )
    manifestation = result.scalar_one_or_none()
    if manifestation is None:
        raise HTTPException(status_code=404, detail="Manifestation not found")

    await session.delete(manifestation)
    await session.commit()
