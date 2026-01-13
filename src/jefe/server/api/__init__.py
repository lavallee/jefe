"""API routes and endpoints."""

from fastapi import APIRouter

from jefe.server.api.auth import router as auth_router
from jefe.server.api.harnesses import router as harnesses_router
from jefe.server.api.health import router as health_router
from jefe.server.api.projects import router as projects_router
from jefe.server.api.status import router as status_router

# Main API router
api_router = APIRouter()

# Include sub-routers
api_router.include_router(health_router, tags=["health"])
api_router.include_router(auth_router, tags=["auth"])
api_router.include_router(projects_router, tags=["projects"])
api_router.include_router(harnesses_router, tags=["harnesses"])
api_router.include_router(status_router, tags=["status"])

__all__ = ["api_router"]
