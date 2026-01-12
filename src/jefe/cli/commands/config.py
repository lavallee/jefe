"""Configuration management commands."""

import typer
from rich.console import Console
from rich.table import Table

from jefe.cli.config import (
    get_config_file,
    load_config,
    set_config_value,
)

config_app = typer.Typer(
    name="config",
    help="Manage CLI configuration",
)
console = Console()


@config_app.command("show")
def config_show() -> None:
    """Display current configuration."""
    config = load_config()

    if not config:
        console.print("[yellow]No configuration found.[/yellow]")
        console.print(f"Config file: [dim]{get_config_file()}[/dim]")
        return

    # Create a table for nice output
    table = Table(title="Station Chief Configuration", show_header=True, header_style="bold magenta")
    table.add_column("Key", style="cyan", no_wrap=True)
    table.add_column("Value", style="green")

    for key, value in sorted(config.items()):
        table.add_row(key, str(value))

    console.print(table)
    console.print(f"\nConfig file: [dim]{get_config_file()}[/dim]")


@config_app.command("set")
def config_set(
    key: str = typer.Argument(..., help="Configuration key to set"),
    value: str = typer.Argument(..., help="Value to set"),
) -> None:
    """Set a configuration value.

    Examples:
        sc config set server_url http://localhost:8000
        sc config set api_key abc123
    """
    set_config_value(key, value)
    console.print(f"[green]✓[/green] Set [cyan]{key}[/cyan] = [green]{value}[/green]")
    console.print(f"Config file: [dim]{get_config_file()}[/dim]")
