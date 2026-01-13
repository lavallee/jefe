"""Sync CLI commands for manual sync control."""

from typing import Any

import anyio
import typer
from rich.console import Console
from rich.table import Table

from jefe.cli.cache.manager import CacheManager
from jefe.cli.client import get_api_key, get_server_url, is_online
from jefe.cli.sync.protocol import SyncProtocol

sync_app = typer.Typer(name="sync", help="Manage synchronization")
console = Console()


def _require_api_key() -> None:
    if not get_api_key():
        console.print("[red]API key not configured.[/red] Set it with:")
        console.print("  jefe config set api_key <key>")
        raise typer.Exit(code=1)


def _render_conflicts(result: Any) -> None:
    """Render sync conflicts table."""
    if not result.had_conflicts:
        return

    table = Table(title="Conflicts", show_header=True, header_style="bold yellow")
    table.add_column("Entity Type", style="cyan")
    table.add_column("Local ID", style="white")
    table.add_column("Server ID", style="white")
    table.add_column("Resolution", style="green")

    for conflict in result.conflicts:
        resolution_display = (
            "Local Wins" if conflict.resolution.value == "local_wins" else "Server Wins"
        )
        table.add_row(
            conflict.entity_type.value,
            str(conflict.local_id),
            str(conflict.server_id),
            resolution_display,
        )

    console.print(table)


def _render_dirty_items(
    projects: list[Any],
    skills: list[Any],
    installed: list[Any],
    configs: list[Any],
) -> None:
    """Render pending changes table."""
    total = len(projects) + len(skills) + len(installed) + len(configs)

    if total == 0:
        console.print("[green]No pending changes.[/green]")
        return

    table = Table(title="Pending Changes", show_header=True, header_style="bold yellow")
    table.add_column("Entity Type", style="cyan")
    table.add_column("Count", style="white")
    table.add_column("Items", style="dim")

    if projects:
        items = ", ".join([p.name for p in projects[:3]])
        if len(projects) > 3:
            items += f", ... (+{len(projects) - 3} more)"
        table.add_row("Projects", str(len(projects)), items)

    if skills:
        items = ", ".join([s.name for s in skills[:3]])
        if len(skills) > 3:
            items += f", ... (+{len(skills) - 3} more)"
        table.add_row("Skills", str(len(skills)), items)

    if installed:
        items = ", ".join([str(i.id) for i in installed[:3]])
        if len(installed) > 3:
            items += f", ... (+{len(installed) - 3} more)"
        table.add_row("Installed Skills", str(len(installed)), items)

    if configs:
        items = ", ".join([c.kind for c in configs[:3]])
        if len(configs) > 3:
            items += f", ... (+{len(configs) - 3} more)"
        table.add_row("Harness Configs", str(len(configs)), items)

    console.print(table)
    console.print(f"\n[yellow]Total pending changes: {total}[/yellow]")


@sync_app.command("status")
def sync_status() -> None:
    """Show sync status and pending changes."""
    _require_api_key()
    anyio.run(_sync_status_async)


async def _sync_status_async() -> None:
    """Show pending changes that need to be synced."""
    online = await is_online()

    if not online:
        console.print(
            f"[red]Unable to reach server at {get_server_url()}.[/red]"
        )
        console.print("[yellow]Status: Offline[/yellow]")
        return

    console.print(f"[green]Server: {get_server_url()}[/green]")
    console.print("[green]Status: Online[/green]\n")

    # Get dirty items from cache
    cache = CacheManager()
    try:
        dirty_projects, dirty_skills, dirty_installed, dirty_configs = (
            cache.get_all_dirty_items()
        )
        _render_dirty_items(dirty_projects, dirty_skills, dirty_installed, dirty_configs)
    finally:
        cache.close()


@sync_app.command("push")
def sync_push() -> None:
    """Push local changes to server."""
    _require_api_key()
    anyio.run(_sync_push_async)


async def _sync_push_async() -> None:
    """Push dirty items to the server."""
    online = await is_online()

    if not online:
        console.print(
            f"[red]Unable to reach server at {get_server_url()}.[/red]"
        )
        console.print("Cannot push changes while offline.")
        raise typer.Exit(code=1)

    console.print("[cyan]Pushing local changes...[/cyan]")

    protocol = SyncProtocol()
    try:
        result = await protocol.push()

        if result.success:
            if result.pushed == 0:
                console.print("[green]No changes to push.[/green]")
            else:
                console.print(f"[green]✓ Pushed {result.pushed} items.[/green]")

            if result.had_conflicts:
                console.print("\n[yellow]Conflicts detected:[/yellow]")
                _render_conflicts(result)
        else:
            console.print("[red]✗ Push failed.[/red]")
            if result.error_message:
                console.print(f"[dim]{result.error_message}[/dim]")
            raise typer.Exit(code=1)
    finally:
        protocol.close()


@sync_app.command("pull")
def sync_pull() -> None:
    """Pull server changes to local cache."""
    _require_api_key()
    anyio.run(_sync_pull_async)


async def _sync_pull_async() -> None:
    """Pull changes from the server."""
    online = await is_online()

    if not online:
        console.print(
            f"[red]Unable to reach server at {get_server_url()}.[/red]"
        )
        console.print("Cannot pull changes while offline.")
        raise typer.Exit(code=1)

    console.print("[cyan]Pulling server changes...[/cyan]")

    protocol = SyncProtocol()
    try:
        result = await protocol.pull()

        if result.success:
            if result.pulled == 0:
                console.print("[green]No new changes from server.[/green]")
            else:
                console.print(f"[green]✓ Pulled {result.pulled} items.[/green]")

            if result.had_conflicts:
                console.print("\n[yellow]Conflicts detected:[/yellow]")
                _render_conflicts(result)
        else:
            console.print("[red]✗ Pull failed.[/red]")
            if result.error_message:
                console.print(f"[dim]{result.error_message}[/dim]")
            raise typer.Exit(code=1)
    finally:
        protocol.close()


@sync_app.callback(invoke_without_command=True)
def sync(ctx: typer.Context) -> None:
    """Perform full bidirectional sync (push then pull)."""
    if ctx.invoked_subcommand is None:
        _require_api_key()
        anyio.run(_sync_async)


async def _sync_async() -> None:
    """Perform full sync operation."""
    online = await is_online()

    if not online:
        console.print(
            f"[red]Unable to reach server at {get_server_url()}.[/red]"
        )
        console.print("Cannot sync while offline.")
        raise typer.Exit(code=1)

    console.print("[cyan]Starting full sync...[/cyan]")

    protocol = SyncProtocol()
    try:
        result = await protocol.sync()

        if result.success:
            console.print("[green]✓ Sync complete.[/green]")

            if result.pushed > 0:
                console.print(f"  Pushed: {result.pushed} items")
            if result.pulled > 0:
                console.print(f"  Pulled: {result.pulled} items")

            if result.pushed == 0 and result.pulled == 0:
                console.print("  No changes to synchronize.")

            if result.had_conflicts:
                console.print("\n[yellow]Conflicts detected:[/yellow]")
                _render_conflicts(result)
        else:
            console.print("[red]✗ Sync failed.[/red]")
            if result.error_message:
                console.print(f"[dim]{result.error_message}[/dim]")
            raise typer.Exit(code=1)
    finally:
        protocol.close()
