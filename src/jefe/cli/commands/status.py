"""Status CLI command."""

import typer
from rich.console import Console
from rich.table import Table

from jefe.cli.api import create_client, get_api_key

status_app = typer.Typer(name="status", help="Show registry status")
console = Console()


def _require_api_key() -> None:
    if not get_api_key():
        console.print("[red]API key not configured.[/red] Set it with:")
        console.print("  jefe config set api_key <key>")
        raise typer.Exit(code=1)


@status_app.callback(invoke_without_command=True)
def show_status() -> None:
    """Show current project and config counts."""
    _require_api_key()
    with create_client() as client:
        response = client.get("/api/status")

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
