"""Harness discovery CLI commands."""

from typing import Any

import anyio
import httpx
import typer
from rich.console import Console
from rich.table import Table

from jefe.cli.client import create_client, get_api_key, get_server_url

harnesses_app = typer.Typer(name="harnesses", help="Discover harness configs")
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


def _render_configs(configs: list[dict[str, object]]) -> None:
    if not configs:
        console.print("No configs discovered.")
        return

    table = Table(title="Harness Configs", show_header=True, header_style="bold magenta")
    table.add_column("Harness", style="cyan", no_wrap=True)
    table.add_column("Scope", style="green")
    table.add_column("Kind", style="yellow")
    table.add_column("Path", style="white")
    table.add_column("Project", style="dim")

    for config in configs:
        project_label = str(config.get("project_name") or "-")
        table.add_row(
            str(config.get("harness", "")),
            str(config.get("scope", "")),
            str(config.get("kind", "")),
            str(config.get("path", "")),
            project_label,
        )

    console.print(table)


@harnesses_app.command("discover")
def discover_configs() -> None:
    """Discover configs for all harnesses."""
    _require_api_key()
    anyio.run(_discover_configs_async)


async def _discover_configs_async() -> None:
    async with create_client() as client:
        response = await _request(client, "POST", "/api/harnesses/discover")

    if response.status_code != 200:
        console.print(f"[red]Failed to discover configs ({response.status_code}).[/red]")
        if response.text:
            console.print(response.text)
        raise typer.Exit(code=1)

    _render_configs(response.json())


@harnesses_app.command("show")
def show_harness(
    harness_name: str = typer.Argument(..., help="Harness name (e.g. claude-code)"),
    project_id: int | None = typer.Option(None, "--project-id", help="Filter by project id"),
) -> None:
    """Show configs for a specific harness."""
    _require_api_key()
    anyio.run(_show_harness_async, harness_name, project_id)


async def _show_harness_async(harness_name: str, project_id: int | None) -> None:
    params = {"project_id": project_id} if project_id is not None else None
    async with create_client() as client:
        response = await _request(
            client,
            "GET",
            f"/api/harnesses/{harness_name}/configs",
            params=params,
        )

    if response.status_code != 200:
        console.print(f"[red]Failed to load configs ({response.status_code}).[/red]")
        if response.text:
            console.print(response.text)
        raise typer.Exit(code=1)

    _render_configs(response.json())
