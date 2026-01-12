# Agent Instructions

This file contains instructions for building and running the project.
Update this file as you learn new things about the codebase.

## Project Overview

Jefe is a comprehensive Git repository management system with web and CLI interfaces. It provides tools for managing, monitoring, and automating Git repository operations with both programmatic (REST API) and user-friendly (web + CLI) interfaces.

## Tech Stack

- **Language**: Python 3.11+
- **Framework**: FastAPI, Typer
- **Database**: SQLAlchemy + Alembic for ORM and migrations
- **Web**: Jinja2 templates
- **CLI**: Typer (built on Click)
- **Tools**: Rich (terminal formatting), GitPython, Pydantic

## Development Setup

```bash
# Install dependencies using uv (recommended)
uv sync

# Or using pip
pip install -e ".[dev]"

# Activate virtual environment (if using pip)
source .venv/bin/activate
```

## Running the Project

### Local Development (with Docker)

```bash
# Start the development server in Docker
make docker-up

# Stop the server
make docker-down

# View logs
make docker-logs

# Restart the server
make docker-restart

# Access the API at http://localhost:8000
# API key is displayed on first startup
```

### Local Development (native)

```bash
# Development server (API) - using factory pattern
uvicorn jefe.server.app:create_app --factory --reload

# Or using module entry point
python -m jefe.server

# CLI (installed as 'jefe' command)
jefe --version
jefe --help
jefe config show
jefe config set server_url http://localhost:8000
```

### Docker Setup

The project includes Docker support for containerized development:

- **Dockerfile**: Python 3.11 image with dependencies
- **docker-compose.yml**: Single-service setup with hot reload and database persistence
- **docker-compose.override.yml.example**: Template for local customization
- **.dockerignore**: Optimizes build context

Hot reload is enabled - source code changes are reflected without rebuild.

## Feedback Loops

Run these before committing:

```bash
# Type checking
mypy src/jefe

# Tests
pytest

# Linting
ruff check src/jefe

# Format (optional, ruff handles most formatting)
black src/jefe
ruff format src/jefe
```

## Project Structure

```
├── src/           # Source code
├── specs/         # Specifications
├── tests/         # Test files
├── prd.json       # Task backlog
├── progress.txt   # Session learnings
└── AGENT.md       # This file
```

## Key Files

- `pyproject.toml` - Project configuration, dependencies, tool settings
- `src/jefe/__init__.py` - Package entry point with version
- `src/jefe/server/` - FastAPI server and REST API implementation
- `src/jefe/cli/` - Command-line interface with Typer
- `src/jefe/web/` - Web interface templates and static files
- `src/jefe/adapters/` - Integration adapters (Git hosting platforms, etc.)
- `src/jefe/data/` - Data models, database schema, ORM definitions
- `README.md` - User-facing documentation

## Gotchas & Learnings

- W503 linting rule was removed in newer ruff versions (removed from pyproject.toml config)
- Typer's `[all]` extra doesn't exist in version 0.21.1 (uses standard Typer with Click)
- Virtual environment is created at `.venv/` by uv

## Common Commands

```bash
# Activate virtual environment
source .venv/bin/activate

# Run all feedback loops
mypy src/jefe && ruff check src/jefe && pytest

# Test module import
python -c "import jefe; print(jefe.__version__)"

# Install in editable mode with dev dependencies
pip install -e ".[dev]"
```
