"""Status CLI command."""

from typing import Any

import anyio
import httpx
import typer
from rich.console import Console
from rich.table import Table

from jefe.cli.client import create_client, get_api_key, get_server_url

status_app = typer.Typer(name="status", help="Show registry status")
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


@status_app.callback(invoke_without_command=True)
def show_status() -> None:
    """Show current project and config counts."""
    _require_api_key()
    anyio.run(_show_status_async)


async def _show_status_async() -> None:
    async with create_client() as client:
        response = await _request(client, "GET", "/api/status")

    if response.status_code != 200:
        console.print(f"[red]Failed to load status ({response.status_code}).[/red]")
        if response.text:
            console.print(response.text)
        raise typer.Exit(code=1)

    data = response.json()
    table = Table(title="Jefe Status", show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("Projects", str(data.get("projects", 0)))
    table.add_row("Manifestations", str(data.get("manifestations", 0)))
    table.add_row("Configs", str(data.get("configs", 0)))
    table.add_row("Harnesses", str(data.get("harnesses", 0)))
    console.print(table)
