"""Project registry CLI commands."""

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from jefe.cli.api import create_client, get_api_key

projects_app = typer.Typer(name="projects", help="Manage project registry")
console = Console()
PATH_OPTION = typer.Option(..., "--path", help="Local path to the project")
DESCRIPTION_OPTION = typer.Option(None, "--description", help="Optional description")


def _require_api_key() -> None:
    if not get_api_key():
        console.print("[red]API key not configured.[/red] Set it with:")
        console.print("  jefe config set api_key <key>")
        raise typer.Exit(code=1)


@projects_app.command("list")
def list_projects() -> None:
    """List registered projects."""
    _require_api_key()
    with create_client() as client:
        response = client.get("/api/projects")

    if response.status_code != 200:
        console.print(f"[red]Failed to list projects ({response.status_code}).[/red]")
        raise typer.Exit(code=1)

    projects = response.json()
    if not projects:
        console.print("No projects registered.")
        return

    table = Table(title="Projects", show_header=True, header_style="bold magenta")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Name", style="green")
    table.add_column("Manifestations", style="yellow")

    for project in projects:
        table.add_row(
            str(project["id"]),
            project["name"],
            str(len(project.get("manifestations", []))),
        )

    console.print(table)


@projects_app.command("add")
def add_project(
    name: str = typer.Argument(..., help="Project name"),
    path: Path = PATH_OPTION,
    description: str | None = DESCRIPTION_OPTION,
) -> None:
    """Register a new project."""
    _require_api_key()
    if not path.exists():
        console.print(f"[red]Path does not exist:[/red] {path}")
        raise typer.Exit(code=1)

    payload = {"name": name, "description": description, "path": str(path)}
    with create_client() as client:
        response = client.post("/api/projects", json=payload)

    if response.status_code != 201:
        console.print(f"[red]Failed to create project ({response.status_code}).[/red]")
        if response.text:
            console.print(response.text)
        raise typer.Exit(code=1)

    project = response.json()
    console.print(f"Created project {project['name']} (id={project['id']}).")
