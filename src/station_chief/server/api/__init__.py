"""API routes and endpoints."""

from fastapi import APIRouter

from station_chief.server.api.health import router as health_router

# Main API router
api_router = APIRouter()

# Include sub-routers
api_router.include_router(health_router, tags=["health"])

__all__ = ["api_router"]
