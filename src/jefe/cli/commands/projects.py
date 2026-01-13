"""Project registry CLI commands."""

from pathlib import Path
from typing import Any

import anyio
import httpx
import typer
from rich.console import Console
from rich.table import Table

from jefe.cli.client import create_client, get_api_key, get_server_url

projects_app = typer.Typer(name="projects", help="Manage project registry")
console = Console()
PATH_OPTION = typer.Option(None, "--path", help="Local path to the project")
REMOTE_OPTION = typer.Option(None, "--remote", help="Remote repository URL")
DESCRIPTION_OPTION = typer.Option(None, "--description", help="Optional description")


def _require_api_key() -> None:
    if not get_api_key():
        console.print("[red]API key not configured.[/red] Set it with:")
        console.print("  jefe config set api_key <key>")
        raise typer.Exit(code=1)


async def _request(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    **kwargs: Any,
) -> httpx.Response:
    try:
        return await client.request(method, url, **kwargs)
    except httpx.RequestError as exc:
        console.print(f"[red]Unable to reach server at {get_server_url()}.[/red]")
        console.print(f"[dim]{exc}[/dim]")
        raise typer.Exit(code=1) from exc


def _fail_request(action: str, response: httpx.Response) -> None:
    console.print(f"[red]Failed to {action} ({response.status_code}).[/red]")
    if response.text:
        console.print(response.text)
    raise typer.Exit(code=1)


def _render_projects_table(projects: list[dict[str, Any]]) -> None:
    table = Table(title="Projects", show_header=True, header_style="bold magenta")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Name", style="green")
    table.add_column("Description", style="white")
    table.add_column("Manifestations", style="yellow")

    for project in projects:
        description = str(project.get("description") or "-")
        manifestations = project.get("manifestations")
        count = len(manifestations) if isinstance(manifestations, list) else 0
        table.add_row(
            str(project["id"]),
            str(project["name"]),
            description,
            str(count),
        )

    console.print(table)


def _render_manifestations(manifestations: list[dict[str, Any]]) -> None:
    if not manifestations:
        console.print("No manifestations registered.")
        return

    table = Table(title="Manifestations", show_header=True, header_style="bold magenta")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Type", style="green")
    table.add_column("Path", style="white")
    table.add_column("Machine", style="dim")
    table.add_column("Last Seen", style="yellow")

    for item in manifestations:
        table.add_row(
            str(item.get("id", "")),
            str(item.get("type", "")),
            str(item.get("path", "")),
            str(item.get("machine_id") or "-"),
            str(item.get("last_seen") or "-"),
        )

    console.print(table)


def _render_configs(configs: list[dict[str, Any]]) -> None:
    if not configs:
        console.print("No configs discovered.")
        return

    table = Table(title="Configs", show_header=True, header_style="bold magenta")
    table.add_column("Harness", style="cyan", no_wrap=True)
    table.add_column("Scope", style="green")
    table.add_column("Kind", style="yellow")
    table.add_column("Path", style="white")

    for config in configs:
        table.add_row(
            str(config.get("harness", "")),
            str(config.get("scope", "")),
            str(config.get("kind", "")),
            str(config.get("path", "")),
        )

    console.print(table)


async def _resolve_project_id(client: httpx.AsyncClient, name_or_id: str) -> int:
    if name_or_id.isdigit():
        return int(name_or_id)

    response = await _request(client, "GET", "/api/projects")
    if response.status_code != 200:
        _fail_request("list projects", response)

    projects = response.json()
    for project in projects:
        if project.get("name") == name_or_id:
            return int(project["id"])

    console.print(f"[red]Project '{name_or_id}' not found.[/red]")
    raise typer.Exit(code=1)


@projects_app.command("list")
def list_projects() -> None:
    """List registered projects."""
    _require_api_key()
    anyio.run(_list_projects_async)


async def _list_projects_async() -> None:
    async with create_client() as client:
        response = await _request(client, "GET", "/api/projects")

    if response.status_code != 200:
        _fail_request("list projects", response)

    projects = response.json()
    if not projects:
        console.print("No projects registered.")
        return

    _render_projects_table(projects)


@projects_app.command("add")
def add_project(
    name: str = typer.Argument(..., help="Project name"),
    path: Path | None = PATH_OPTION,
    remote: str | None = REMOTE_OPTION,
    description: str | None = DESCRIPTION_OPTION,
) -> None:
    """Register a new project."""
    _require_api_key()
    anyio.run(_add_project_async, name, path, remote, description)


async def _add_project_async(
    name: str,
    path: Path | None,
    remote: str | None,
    description: str | None,
) -> None:
    if path is not None and not path.exists():
        console.print(f"[red]Path does not exist:[/red] {path}")
        raise typer.Exit(code=1)

    payload: dict[str, object] = {"name": name, "description": description}
    if path is not None:
        payload["path"] = str(path)

    async with create_client() as client:
        response = await _request(client, "POST", "/api/projects", json=payload)
        if response.status_code != 201:
            _fail_request("create project", response)

        project = response.json()

        if remote:
            manifest_payload = {"type": "remote", "path": remote}
            manifest_response = await _request(
                client,
                "POST",
                f"/api/projects/{project['id']}/manifestations",
                json=manifest_payload,
            )
            if manifest_response.status_code != 201:
                _fail_request("add remote", manifest_response)

    console.print(f"Created project {project['name']} (id={project['id']}).")
    if remote:
        console.print(f"Added remote {remote}.")


@projects_app.command("show")
def show_project(
    name_or_id: str = typer.Argument(..., help="Project name or id"),
) -> None:
    """Show project details."""
    _require_api_key()
    anyio.run(_show_project_async, name_or_id)


async def _show_project_async(name_or_id: str) -> None:
    async with create_client() as client:
        project_id = await _resolve_project_id(client, name_or_id)
        response = await _request(client, "GET", f"/api/projects/{project_id}")

    if response.status_code != 200:
        _fail_request("load project", response)

    project = response.json()
    console.print(f"[bold]{project['name']}[/bold] (id={project['id']})")
    if project.get("description"):
        console.print(project["description"])
    _render_manifestations(project.get("manifestations", []))
    _render_configs(project.get("configs", []))


@projects_app.command("remove")
def remove_project(
    name_or_id: str = typer.Argument(..., help="Project name or id"),
) -> None:
    """Remove a project."""
    _require_api_key()
    anyio.run(_remove_project_async, name_or_id)


async def _remove_project_async(name_or_id: str) -> None:
    async with create_client() as client:
        project_id = await _resolve_project_id(client, name_or_id)
        response = await _request(client, "DELETE", f"/api/projects/{project_id}")

    if response.status_code != 204:
        _fail_request("delete project", response)

    console.print(f"Removed project {name_or_id}.")
