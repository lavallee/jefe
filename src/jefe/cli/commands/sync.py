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


@sync_app.command("conflicts")
def sync_conflicts() -> None:
    """List pending sync conflicts."""
    _require_api_key()
    anyio.run(_sync_conflicts_async)


async def _sync_conflicts_async() -> None:
    """List all unresolved conflicts."""
    cache = CacheManager()
    try:
        conflicts = cache.conflicts.get_unresolved()

        if not conflicts:
            console.print("[green]No pending conflicts.[/green]")
            return

        table = Table(title="Pending Conflicts", show_header=True, header_style="bold yellow")
        table.add_column("ID", style="cyan")
        table.add_column("Entity Type", style="white")
        table.add_column("Local ID", style="white")
        table.add_column("Server ID", style="white")
        table.add_column("Local Modified", style="dim")
        table.add_column("Server Modified", style="dim")

        for conflict in conflicts:
            local_time = conflict.local_updated_at.strftime("%Y-%m-%d %H:%M:%S")
            server_time = conflict.server_updated_at.strftime("%Y-%m-%d %H:%M:%S")
            table.add_row(
                str(conflict.id),
                conflict.entity_type.value,
                str(conflict.local_id),
                str(conflict.server_id),
                local_time,
                server_time,
            )

        console.print(table)
        console.print(f"\n[yellow]Total conflicts: {len(conflicts)}[/yellow]")
        console.print("\nUse [cyan]jefe sync resolve <id> --keep-local[/cyan] or")
        console.print("    [cyan]jefe sync resolve <id> --keep-server[/cyan] to resolve conflicts.")
    finally:
        cache.close()


@sync_app.command("resolve")
def sync_resolve(
    conflict_id: int = typer.Argument(..., help="Conflict ID to resolve"),
    keep_local: bool = typer.Option(False, "--keep-local", help="Keep local version"),
    keep_server: bool = typer.Option(False, "--keep-server", help="Keep server version"),
    interactive: bool = typer.Option(True, "--interactive/--no-interactive", help="Show diff and prompt for choice"),
) -> None:
    """Resolve a sync conflict."""
    _require_api_key()

    if keep_local and keep_server:
        console.print("[red]Error: Cannot specify both --keep-local and --keep-server.[/red]")
        raise typer.Exit(code=1)

    anyio.run(_sync_resolve_async, conflict_id, keep_local, keep_server, interactive)


def _show_conflict_details(conflict: Any, conflict_id: int) -> None:
    """Show conflict details and diff."""
    import json

    console.print(f"\n[bold]Conflict {conflict_id}:[/bold]")
    console.print(f"Entity Type: {conflict.entity_type.value}")
    console.print(f"Local ID: {conflict.local_id}")
    console.print(f"Server ID: {conflict.server_id}")
    console.print(f"Local Modified: {conflict.local_updated_at.strftime('%Y-%m-%d %H:%M:%S')}")
    console.print(f"Server Modified: {conflict.server_updated_at.strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Show diff if we have the data
    if conflict.local_data and conflict.server_data:
        local_data = json.loads(conflict.local_data)
        server_data = json.loads(conflict.server_data)

        console.print("[bold]Differences:[/bold]")
        for key in set(local_data.keys()) | set(server_data.keys()):
            local_val = local_data.get(key)
            server_val = server_data.get(key)
            if local_val != server_val:
                console.print(f"  {key}:")
                console.print(f"    [red]Local:[/red]  {local_val}")
                console.print(f"    [green]Server:[/green] {server_val}")

        console.print()


def _prompt_resolution() -> Any:
    """Prompt user to choose conflict resolution."""
    from jefe.cli.cache.models import ConflictResolutionType

    console.print("[yellow]Choose resolution:[/yellow]")
    console.print("  1. Keep local version")
    console.print("  2. Keep server version")
    choice = typer.prompt("Enter choice", type=int)

    if choice == 1:
        return ConflictResolutionType.LOCAL_WINS
    elif choice == 2:
        return ConflictResolutionType.SERVER_WINS
    else:
        console.print("[red]Invalid choice.[/red]")
        raise typer.Exit(code=1)


async def _sync_resolve_async(
    conflict_id: int, keep_local: bool, keep_server: bool, interactive: bool
) -> None:
    """Resolve a specific conflict."""
    from jefe.cli.cache.models import ConflictResolutionType

    cache = CacheManager()
    try:
        conflict = cache.conflicts.get_by_id(conflict_id)

        if not conflict:
            console.print(f"[red]Conflict {conflict_id} not found.[/red]")
            raise typer.Exit(code=1)

        if conflict.resolution != ConflictResolutionType.UNRESOLVED:
            console.print(f"[yellow]Conflict {conflict_id} is already resolved as {conflict.resolution.value}.[/yellow]")
            return

        # Show conflict details and diff
        _show_conflict_details(conflict, conflict_id)

        # Determine resolution
        resolution = None
        if keep_local:
            resolution = ConflictResolutionType.LOCAL_WINS
        elif keep_server:
            resolution = ConflictResolutionType.SERVER_WINS
        elif interactive:
            resolution = _prompt_resolution()

        if not resolution:
            console.print("[red]No resolution specified. Use --keep-local, --keep-server, or run in interactive mode.[/red]")
            raise typer.Exit(code=1)

        # Apply resolution
        cache.conflicts.resolve(conflict_id, resolution)

        resolution_text = "local" if resolution == ConflictResolutionType.LOCAL_WINS else "server"
        console.print(f"[green]✓ Conflict {conflict_id} resolved (keeping {resolution_text} version).[/green]")

        # Note: The actual data sync happens during next pull/push
        console.print("[dim]Note: Run 'jefe sync' to apply the resolution.[/dim]")
    finally:
        cache.close()


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
