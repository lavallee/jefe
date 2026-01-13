"""Web routes for the Jefe web interface."""

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from jefe.data.database import get_session
from jefe.data.models.harness_config import ConfigScope, HarnessConfig
from jefe.data.models.installed_skill import InstalledSkill, InstallScope
from jefe.data.models.manifestation import ManifestationType
from jefe.data.models.project import Project
from jefe.data.models.skill import Skill
from jefe.data.models.skill_source import SkillSource, SyncStatus
from jefe.data.repositories.harness import HarnessRepository
from jefe.data.repositories.harness_config import HarnessConfigRepository
from jefe.data.repositories.manifestation import ManifestationRepository
from jefe.data.repositories.project import ProjectRepository
from jefe.data.repositories.skill import SkillRepository
from jefe.data.repositories.skill_source import SkillSourceRepository
from jefe.server.auth import APIKey
from jefe.server.services.discovery import discover_all, discover_for_harness
from jefe.server.services.skill import SkillInstallError, SkillService
from jefe.server.services.translation.service import TranslationService
from jefe.server.services.translation.syntax import TranslationError

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
    _api_key: APIKey,
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
    _api_key: APIKey,
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
    _api_key: APIKey,
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
    _api_key: APIKey,
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
    _api_key: APIKey,
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
async def skills_browser(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """
    Render the skills browser page.

    Args:
        request: FastAPI request object
        session: Database session

    Returns:
        Rendered HTML response with skills browser
    """
    source_repo = SkillSourceRepository(session)

    # Fetch all skills with their sources
    result = await session.execute(
        select(Skill)
        .options(selectinload(Skill.source))
        .order_by(Skill.name)
    )
    skills_data = result.scalars().all()

    # Fetch all sources for filter dropdown
    sources = await source_repo.list_all()

    # Get all installed skill IDs to mark them in the UI
    installed_result = await session.execute(select(InstalledSkill.skill_id))
    installed_skill_ids = set(installed_result.scalars().all())

    return templates.TemplateResponse(
        "skills/browser.html",
        {
            "request": request,
            "skills": skills_data,
            "sources": sources,
            "installed_skill_ids": installed_skill_ids,
        },
    )


@web_router.get("/skills/search", response_class=HTMLResponse)
async def skills_search(
    request: Request,
    search: str | None = None,
    source_filter: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """
    Search and filter skills (htmx endpoint).

    Args:
        request: FastAPI request object
        search: Search query (name or tag)
        source_filter: Source ID filter
        session: Database session

    Returns:
        Rendered HTML fragment with filtered skills
    """
    # Build query based on filters
    query = select(Skill).options(selectinload(Skill.source))

    # Apply source filter
    if source_filter:
        try:
            source_id = int(source_filter)
            query = query.where(Skill.source_id == source_id)
        except ValueError:
            pass

    # Apply search filter (search in name, display_name, description, and tags)
    if search:
        search_pattern = f"%{search}%"
        query = query.where(
            (Skill.name.ilike(search_pattern))
            | (Skill.display_name.ilike(search_pattern))
            | (Skill.description.ilike(search_pattern))
            | (Skill.tags.ilike(search_pattern))
        )

    query = query.order_by(Skill.name)

    result = await session.execute(query)
    skills_data = result.scalars().all()

    # Get installed skill IDs
    installed_result = await session.execute(select(InstalledSkill.skill_id))
    installed_skill_ids = set(installed_result.scalars().all())

    # Render just the grid content
    if skills_data:
        cards_html = ""
        for skill in skills_data:
            card_html = templates.get_template("skills/_card.html").render(
                request=request,
                skill=skill,
                installed_skill_ids=installed_skill_ids,
            )
            cards_html += card_html
        return HTMLResponse(
            content=f'<div class="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">{cards_html}</div>'
        )
    else:
        return HTMLResponse(
            content="""
            <div class="bg-white shadow rounded-lg border border-gray-200 py-12">
                <div class="text-center">
                    <svg class="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path>
                    </svg>
                    <h3 class="mt-2 text-lg font-medium text-gray-900">No skills found</h3>
                    <p class="mt-1 text-sm text-gray-500">Try adjusting your search or filters.</p>
                </div>
            </div>
            """
        )


@web_router.get("/skills/install/{skill_id}", response_class=HTMLResponse)
async def skills_install_form(
    request: Request,
    skill_id: int,
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """
    Render the skill installation modal.

    Args:
        request: FastAPI request object
        skill_id: Skill ID to install
        session: Database session

    Returns:
        Rendered HTML response with installation form
    """
    skill_repo = SkillRepository(session)
    harness_repo = HarnessRepository(session)
    project_repo = ProjectRepository(session)

    # Get the skill
    skill = await skill_repo.get_with_source(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    # Get all harnesses
    harnesses = await harness_repo.list_all()

    # Get all projects
    projects = await project_repo.list_all()

    return templates.TemplateResponse(
        "skills/_install_modal.html",
        {
            "request": request,
            "skill": skill,
            "harnesses": harnesses,
            "projects": projects,
        },
    )


@web_router.post("/skills/install")
async def skills_install(
    _api_key: APIKey,
    skill_id: int = Form(...),
    harness_id: int = Form(...),
    scope: str = Form(...),
    project_id: int | None = Form(None),
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    """
    Install a skill.

    Args:
        skill_id: Skill ID to install
        harness_id: Harness ID to install to
        scope: Installation scope (global or project)
        project_id: Project ID (required for project scope)
        session: Database session

    Returns:
        Redirect to skills browser
    """
    skill_service = SkillService(session)

    # Convert scope string to enum
    install_scope = InstallScope.GLOBAL if scope == "global" else InstallScope.PROJECT

    try:
        await skill_service.install_skill(
            skill_id=skill_id,
            harness_id=harness_id,
            scope=install_scope,
            project_id=project_id,
        )

        # Return redirect response with HX-Redirect header for htmx
        response = RedirectResponse(url="/skills", status_code=303)
        response.headers["HX-Redirect"] = "/skills"
        return response

    except SkillInstallError:
        # For now, just redirect back with error (could enhance with flash messages)
        response = RedirectResponse(url="/skills", status_code=303)
        response.headers["HX-Redirect"] = "/skills"
        return response


@web_router.get("/harnesses", response_class=HTMLResponse)
async def harnesses_list(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """
    Render the harnesses list page.

    Args:
        request: FastAPI request object
        session: Database session

    Returns:
        Rendered HTML response with harnesses list
    """
    harness_repo = HarnessRepository(session)
    config_repo = HarnessConfigRepository(session)

    # Fetch all harnesses
    harnesses = await harness_repo.list_all()

    # Get config counts for each harness
    harnesses_with_counts = []
    for harness in harnesses:
        configs = await config_repo.list_for_harness(harness.id)
        harnesses_with_counts.append(
            {
                "id": harness.id,
                "name": harness.name,
                "display_name": harness.display_name,
                "version": harness.version,
                "config_count": len(configs),
            }
        )

    return templates.TemplateResponse(
        "harnesses/list.html",
        {
            "request": request,
            "harnesses": harnesses_with_counts,
        },
    )


@web_router.get("/harnesses/{harness_name}", response_class=HTMLResponse)
async def harnesses_detail(
    request: Request,
    harness_name: str,
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """
    Render the harness detail page.

    Args:
        request: FastAPI request object
        harness_name: Harness name
        session: Database session

    Returns:
        Rendered HTML response with harness details
    """
    harness_repo = HarnessRepository(session)
    config_repo = HarnessConfigRepository(session)

    # Fetch harness
    harness = await harness_repo.get_by_name(harness_name)
    if not harness:
        raise HTTPException(status_code=404, detail="Harness not found")

    # Fetch configs for this harness
    all_configs = await config_repo.list_for_harness(harness.id)

    # Separate global and project configs
    global_configs = [config for config in all_configs if config.scope == ConfigScope.GLOBAL]
    project_configs = [config for config in all_configs if config.scope == ConfigScope.PROJECT]

    return templates.TemplateResponse(
        "harnesses/detail.html",
        {
            "request": request,
            "harness": harness,
            "global_configs": global_configs,
            "project_configs": project_configs,
        },
    )


@web_router.post("/harnesses/discover")
async def harnesses_discover_all(
    _api_key: APIKey,
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    """
    Trigger discovery for all harnesses.

    Args:
        session: Database session

    Returns:
        Redirect to harnesses list
    """
    # Run discovery
    await discover_all(session)
    await session.commit()

    # Return redirect response with HX-Redirect header for htmx
    response = RedirectResponse(url="/harnesses", status_code=303)
    response.headers["HX-Redirect"] = "/harnesses"
    return response


@web_router.post("/harnesses/{harness_name}/discover")
async def harnesses_discover_single(
    harness_name: str,
    _api_key: APIKey,
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    """
    Trigger discovery for a specific harness.

    Args:
        harness_name: Harness name
        session: Database session

    Returns:
        Redirect to harness detail
    """
    harness_repo = HarnessRepository(session)

    # Verify harness exists
    harness = await harness_repo.get_by_name(harness_name)
    if not harness:
        raise HTTPException(status_code=404, detail="Harness not found")

    # Run discovery for this harness
    await discover_for_harness(session, harness_name)
    await session.commit()

    # Return redirect response with HX-Redirect header for htmx
    response = RedirectResponse(url=f"/harnesses/{harness_name}", status_code=303)
    response.headers["HX-Redirect"] = f"/harnesses/{harness_name}"
    return response


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


# Translation routes


class TranslateWebRequest(BaseModel):
    """Translation request from web UI."""

    content: str
    source_harness: str
    target_harness: str
    config_kind: str = "instructions"
    project_id: int | None = None


class ApplyWebRequest(BaseModel):
    """Apply translation request from web UI."""

    file_path: str
    content: str


def _parse_diff_to_html(diff: str) -> str:
    """Parse unified diff into HTML for display."""
    lines = diff.split("\n")
    html_parts = []

    html_parts.append('<div class="bg-gray-50 rounded-lg border border-gray-200 overflow-hidden">')
    html_parts.append('<div class="overflow-x-auto">')
    html_parts.append(
        '<table class="min-w-full divide-y divide-gray-200 font-mono text-sm">'
        '<tbody class="bg-white divide-y divide-gray-200">'
    )

    line_num = 0
    for line in lines:
        if line.startswith("@@"):
            # Section header
            html_parts.append(
                f'<tr class="bg-blue-50">'
                f'<td colspan="3" class="px-3 py-1 text-xs text-blue-700 font-semibold">{line}</td>'
                f"</tr>"
            )
            continue

        if line.startswith("---") or line.startswith("+++"):
            # File headers
            continue

        line_num += 1
        line_class = "diff-context"
        symbol = " "
        symbol_class = "text-gray-400"
        content = line

        if line.startswith("+"):
            line_class = "diff-addition"
            symbol = "+"
            symbol_class = "text-green-600"
            content = line[1:]
        elif line.startswith("-"):
            line_class = "diff-deletion"
            symbol = "-"
            symbol_class = "text-red-600"
            content = line[1:]

        # Escape HTML
        content = content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        html_parts.append(
            f'<tr class="{line_class}">'
            f'<td class="px-3 py-1 whitespace-nowrap text-xs text-gray-500 select-none w-12 text-right">{line_num}</td>'
            f'<td class="px-3 py-1 whitespace-nowrap text-xs text-gray-500 select-none w-4">'
            f'<span class="{symbol_class}">{symbol}</span></td>'
            f'<td class="px-3 py-1 text-xs"><pre class="whitespace-pre-wrap break-all">{content}</pre></td>'
            f"</tr>"
        )

    html_parts.append("</tbody></table>")
    html_parts.append("</div></div>")

    return "".join(html_parts)


@web_router.get("/translate", response_class=HTMLResponse)
async def translate_page(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """
    Render the translation page.

    Args:
        request: FastAPI request object
        session: Database session

    Returns:
        Rendered HTML response
    """
    # Get all projects for the dropdown
    project_repo = ProjectRepository(session)
    projects = await project_repo.get_all()

    return templates.TemplateResponse(
        "translate/index.html",
        {
            "request": request,
            "projects": projects,
        },
    )


@web_router.post("/translate/api")
async def translate_api(
    payload: TranslateWebRequest,
    _api_key: APIKey,
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    """
    Translate content between harness formats (web API endpoint).

    Args:
        payload: Translation request
        session: Database session

    Returns:
        JSON response with translation result
    """
    service = TranslationService(session)

    try:
        result = await service.translate(
            content=payload.content,
            source_harness=payload.source_harness,  # type: ignore[arg-type]
            target_harness=payload.target_harness,  # type: ignore[arg-type]
            config_kind=payload.config_kind,  # type: ignore[arg-type]
            project_id=payload.project_id,
        )

        # Convert diff to HTML
        diff_html = _parse_diff_to_html(result.diff)

        return JSONResponse(
            content={
                "output": result.output,
                "diff": result.diff,
                "diff_html": diff_html,
                "log_id": result.log_id,
            }
        )

    except TranslationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Translation failed: {e}") from e


@web_router.post("/translate/apply")
async def apply_translation(
    payload: ApplyWebRequest,
    _api_key: APIKey,
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    """
    Apply translated content to a file.

    Args:
        payload: Apply request
        session: Database session

    Returns:
        JSON response with success message
    """
    service = TranslationService(session)

    try:
        file_path = Path(payload.file_path).expanduser()
        await service.apply_translation(
            file_path=file_path,
            content=payload.content,
        )
        return JSONResponse(content={"message": f"Translation applied to {file_path}"})

    except TranslationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to apply translation: {e}") from e


@web_router.get("/translate/history")
async def translate_history(
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    """
    Get translation history.

    Args:
        session: Database session

    Returns:
        JSON response with translation history
    """
    service = TranslationService(session)

    try:
        logs = await service.get_history(limit=50, offset=0)

        return JSONResponse(
            content=[
                {
                    "id": log.id,
                    "input_text": log.input_text,
                    "output_text": log.output_text,
                    "translation_type": str(log.translation_type.value),
                    "model_name": log.model_name,
                    "project_id": log.project_id,
                    "created_at": log.created_at.isoformat(),
                }
                for log in logs
            ]
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get history: {e}") from e
