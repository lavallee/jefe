"""Bundles API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from jefe.data.database import get_session
from jefe.data.models.bundle import Bundle
from jefe.server.auth import APIKey
from jefe.server.schemas.bundle import (
    BundleApplyRequest,
    BundleApplyResponse,
    BundleCreateRequest,
    BundleResponse,
    SkillRef,
)
from jefe.server.services.bundle import BundleError, BundleService

router = APIRouter()


def _bundle_to_response(bundle: Bundle) -> BundleResponse:
    """Convert a Bundle model to a response schema."""
    skill_refs_list = bundle.get_skill_refs_list()
    skill_refs = [SkillRef(**ref) for ref in skill_refs_list]
    return BundleResponse(
        id=bundle.id,
        name=bundle.name,
        display_name=bundle.display_name,
        description=bundle.description,
        skill_refs=skill_refs,
    )


@router.get("/api/bundles", response_model=list[BundleResponse])
async def list_bundles(
    _api_key: APIKey,
    session: AsyncSession = Depends(get_session),
) -> list[BundleResponse]:
    """List all bundles."""
    service = BundleService(session)
    bundles = await service.list_bundles()
    return [_bundle_to_response(bundle) for bundle in bundles]


@router.get("/api/bundles/{bundle_id}", response_model=BundleResponse)
async def get_bundle(
    bundle_id: int,
    _api_key: APIKey,
    session: AsyncSession = Depends(get_session),
) -> BundleResponse:
    """Get a bundle by ID."""
    service = BundleService(session)
    bundle = await service.get_bundle(bundle_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="Bundle not found")

    return _bundle_to_response(bundle)


@router.post("/api/bundles", response_model=BundleResponse, status_code=status.HTTP_201_CREATED)
async def create_bundle(
    payload: BundleCreateRequest,
    _api_key: APIKey,
    session: AsyncSession = Depends(get_session),
) -> BundleResponse:
    """Create a new bundle."""
    service = BundleService(session)

    try:
        # Convert SkillRef objects to dicts
        skill_refs_list = [ref.model_dump() for ref in payload.skill_refs]

        bundle = await service.create_bundle(
            name=payload.name,
            display_name=payload.display_name,
            description=payload.description,
            skill_refs=skill_refs_list,
        )
        return _bundle_to_response(bundle)
    except BundleError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/api/bundles/{bundle_id}/apply", response_model=BundleApplyResponse)
async def apply_bundle(
    bundle_id: int,
    payload: BundleApplyRequest,
    _api_key: APIKey,
    session: AsyncSession = Depends(get_session),
) -> BundleApplyResponse:
    """Apply a bundle by installing all its skills."""
    service = BundleService(session)

    try:
        result = await service.apply_bundle(
            bundle_id=bundle_id,
            harness_id=payload.harness_id,
            scope=payload.scope,
            project_id=payload.project_id,
        )
        return BundleApplyResponse(
            success=result["success"],
            failed=result["failed"],
            errors=result["errors"],
        )
    except BundleError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
