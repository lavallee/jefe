"""Bundle CLI commands."""

from __future__ import annotations

from typing import Any

import anyio
import httpx
import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from jefe.cli.client import create_client, get_api_key, get_server_url

bundles_app = typer.Typer(name="bundles", help="Manage skill bundles")
console = Console()


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


def _render_bundles_table(bundles: list[dict[str, Any]]) -> None:
    """Render a table of bundles."""
    if not bundles:
        console.print("No bundles available.")
        return

    table = Table(title="Skill Bundles", show_header=True, header_style="bold magenta")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Name", style="green")
    table.add_column("Display Name", style="white")
    table.add_column("Skills", style="yellow", justify="right")
    table.add_column("Description", style="dim")

    for bundle in bundles:
        skill_refs = bundle.get("skill_refs", [])
        skill_count = str(len(skill_refs)) if skill_refs else "0"
        description = str(bundle.get("description") or "")[:50]

        table.add_row(
            str(bundle["id"]),
            str(bundle["name"]),
            str(bundle.get("display_name") or "-"),
            skill_count,
            description,
        )

    console.print(table)


def _render_bundle_detail(bundle: dict[str, Any]) -> None:
    """Render detailed bundle information in a panel."""
    lines = [
        f"[bold green]Name:[/bold green] {bundle['name']}",
        f"[bold cyan]Display Name:[/bold cyan] {bundle.get('display_name') or '-'}",
        f"[bold magenta]ID:[/bold magenta] {bundle['id']}",
        "",
        "[bold]Description:[/bold]",
        bundle.get("description") or "No description available.",
    ]

    # Add skill references
    skill_refs = bundle.get("skill_refs", [])
    if skill_refs:
        lines.append("")
        lines.append(f"[bold]Skills ({len(skill_refs)}):[/bold]")
        for ref in skill_refs:
            source = ref.get("source", "?")
            name = ref.get("name", "?")
            lines.append(f"  • {source}/{name}")
    else:
        lines.append("")
        lines.append("[dim]No skills in this bundle.[/dim]")

    panel = Panel("\n".join(lines), title=f"Bundle: {bundle['name']}", border_style="magenta")
    console.print(panel)


async def _resolve_bundle_id(client: httpx.AsyncClient, name_or_id: str) -> int:
    """Resolve a bundle name or ID to an ID."""
    if name_or_id.isdigit():
        return int(name_or_id)

    # Fetch all bundles and search by name
    response = await _request(client, "GET", "/api/bundles")
    if response.status_code != 200:
        _fail_request("list bundles", response)

    bundles = response.json()
    for bundle in bundles:
        if bundle.get("name") == name_or_id:
            return int(bundle["id"])

    console.print(f"[red]Bundle '{name_or_id}' not found.[/red]")
    raise typer.Exit(code=1)


async def _resolve_harness_id(client: httpx.AsyncClient, harness_name: str) -> int:
    """Resolve a harness name to an ID."""
    harnesses_response = await _request(client, "GET", "/api/harnesses")
    if harnesses_response.status_code != 200:
        _fail_request("list harnesses", harnesses_response)

    harnesses = harnesses_response.json()
    for harness in harnesses:
        if harness.get("name") == harness_name:
            return int(harness["id"])

    console.print(f"[red]Harness '{harness_name}' not found.[/red]")
    console.print("Discover harnesses with: [cyan]jefe harnesses discover[/cyan]")
    raise typer.Exit(code=1)


async def _resolve_project_id(client: httpx.AsyncClient, project_name: str) -> int:
    """Resolve a project name to an ID."""
    projects_response = await _request(client, "GET", "/api/projects")
    if projects_response.status_code != 200:
        _fail_request("list projects", projects_response)

    projects = projects_response.json()
    for proj in projects:
        if proj.get("name") == project_name:
            return int(proj["id"])

    console.print(f"[red]Project '{project_name}' not found.[/red]")
    raise typer.Exit(code=1)


@bundles_app.command("list")
def list_bundles() -> None:
    """List all available skill bundles."""
    _require_api_key()
    anyio.run(_list_bundles_async)


async def _list_bundles_async() -> None:
    async with create_client() as client:
        response = await _request(client, "GET", "/api/bundles")

        if response.status_code != 200:
            _fail_request("list bundles", response)

        bundles = response.json()
        _render_bundles_table(bundles)


@bundles_app.command("show")
def show_bundle(
    name_or_id: str = typer.Argument(..., help="Bundle name or ID"),
) -> None:
    """Show detailed information about a bundle."""
    _require_api_key()
    anyio.run(_show_bundle_async, name_or_id)


async def _show_bundle_async(name_or_id: str) -> None:
    async with create_client() as client:
        bundle_id = await _resolve_bundle_id(client, name_or_id)
        response = await _request(client, "GET", f"/api/bundles/{bundle_id}")

        if response.status_code != 200:
            _fail_request("get bundle", response)

        bundle = response.json()
        _render_bundle_detail(bundle)


@bundles_app.command("apply")
def apply_bundle(
    name_or_id: str = typer.Argument(..., help="Bundle name or ID"),
    harness: str = typer.Option(..., "--harness", help="Target harness name"),
    project: str | None = typer.Option(None, "--project", help="Project name (for project scope)"),
    global_scope: bool = typer.Option(False, "--global", help="Install globally"),
) -> None:
    """Apply a bundle by installing all its skills to a harness."""
    _require_api_key()

    # Validate scope
    if global_scope and project:
        console.print("[red]Cannot specify both --global and --project.[/red]")
        raise typer.Exit(code=1)

    if not global_scope and not project:
        console.print("[red]Must specify either --global or --project.[/red]")
        raise typer.Exit(code=1)

    anyio.run(_apply_bundle_async, name_or_id, harness, project, global_scope)


async def _apply_bundle_async(
    name_or_id: str,
    harness_name: str,
    project_name: str | None,
    global_scope: bool,
) -> None:
    async with create_client() as client:
        # Resolve bundle ID
        bundle_id = await _resolve_bundle_id(client, name_or_id)

        # Resolve harness ID
        harness_id = await _resolve_harness_id(client, harness_name)

        # Resolve project ID if needed
        project_id = None
        if project_name:
            project_id = await _resolve_project_id(client, project_name)

        # Prepare payload
        payload: dict[str, object] = {
            "harness_id": harness_id,
            "scope": "global" if global_scope else "project",
            "project_id": project_id,
        }

        # Apply bundle with progress indication
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Applying bundle...", total=None)

            response = await _request(
                client, "POST", f"/api/bundles/{bundle_id}/apply", json=payload
            )

            progress.update(task, completed=True)

        if response.status_code != 200:
            _fail_request("apply bundle", response)

        result = response.json()
        success_count = result.get("success_count", 0)
        failed_count = result.get("failed_count", 0)
        errors = result.get("errors", [])

        # Display results
        scope_display = "globally" if global_scope else f"to project '{project_name}'"
        console.print()

        if success_count > 0:
            console.print(
                f"[green]✓[/green] Successfully installed {success_count} skill(s) {scope_display}."
            )

        if failed_count > 0:
            console.print(
                f"[red]✗[/red] Failed to install {failed_count} skill(s)."
            )
            if errors:
                console.print("\n[bold]Errors:[/bold]")
                for error in errors:
                    console.print(f"  • [red]{error}[/red]")

        if success_count == 0 and failed_count == 0:
            console.print("[yellow]No skills were installed.[/yellow]")
