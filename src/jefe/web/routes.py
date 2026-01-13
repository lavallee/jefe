"""Web routes for the Jefe web interface."""

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from jefe.data.database import get_session
from jefe.data.models.harness_config import HarnessConfig
from jefe.data.models.installed_skill import InstalledSkill
from jefe.data.models.project import Project
from jefe.data.models.skill_source import SkillSource, SyncStatus

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
async def projects(request: Request) -> HTMLResponse:
    """
    Render the projects page.

    Args:
        request: FastAPI request object

    Returns:
        Rendered HTML response (placeholder for now)
    """
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "messages": [{"type": "info", "text": "Projects page coming soon!"}]},
    )


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
