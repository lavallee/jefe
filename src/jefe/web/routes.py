"""Web routes for the Jefe web interface."""

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from jefe.data.database import get_session
from jefe.data.models.harness_config import HarnessConfig
from jefe.data.models.installed_skill import InstalledSkill
from jefe.data.models.manifestation import ManifestationType
from jefe.data.models.project import Project
from jefe.data.models.skill_source import SkillSource, SyncStatus
from jefe.data.repositories.manifestation import ManifestationRepository
from jefe.data.repositories.project import ProjectRepository

# Get the directory of the current file
CURRENT_DIR = Path(__file__).parent
TEMPLATES_DIR = CURRENT_DIR / "templates"

# Initialize Jinja2 templates
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Create web router
web_router = APIRouter(tags=["web"])


@web_router.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """
    Render the main dashboard page.

    Args:
        request: FastAPI request object
        session: Database session

    Returns:
        Rendered HTML response with dashboard statistics
    """
    # Fetch dashboard statistics
    projects_count = await session.scalar(select(func.count(Project.id)))
    total_skills = await session.scalar(select(func.count(InstalledSkill.id)))
    harness_configs_count = await session.scalar(select(func.count(HarnessConfig.id)))
    sources_count = await session.scalar(select(func.count(SkillSource.id)))
    synced_sources_count = await session.scalar(
        select(func.count(SkillSource.id)).where(SkillSource.sync_status == SyncStatus.SYNCED)
    )

    # Package stats for template
    stats = {
        "projects_count": projects_count or 0,
        "total_skills": total_skills or 0,
        "harness_configs_count": harness_configs_count or 0,
        "sources_count": sources_count or 0,
        "synced_sources_count": synced_sources_count or 0,
    }

    # Recent activities placeholder (to be implemented later)
    recent_activities: list[dict[str, str]] = []

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "stats": stats,
            "recent_activities": recent_activities,
        },
    )


@web_router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """
    Render the dashboard page (alternative route).

    Args:
        request: FastAPI request object
        session: Database session

    Returns:
        Rendered HTML response with dashboard statistics
    """
    return await index(request, session)


