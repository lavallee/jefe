"""Skills CLI commands."""

from typing import Any

import anyio
import httpx
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from jefe.cli.client import create_client, get_api_key, get_server_url

skills_app = typer.Typer(name="skills", help="Browse and install skills")
console = Console()


def _require_api_key() -> None:
    if not get_api_key():
        console.print("[red]API key not configured.[/red] Set it with:")
        console.print("  sc config set api_key <key>")
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


def _render_skills_table(skills: list[dict[str, Any]], title: str = "Skills") -> None:
    table = Table(title=title, show_header=True, header_style="bold magenta")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Name", style="green")
    table.add_column("Display Name", style="white")
    table.add_column("Version", style="yellow")
    table.add_column("Author", style="blue")
    table.add_column("Description", style="dim")

    for skill in skills:
        table.add_row(
            str(skill["id"]),
            str(skill["name"]),
            str(skill.get("display_name") or "-"),
            str(skill.get("version") or "-"),
            str(skill.get("author") or "-"),
            str(skill.get("description") or "")[:60],
        )

    console.print(table)


def _render_installed_skills_table(installs: list[dict[str, Any]]) -> None:
    table = Table(title="Installed Skills", show_header=True, header_style="bold magenta")
    table.add_column("Install ID", style="cyan", no_wrap=True)
    table.add_column("Name", style="green")
    table.add_column("Scope", style="yellow")
    table.add_column("Harness", style="blue")
    table.add_column("Project", style="white")
    table.add_column("Version", style="dim")

    for install in installs:
        skill = install.get("skill", {})
        harness = install.get("harness", {})
        project = install.get("project")

        table.add_row(
            str(install["id"]),
            str(skill.get("name", "-")),
            str(install.get("scope", "-")),
            str(harness.get("name", "-")),
            str(project["name"] if project else "-"),
            str(install.get("pinned_version") or skill.get("version") or "-"),
        )

    console.print(table)


def _render_skill_detail(skill: dict[str, Any]) -> None:
    """Render detailed skill information in a panel."""
    lines = [
        f"[bold green]Name:[/bold green] {skill['name']}",
        f"[bold cyan]Display Name:[/bold cyan] {skill.get('display_name') or '-'}",
        f"[bold yellow]Version:[/bold yellow] {skill.get('version') or '-'}",
        f"[bold blue]Author:[/bold blue] {skill.get('author') or '-'}",
        f"[bold magenta]Source ID:[/bold magenta] {skill.get('source_id')}",
        "",
        "[bold]Description:[/bold]",
        skill.get("description") or "No description available.",
    ]

    # Add tags if present
    tags = skill.get("tags")
    if tags:
        lines.append("")
        lines.append(f"[bold]Tags:[/bold] {', '.join(tags)}")

    # Add metadata if present
    metadata = skill.get("metadata_json")
    if metadata and isinstance(metadata, dict):
        lines.append("")
        lines.append("[bold]Metadata:[/bold]")
        for key, value in metadata.items():
            lines.append(f"  {key}: {value}")

    panel = Panel("\n".join(lines), title=f"Skill: {skill['name']}", border_style="magenta")
    console.print(panel)


async def _resolve_skill_id(client: httpx.AsyncClient, name_or_id: str) -> int:
    if name_or_id.isdigit():
        return int(name_or_id)

    response = await _request(client, "GET", "/api/skills")
    if response.status_code != 200:
        _fail_request("list skills", response)

    skills = response.json()
    for skill in skills:
        if skill.get("name") == name_or_id:
            return int(skill["id"])

    console.print(f"[red]Skill '{name_or_id}' not found.[/red]")
    raise typer.Exit(code=1)


@skills_app.command("search")
def search_skills(
    query: str = typer.Argument(..., help="Search query (searches names, descriptions, tags)"),
) -> None:
    """Search for skills by name, tag, or description."""
    _require_api_key()
    anyio.run(_search_skills_async, query)


async def _search_skills_async(query: str) -> None:
    async with create_client() as client:
        # Try searching by tag first
        response = await _request(client, "GET", f"/api/skills?tag={query}")

        if response.status_code != 200:
            _fail_request("search skills", response)

        skills = response.json()

        # If no results by tag, try by name
        if not skills:
            response = await _request(client, "GET", f"/api/skills?name={query}")

            if response.status_code != 200:
                _fail_request("search skills", response)

            skills = response.json()

        if not skills:
            console.print(f"No skills found matching '{query}'.")
            return

        _render_skills_table(skills, title=f"Search Results: '{query}'")


async def _resolve_project_id(client: httpx.AsyncClient, project_name: str) -> int:
    projects_response = await _request(client, "GET", "/api/projects")
    if projects_response.status_code != 200:
        _fail_request("list projects", projects_response)

    projects = projects_response.json()
    for proj in projects:
        if proj.get("name") == project_name:
            return int(proj["id"])

    console.print(f"[red]Project '{project_name}' not found.[/red]")
    raise typer.Exit(code=1)


