"""API routes and endpoints."""

from fastapi import APIRouter

from jefe.server.api.auth import router as auth_router
from jefe.server.api.bundles import router as bundles_router
from jefe.server.api.harnesses import router as harnesses_router
from jefe.server.api.health import router as health_router
from jefe.server.api.projects import router as projects_router
from jefe.server.api.recipes import router as recipes_router
from jefe.server.api.skills import router as skills_router
from jefe.server.api.sources import router as sources_router
from jefe.server.api.status import router as status_router
from jefe.server.api.sync import router as sync_router
from jefe.server.api.translation import router as translation_router

# Main API router
api_router = APIRouter()

# Include sub-routers
api_router.include_router(health_router, tags=["health"])
api_router.include_router(auth_router, tags=["auth"])
api_router.include_router(projects_router, tags=["projects"])
api_router.include_router(harnesses_router, tags=["harnesses"])
api_router.include_router(skills_router, tags=["skills"])
api_router.include_router(bundles_router, tags=["bundles"])
api_router.include_router(sources_router, tags=["sources"])
api_router.include_router(recipes_router, tags=["recipes"])
api_router.include_router(status_router, tags=["status"])
api_router.include_router(sync_router, tags=["sync"])
api_router.include_router(translation_router, tags=["translation"])

__all__ = ["api_router"]
