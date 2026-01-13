"""Recipe API endpoints."""

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from jefe.data.database import get_session
from jefe.server.schemas.recipe import RecipeResponse
from jefe.server.services.recipe import (
    RecipeParseError,
    RecipeResolutionError,
    RecipeService,
    RecipeValidationError,
)

router = APIRouter(prefix="/recipes")


def get_recipe_service(session: AsyncSession = Depends(get_session)) -> RecipeService:
    """Get recipe service instance."""
    # Get data directory from environment or use default
    data_dir = Path("data")
    return RecipeService(session, data_dir)


@router.post("/parse", response_model=RecipeResponse, status_code=status.HTTP_200_OK)
async def parse_recipe(
    payload: dict[str, str],
    service: RecipeService = Depends(get_recipe_service),
) -> dict[str, Any]:
    """
    Parse a recipe from YAML content.

    Args:
        payload: Dictionary with "content" key containing YAML string

    Returns:
        Parsed recipe with metadata

    Raises:
        400: Recipe parsing or validation failed
    """
    content = payload.get("content")
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing 'content' field in request",
        )

    try:
        recipe = service.parse_recipe_content(content)
    except RecipeParseError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except RecipeValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    return {
        "name": recipe.name,
        "description": recipe.description,
        "harnesses": recipe.harnesses,
        "skills": [skill.model_dump() for skill in recipe.skills],
        "bundles": recipe.bundles,
        "skill_count": len(recipe.skills),
        "bundle_count": len(recipe.bundles),
    }


@router.post("/resolve", status_code=status.HTTP_200_OK)
async def resolve_recipe(
    payload: dict[str, str],
    service: RecipeService = Depends(get_recipe_service),
) -> dict[str, Any]:
    """
    Resolve a recipe to actual skill IDs.

    Parses the recipe and resolves all skills and bundles to their database IDs.

    Args:
        payload: Dictionary with "content" key containing YAML string

    Returns:
        Dictionary mapping harness names to lists of resolved skills

    Raises:
        400: Recipe parsing, validation, or resolution failed
    """
    content = payload.get("content")
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing 'content' field in request",
        )

    try:
        recipe = service.parse_recipe_content(content)
        resolved = await service.resolve_recipe(recipe)
    except RecipeParseError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except RecipeValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except RecipeResolutionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    return resolved
