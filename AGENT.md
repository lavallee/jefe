# Agent Instructions

This file contains instructions for building and running the project.
Update this file as you learn new things about the codebase.

## Project Overview

Station Chief is a comprehensive Git repository management system with web and CLI interfaces. It provides tools for managing, monitoring, and automating Git repository operations with both programmatic (REST API) and user-friendly (web + CLI) interfaces.

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

```bash
# Development server (API) - using factory pattern
uvicorn station_chief.server.app:create_app --factory --reload

# Or using module entry point
python -m station_chief.server

# CLI
# python -m station_chief.cli
# Note: CLI implementation pending
```

## Feedback Loops

Run these before committing:

```bash
# Type checking
mypy src/station_chief

# Tests
pytest

# Linting
ruff check src/station_chief

# Format (optional, ruff handles most formatting)
black src/station_chief
ruff format src/station_chief
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
- `src/station_chief/__init__.py` - Package entry point with version
- `src/station_chief/server/` - FastAPI server and REST API implementation
- `src/station_chief/cli/` - Command-line interface with Typer
- `src/station_chief/web/` - Web interface templates and static files
- `src/station_chief/adapters/` - Integration adapters (Git hosting platforms, etc.)
- `src/station_chief/data/` - Data models, database schema, ORM definitions
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
mypy src/station_chief && ruff check src/station_chief && pytest

# Test module import
python -c "import station_chief; print(station_chief.__version__)"

# Install in editable mode with dev dependencies
pip install -e ".[dev]"
```
