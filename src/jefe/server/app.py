"""FastAPI application factory and configuration."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from jefe import __version__
from jefe.data.database import close_db, init_db


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Handle application startup and shutdown events.

    On startup: Initialize database connections and ensure API key exists.
    On shutdown: Close database connections.
    """
    # Startup
    await init_db()

    # Ensure API key exists
    from jefe.server.auth import ensure_api_key_exists

    new_key = ensure_api_key_exists()
    if new_key is not None:
        print("\n" + "=" * 70)
        print("🔑 NEW API KEY GENERATED")
        print("=" * 70)
        print(f"\nYour API key: {new_key}")
        print("\nSave this key securely - it won't be shown again!")
        print("Use it in the X-API-Key header for all API requests.")
        print("=" * 70 + "\n")

    from jefe.data.database import AsyncSessionLocal
    from jefe.server.services.harness import HarnessService

    async with AsyncSessionLocal() as session:
        await HarnessService(session).seed_harnesses()

    yield
    # Shutdown
    await close_db()


def create_app() -> FastAPI:
    """
    Create and configure FastAPI application instance.

    Returns:
        Configured FastAPI application ready to serve requests.
    """
    app = FastAPI(
        title="Jefe",
        description="A comprehensive Git repository management system with web and CLI interfaces",
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # Configure CORS middleware
    # Allow all origins in development, should be configured for production
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure this for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register global exception handlers
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Handle validation errors with consistent JSON response."""
        return JSONResponse(
            status_code=422,
            content={
                "error": "Validation Error",
                "message": "Request validation failed",
                "details": exc.errors(),
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
        """Handle general exceptions with consistent JSON response."""
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal Server Error",
                "message": str(exc),
            },
        )

    # Import and register routers
    from jefe.server.api import api_router
    from jefe.web import web_router

    app.include_router(api_router)
    app.include_router(web_router)

    return app
