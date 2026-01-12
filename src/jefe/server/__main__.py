"""Entry point for running the server as a module."""

import uvicorn


def main() -> None:
    """Run the FastAPI server."""
    uvicorn.run(
        "jefe.server.app:create_app",
        factory=True,
        host="0.0.0.0",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":
    main()
