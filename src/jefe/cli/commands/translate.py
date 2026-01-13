"""Translation CLI commands."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import anyio
import httpx
import typer
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from jefe.cli.client import create_client, get_api_key, get_server_url

translate_app = typer.Typer(name="translate", help="Translate configs between harnesses")
console = Console()


def _require_api_key() -> None:
    """Check that API key is configured."""
    if not get_api_key():
        console.print("[red]API key not configured.[/red] Set it with:")
        console.print("  sc config set api_key <key>")
        raise typer.Exit(code=1)


async def _request(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    **kwargs: object,
) -> httpx.Response:
    """Make an HTTP request with error handling."""
    try:
        return await client.request(method, url, **kwargs)  # type: ignore[arg-type]
    except httpx.RequestError as exc:
        console.print(f"[red]Unable to reach server at {get_server_url()}.[/red]")
        console.print(f"[dim]{exc}[/dim]")
        raise typer.Exit(code=1) from exc


def _fail_request(action: str, response: httpx.Response) -> None:
    """Handle failed HTTP requests."""
    console.print(f"[red]Failed to {action} ({response.status_code}).[/red]")
    if response.text:
        try:
            error_data = response.json()
            if "detail" in error_data:
                console.print(f"[red]{error_data['detail']}[/red]")
            else:
                console.print(response.text)
        except Exception:
            console.print(response.text)
    raise typer.Exit(code=1)


def _render_diff(diff: str) -> None:
    """Render diff output with syntax highlighting."""
    if not diff:
        console.print("[yellow]No changes detected[/yellow]")
        return

    syntax = Syntax(diff, "diff", theme="monokai", line_numbers=False)
    console.print(Panel(syntax, title="Changes Preview", expand=False))


def _confirm_apply(prompt: str = "Apply these changes?") -> bool:
    """Prompt user for confirmation."""
    return typer.confirm(prompt, default=False)


@translate_app.command(name="file")
def translate_file(
    file_path: Annotated[Path, typer.Argument(help="File to translate", metavar="FILE")],
    from_harness: Annotated[str, typer.Option("--from", help="Source harness")] = "",
    to_harness: Annotated[str, typer.Option("--to", help="Target harness")] = "",
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Show translation without applying")
    ] = False,
    output: Annotated[
        Path | None, typer.Option("--output", help="Write to different file")
    ] = None,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation")] = False,
) -> None:
    """Translate a config file between harness formats.

    Examples:
        sc translate file CLAUDE.md --from claude-code --to codex-cli
        sc translate file CLAUDE.md --from claude-code --to gemini-cli --dry-run
        sc translate file CLAUDE.md --from claude-code --to codex-cli --output AGENTS.md
    """
    _require_api_key()

    # Validate file exists
    if not file_path.exists():
        console.print(f"[red]File not found:[/red] {file_path}")
        raise typer.Exit(code=1)

    # Validate harness names
    if not from_harness:
        console.print("[red]Missing required option:[/red] --from")
        raise typer.Exit(code=1)
    if not to_harness:
        console.print("[red]Missing required option:[/red] --to")
        raise typer.Exit(code=1)

    anyio.run(_translate_file, file_path, from_harness, to_harness, dry_run, output, yes)


async def _translate_file(
    file: Path,
    from_harness: str,
    to_harness: str,
    dry_run: bool,
    output: Path | None,
    yes: bool,
) -> None:
    """Async implementation of file translation."""
    # Read file content
    try:
        content = file.read_text(encoding="utf-8")
    except Exception as e:
        console.print(f"[red]Failed to read file:[/red] {e}")
        raise typer.Exit(code=1) from e

    # Determine config kind from file name
    config_kind = "instructions"
    file_name = file.name.upper()
    if any(name in file_name for name in ["SETTING", "CONFIG", ".TOML", ".JSON"]):
        config_kind = "settings"

    # Call translation API
    async with create_client() as client:
        response = await _request(
            client,
            "POST",
            "/api/translate",
            json={
                "content": content,
                "source_harness": from_harness,
                "target_harness": to_harness,
                "config_kind": config_kind,
            },
        )

    if response.status_code != 200:
        _fail_request("translate", response)

    result = response.json()
    translated_content = result["output"]
    diff = result["diff"]
    log_id = result["log_id"]

    # Show diff
    console.print(f"\n[cyan]Translating:[/cyan] {file}")
    console.print(f"[cyan]From:[/cyan] {from_harness}")
    console.print(f"[cyan]To:[/cyan] {to_harness}")
    console.print(f"[dim]Translation log ID: {log_id}[/dim]\n")

    _render_diff(diff)

    # Handle dry-run
    if dry_run:
        console.print("\n[yellow]Dry run - no changes applied[/yellow]")
        return

    # Determine output file
    output_file = output if output else file

    # Confirm before applying
    if not yes and not _confirm_apply(f"Apply changes to {output_file}?"):
        console.print("[yellow]Cancelled[/yellow]")
        return

    # Apply translation
    try:
        output_file.write_text(translated_content, encoding="utf-8")
        console.print(f"\n[green]✓[/green] Translation applied to {output_file}")
    except Exception as e:
        console.print(f"[red]Failed to write file:[/red] {e}")
        raise typer.Exit(code=1) from e


@translate_app.command()
def history(
    limit: Annotated[int, typer.Option("--limit", "-n", help="Number of logs to show")] = 10,
) -> None:
    """Show recent translations.

    Examples:
        sc translate history
        sc translate history --limit 20
    """
    _require_api_key()
    anyio.run(_show_history, limit)


async def _show_history(limit: int) -> None:
    """Async implementation of history command."""
    async with create_client() as client:
        response = await _request(
            client,
            "GET",
            "/api/translate/log",
            params={"limit": limit},
        )

    if response.status_code != 200:
        _fail_request("get translation history", response)

    logs = response.json()

    if not logs:
        console.print("[yellow]No translation history found[/yellow]")
        return

    table = Table(
        title=f"Recent Translations (showing {len(logs)})",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("ID", style="dim", width=8)
    table.add_column("Model", style="cyan", width=30)
    table.add_column("Type", style="yellow", width=10)
    table.add_column("Date", style="green", width=20)
    table.add_column("Input Length", style="white", justify="right", width=12)

    for log in logs:
        model_name = log["model_name"]
        translation_type = log["translation_type"]
        created_at = log["created_at"]
        input_length = len(log["input_text"])

        # Format date
        date_part = created_at.split("T")[0] if "T" in created_at else created_at[:10]

        table.add_row(
            str(log["id"]),
            model_name,
            translation_type,
            date_part,
            str(input_length),
        )

    console.print(table)
