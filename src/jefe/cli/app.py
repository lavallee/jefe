"""Main CLI application using Typer."""

import typer
from rich.console import Console

from jefe import __version__
from jefe.cli.commands.config import config_app
from jefe.cli.commands.harnesses import harnesses_app
from jefe.cli.commands.projects import projects_app
from jefe.cli.commands.skills import skills_app
from jefe.cli.commands.sources import sources_app
from jefe.cli.commands.status import status_app

app = typer.Typer(
    name="jefe",
    help="Jefe - A comprehensive Git repository management system",
    add_completion=False,
)
console = Console()

# Register subcommands
app.add_typer(config_app, name="config")
app.add_typer(projects_app, name="projects")
app.add_typer(harnesses_app, name="harnesses")
app.add_typer(sources_app, name="sources")
app.add_typer(skills_app, name="skills")
app.add_typer(status_app, name="status")


def version_callback(value: bool) -> None:
    """Show version information."""
    if value:
        console.print(f"Jefe version {__version__}")
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
    """Jefe CLI - Manage Git repositories with ease."""
    pass


if __name__ == "__main__":
    app()
