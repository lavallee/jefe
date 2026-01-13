"""Web routes for the Jefe web interface."""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

# Get the directory of the current file
CURRENT_DIR = Path(__file__).parent
TEMPLATES_DIR = CURRENT_DIR / "templates"

# Initialize Jinja2 templates
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Create web router
web_router = APIRouter(tags=["web"])


@web_router.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    """
    Render the main dashboard page.

    Args:
        request: FastAPI request object

    Returns:
        Rendered HTML response
    """
    return templates.TemplateResponse(
        "index.html",
        {"request": request},
    )


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