@web_router.get("/projects", response_class=HTMLResponse)
async def projects_list(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """
    Render the projects list page.

    Args:
        request: FastAPI request object
        session: Database session

    Returns:
        Rendered HTML response with projects list
    """
    # Fetch all projects with their manifestations
    result = await session.execute(
        select(Project)
        .options(selectinload(Project.manifestations))
        .order_by(Project.name)
    )
    projects_data = result.scalars().all()

    # Calculate last_seen for each project (most recent manifestation)
    projects_with_last_seen = []
    for project in projects_data:
        last_seen = None
        if project.manifestations:
            manifestation_times = [
                m.last_seen for m in project.manifestations if m.last_seen is not None
            ]
            if manifestation_times:
                last_seen = max(manifestation_times)

        # Create a dict with the project and its computed last_seen
        projects_with_last_seen.append(
            {
                "id": project.id,
                "name": project.name,
                "description": project.description,
                "manifestations": project.manifestations,
                "last_seen": last_seen,
            }
        )

    return templates.TemplateResponse(
        "projects/list.html",
        {
            "request": request,
            "projects": projects_with_last_seen,
        },
    )


@web_router.get("/projects/new", response_class=HTMLResponse)
async def projects_new(request: Request) -> HTMLResponse:
    """
    Render the new project form.

    Args:
        request: FastAPI request object

    Returns:
        Rendered HTML response with project form
    """
    return templates.TemplateResponse(
        "projects/_form.html",
        {"request": request, "project": None},
    )


@web_router.post("/projects")
async def projects_create(
    name: str = Form(...),
    description: str | None = Form(None),
    path: str | None = Form(None),
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    """
    Create a new project.

    Args:
        name: Project name
        description: Optional project description
        path: Optional initial path for first manifestation
        session: Database session

    Returns:
        Redirect to projects list
    """
    project_repo = ProjectRepository(session)

    # Create the project
    project = await project_repo.create(name=name, description=description)

    # If path provided, create initial manifestation
    if path:
        manifestation_repo = ManifestationRepository(session)
        # Determine type based on path
        manifestation_type = ManifestationType.REMOTE if path.startswith(("http://", "https://")) else ManifestationType.LOCAL

        await manifestation_repo.create(
            project_id=project.id,
            type=manifestation_type,
            path=path,
            last_seen=datetime.now(),
        )

    await session.commit()

    # Return redirect response with HX-Redirect header for htmx
    response = RedirectResponse(url="/projects", status_code=303)
    response.headers["HX-Redirect"] = "/projects"
    return response


@web_router.get("/projects/{project_id}", response_class=HTMLResponse)
async def projects_detail(
    request: Request,
    project_id: int,
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """
    Render the project detail page.

    Args:
        request: FastAPI request object
        project_id: Project ID
        session: Database session

    Returns:
        Rendered HTML response with project details
    """
    project_repo = ProjectRepository(session)

    # Fetch project with manifestations
    project = await project_repo.get_with_manifestations(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Fetch associated harness configs
    result = await session.execute(
        select(HarnessConfig)
        .where(HarnessConfig.project_id == project_id)
        .order_by(HarnessConfig.harness_id)
    )
    configs = result.scalars().all()

    return templates.TemplateResponse(
        "projects/detail.html",
        {
            "request": request,
            "project": project,
            "configs": configs,
        },
    )


@web_router.get("/projects/{project_id}/edit", response_class=HTMLResponse)
async def projects_edit(
    request: Request,
    project_id: int,
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """
    Render the edit project form.

    Args:
        request: FastAPI request object
        project_id: Project ID
        session: Database session

    Returns:
        Rendered HTML response with project form
    """
    project_repo = ProjectRepository(session)
    project = await project_repo.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return templates.TemplateResponse(
        "projects/_form.html",
        {"request": request, "project": project},
    )


@web_router.put("/projects/{project_id}")
async def projects_update(
    project_id: int,
    name: str = Form(...),
    description: str | None = Form(None),
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    """
    Update a project.

    Args:
        project_id: Project ID
        name: Project name
        description: Optional project description
        session: Database session

    Returns:
        Redirect to project detail
    """
    project_repo = ProjectRepository(session)

    project = await project_repo.update(project_id, name=name, description=description)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    await session.commit()

    # Return redirect response with HX-Redirect header for htmx
    response = RedirectResponse(url=f"/projects/{project_id}", status_code=303)
    response.headers["HX-Redirect"] = f"/projects/{project_id}"
    return response


@web_router.delete("/projects/{project_id}")
async def projects_delete(
    project_id: int,
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    """
    Delete a project.

    Args:
        project_id: Project ID
        session: Database session

    Returns:
        Redirect to projects list
    """
    project_repo = ProjectRepository(session)

    success = await project_repo.delete(project_id)
    if not success:
        raise HTTPException(status_code=404, detail="Project not found")

    await session.commit()

    # Return redirect response with HX-Redirect header for htmx
    response = RedirectResponse(url="/projects", status_code=303)
    response.headers["HX-Redirect"] = "/projects"
    return response


@web_router.get("/projects/{project_id}/manifestations/new", response_class=HTMLResponse)
async def manifestations_new(
    request: Request,
    project_id: int,
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """
    Render the new manifestation form.

    Args:
        request: FastAPI request object
        project_id: Project ID
        session: Database session

    Returns:
        Rendered HTML response with manifestation form
    """
    # Verify project exists
    project_repo = ProjectRepository(session)
    project = await project_repo.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return templates.TemplateResponse(
        "projects/_manifestation_form.html",
        {"request": request, "project_id": project_id},
    )


@web_router.post("/projects/{project_id}/manifestations")
async def manifestations_create(
    project_id: int,
    type: str = Form(...),
    path: str = Form(...),
    machine_id: str | None = Form(None),
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    """
    Create a new manifestation.

    Args:
        project_id: Project ID
        type: Manifestation type (local or remote)
        path: Filesystem path or remote URL
        machine_id: Optional machine identifier
        session: Database session

    Returns:
        Redirect to project detail
    """
    # Verify project exists
    project_repo = ProjectRepository(session)
    project = await project_repo.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Create manifestation
    manifestation_repo = ManifestationRepository(session)
    manifestation_type = ManifestationType(type)

    await manifestation_repo.create(
        project_id=project_id,
        type=manifestation_type,
        path=path,
        machine_id=machine_id,
        last_seen=datetime.now(),
    )

    await session.commit()

    # Return redirect response with HX-Redirect header for htmx
    response = RedirectResponse(url=f"/projects/{project_id}", status_code=303)
    response.headers["HX-Redirect"] = f"/projects/{project_id}"
    return response


@web_router.delete("/projects/{project_id}/manifestations/{manifestation_id}")
async def manifestations_delete(
    project_id: int,
    manifestation_id: int,
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """
    Delete a manifestation.

    Args:
        project_id: Project ID
        manifestation_id: Manifestation ID
        session: Database session

    Returns:
        Empty HTML response (htmx will remove the element)
    """
    manifestation_repo = ManifestationRepository(session)

    # Verify manifestation exists and belongs to project
    manifestation = await manifestation_repo.get_by_id(manifestation_id)
    if not manifestation or manifestation.project_id != project_id:
        raise HTTPException(status_code=404, detail="Manifestation not found")

    success = await manifestation_repo.delete(manifestation_id)
    if not success:
        raise HTTPException(status_code=404, detail="Manifestation not found")

    await session.commit()

    # Return empty response for htmx to remove the element
    return HTMLResponse(content="", status_code=200)


@web_router.get("/skills", response_class=HTMLResponse)
async def skills(request: Request) -> HTMLResponse:
    """
    Render the skills page.

    Args:
        request: FastAPI request object

    Returns:
        Rendered HTML response (placeholder for now)
    """
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "messages": [{"type": "info", "text": "Skills page coming soon!"}]},
    )


@web_router.get("/sources", response_class=HTMLResponse)
async def sources(request: Request) -> HTMLResponse:
    """
    Render the sources page.

    Args:
        request: FastAPI request object

    Returns:
        Rendered HTML response (placeholder for now)
    """
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "messages": [{"type": "info", "text": "Sources page coming soon!"}]},
    )
