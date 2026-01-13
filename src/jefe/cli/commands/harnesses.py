"""Harness discovery CLI commands."""

import typer
from rich.console import Console
from rich.table import Table

from jefe.cli.api import create_client, get_api_key

harnesses_app = typer.Typer(name="harnesses", help="Discover harness configs")
console = Console()


def _require_api_key() -> None:
    if not get_api_key():
        console.print("[red]API key not configured.[/red] Set it with:")
        console.print("  jefe config set api_key <key>")
        raise typer.Exit(code=1)


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
    with create_client() as client:
        response = client.post("/api/harnesses/discover")

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
    params = {"project_id": project_id} if project_id is not None else None
    with create_client() as client:
        response = client.get(f"/api/harnesses/{harness_name}/configs", params=params)

    if response.status_code != 200:
        console.print(f"[red]Failed to load configs ({response.status_code}).[/red]")
        if response.text:
            console.print(response.text)
        raise typer.Exit(code=1)

    _render_configs(response.json())