async def _list_installed_skills(client: httpx.AsyncClient, project_name: str | None) -> None:
    url = "/api/skills/installed"

    # Resolve project name to ID if provided
    if project_name:
        project_id = await _resolve_project_id(client, project_name)
        url = f"{url}?project={project_id}"

    response = await _request(client, "GET", url)

    if response.status_code != 200:
        _fail_request("list installed skills", response)

    installs = response.json()
    if not installs:
        console.print("No skills installed.")
        return

    _render_installed_skills_table(installs)


async def _list_available_skills(client: httpx.AsyncClient) -> None:
    response = await _request(client, "GET", "/api/skills")

    if response.status_code != 200:
        _fail_request("list skills", response)

    skills = response.json()
    if not skills:
        console.print("No skills available.")
        console.print("Add a skill source with: [cyan]sc sources add[/cyan]")
        return

    _render_skills_table(skills, title="Available Skills")


@skills_app.command("list")
def list_skills(
    installed: bool = typer.Option(False, "--installed", help="Show only installed skills"),
    project: str | None = typer.Option(None, "--project", help="Filter installed by project name"),
) -> None:
    """List all available skills or installed skills."""
    _require_api_key()
    anyio.run(_list_skills_async, installed, project)


async def _list_skills_async(installed: bool, project_name: str | None) -> None:
    async with create_client() as client:
        if installed:
            await _list_installed_skills(client, project_name)
        else:
            await _list_available_skills(client)


@skills_app.command("show")
def show_skill(
    name_or_id: str = typer.Argument(..., help="Skill name or ID"),
) -> None:
    """Show detailed information about a skill."""
    _require_api_key()
    anyio.run(_show_skill_async, name_or_id)


async def _show_skill_async(name_or_id: str) -> None:
    async with create_client() as client:
        skill_id = await _resolve_skill_id(client, name_or_id)
        response = await _request(client, "GET", f"/api/skills/{skill_id}")

        if response.status_code != 200:
            _fail_request("get skill", response)

        skill = response.json()
        _render_skill_detail(skill)


@skills_app.command("install")
def install_skill(
    name_or_id: str = typer.Argument(..., help="Skill name or ID"),
    harness: str = typer.Option(..., "--harness", help="Target harness name"),
    project: str | None = typer.Option(None, "--project", help="Project name (for project scope)"),
    global_scope: bool = typer.Option(False, "--global", help="Install globally"),
) -> None:
    """Install a skill to a harness."""
    _require_api_key()

    # Validate scope
    if global_scope and project:
        console.print("[red]Cannot specify both --global and --project.[/red]")
        raise typer.Exit(code=1)

    if not global_scope and not project:
        console.print("[red]Must specify either --global or --project.[/red]")
        raise typer.Exit(code=1)

    anyio.run(_install_skill_async, name_or_id, harness, project, global_scope)


async def _resolve_harness_id(client: httpx.AsyncClient, harness_name: str) -> int:
    harnesses_response = await _request(client, "GET", "/api/harnesses")
    if harnesses_response.status_code != 200:
        _fail_request("list harnesses", harnesses_response)

    harnesses = harnesses_response.json()
    for harness in harnesses:
        if harness.get("name") == harness_name:
            return int(harness["id"])

    console.print(f"[red]Harness '{harness_name}' not found.[/red]")
    console.print("Discover harnesses with: [cyan]sc harnesses discover[/cyan]")
    raise typer.Exit(code=1)


async def _install_skill_async(
    name_or_id: str,
    harness_name: str,
    project_name: str | None,
    global_scope: bool,
) -> None:
    async with create_client() as client:
        # Resolve skill ID
        skill_id = await _resolve_skill_id(client, name_or_id)

        # Resolve harness ID
        harness_id = await _resolve_harness_id(client, harness_name)

        # Resolve project ID if needed
        project_id = None
        if project_name:
            project_id = await _resolve_project_id(client, project_name)

        # Install skill
        payload: dict[str, object] = {
            "skill_id": skill_id,
            "harness_id": harness_id,
            "scope": "global" if global_scope else "project",
            "project_id": project_id,
        }

        console.print("[cyan]Installing skill...[/cyan]")
        response = await _request(client, "POST", "/api/skills/install", json=payload)

        if response.status_code != 201:
            _fail_request("install skill", response)

        install = response.json()
        scope_display = "globally" if global_scope else f"to project '{project_name}'"
        console.print(
            f"[green]✓[/green] Installed skill '{name_or_id}' {scope_display} "
            f"(install_id={install['id']})."
        )
        console.print(f"  Path: {install.get('installed_path', 'N/A')}")


@skills_app.command("uninstall")
def uninstall_skill(
    install_id: int = typer.Argument(..., help="Installation ID (from 'sc skills list --installed')"),
) -> None:
    """Uninstall a skill by installation ID."""
    _require_api_key()
    anyio.run(_uninstall_skill_async, install_id)


async def _uninstall_skill_async(install_id: int) -> None:
    async with create_client() as client:
        response = await _request(client, "DELETE", f"/api/skills/installed/{install_id}")

        if response.status_code != 204:
            _fail_request("uninstall skill", response)

        console.print(f"[green]Uninstalled skill (install_id={install_id}).[/green]")
