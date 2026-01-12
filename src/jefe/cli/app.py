"""Main CLI application using Typer."""

import typer
from rich.console import Console

from jefe import __version__
from jefe.cli.commands.config import config_app

app = typer.Typer(
    name="station-chief",
    help="Station Chief - A comprehensive Git repository management system",
    add_completion=False,
)
console = Console()

# Register subcommands
app.add_typer(config_app, name="config")


def version_callback(value: bool) -> None:
    """Show version information."""
    if value:
        console.print(f"Station Chief version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        help="Show version and exit",
        callback=version_callback,
        is_eager=True,
    )
) -> None:
    """Station Chief CLI - Manage Git repositories with ease."""
    pass


if __name__ == "__main__":
    app()
