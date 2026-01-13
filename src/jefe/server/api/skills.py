"""Skills API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from jefe.data.database import get_session
from jefe.data.models.installed_skill import InstalledSkill
from jefe.data.models.skill import Skill
from jefe.server.auth import APIKey
from jefe.server.schemas.skill import (
    InstalledSkillResponse,
    SkillInstallRequest,
    SkillResponse,
)
from jefe.server.services.skill import SkillInstallError, SkillService

router = APIRouter()


def _skill_to_response(skill: Skill) -> SkillResponse:
    """Convert a Skill model to a response schema."""
    return SkillResponse(
        id=skill.id,
        source_id=skill.source_id,
        name=skill.name,
        display_name=skill.display_name,
        description=skill.description,
        version=skill.version,
        author=skill.author,
        tags=skill.get_tags_list(),
        metadata=skill.get_metadata_dict(),
    )


def _installed_skill_to_response(installed: InstalledSkill) -> InstalledSkillResponse:
    """Convert an InstalledSkill model to a response schema."""
    return InstalledSkillResponse(
        id=installed.id,
        skill_id=installed.skill_id,
        harness_id=installed.harness_id,
        scope=installed.scope,
        project_id=installed.project_id,
        installed_path=installed.installed_path,
        pinned_version=installed.pinned_version,
        skill=_skill_to_response(installed.skill),
    )


@router.get("/api/skills", response_model=list[SkillResponse])
async def list_skills(
    _api_key: APIKey,
    session: AsyncSession = Depends(get_session),
    source: int | None = Query(None, description="Filter by source ID"),
    name: str | None = Query(None, description="Filter by skill name"),
    tag: str | None = Query(None, description="Filter by tag"),
) -> list[SkillResponse]:
    """List all skills with optional filters."""
    service = SkillService(session)
    skills = await service.list_skills(source_id=source, name=name, tag=tag)
    return [_skill_to_response(skill) for skill in skills]


@router.get("/api/skills/installed", response_model=list[InstalledSkillResponse])
async def list_installed_skills(
    _api_key: APIKey,
    session: AsyncSession = Depends(get_session),
    project: int | None = Query(None, description="Filter by project ID"),
    harness: int | None = Query(None, description="Filter by harness ID"),
) -> list[InstalledSkillResponse]:
    """List installed skills with optional filters."""
    service = SkillService(session)
    installed = await service.list_installed_skills(project_id=project, harness_id=harness)
    return [_installed_skill_to_response(inst) for inst in installed]


@router.get("/api/skills/{skill_id}", response_model=SkillResponse)
async def get_skill(
    skill_id: int,
    _api_key: APIKey,
    session: AsyncSession = Depends(get_session),
) -> SkillResponse:
    """Get a skill by ID."""
    service = SkillService(session)
    skill = await service.get_skill(skill_id)
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill not found")

    return _skill_to_response(skill)


@router.post("/api/skills/install", response_model=InstalledSkillResponse, status_code=status.HTTP_201_CREATED)
async def install_skill(
    payload: SkillInstallRequest,
    _api_key: APIKey,
    session: AsyncSession = Depends(get_session),
) -> InstalledSkillResponse:
    """Install a skill to a harness."""
    service = SkillService(session)

    try:
        installed = await service.install_skill(
            skill_id=payload.skill_id,
            harness_id=payload.harness_id,
            scope=payload.scope,
            project_id=payload.project_id,
        )
        # Refresh to load relationships
        await session.refresh(installed, ["skill"])
        return _installed_skill_to_response(installed)
    except SkillInstallError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.delete("/api/skills/installed/{installed_skill_id}", status_code=status.HTTP_204_NO_CONTENT)
async def uninstall_skill(
    installed_skill_id: int,
    _api_key: APIKey,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Uninstall a skill."""
    service = SkillService(session)
    success = await service.uninstall_skill(installed_skill_id)
    if not success:
        raise HTTPException(status_code=404, detail="Installed skill not found")
