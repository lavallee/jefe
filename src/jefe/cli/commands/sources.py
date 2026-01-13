"""Skill sources CLI commands."""

from datetime import datetime
from typing import Any

import anyio
import httpx
import typer
from rich.console import Console
from rich.table import Table

from jefe.cli.cache.manager import CacheManager
from jefe.cli.client import create_client, get_api_key, get_server_url, is_online

sources_app = typer.Typer(name="sources", help="Manage skill sources")
console = Console()
DESCRIPTION_OPTION = typer.Option(None, "--description", help="Optional description")


def _require_api_key() -> None:
    if not get_api_key():
        console.print("[red]API key not configured.[/red] Set it with:")
        console.print("  sc config set api_key <key>")
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


def _fail_request(action: str, response: httpx.Response) -> None:
    console.print(f"[red]Failed to {action} ({response.status_code}).[/red]")
    if response.text:
        console.print(response.text)
    raise typer.Exit(code=1)


def _render_sources_table(sources: list[dict[str, Any]]) -> None:
    table = Table(title="Skill Sources", show_header=True, header_style="bold magenta")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Name", style="green")
    table.add_column("Type", style="yellow")
    table.add_column("URL", style="white")
    table.add_column("Status", style="blue")
    table.add_column("Last Synced", style="dim")

    for source in sources:
        last_synced = str(source.get("last_synced_at") or "-")
        status = str(source.get("sync_status", ""))

        # Color code status
        if status == "synced":
            status_display = f"[green]{status}[/green]"
        elif status == "error":
            status_display = f"[red]{status}[/red]"
        elif status == "syncing":
            status_display = f"[yellow]{status}[/yellow]"
        else:
            status_display = status

        table.add_row(
            str(source["id"]),
            str(source["name"]),
            str(source["source_type"]),
            str(source["url"]),
            status_display,
            last_synced,
        )

    console.print(table)


async def _resolve_source_id(client: httpx.AsyncClient, name_or_id: str) -> int:
    if name_or_id.isdigit():
        return int(name_or_id)

    response = await _request(client, "GET", "/api/sources")
    if response.status_code != 200:
        _fail_request("list sources", response)

    sources = response.json()
    for source in sources:
        if source.get("name") == name_or_id:
            return int(source["id"])

    console.print(f"[red]Source '{name_or_id}' not found.[/red]")
    raise typer.Exit(code=1)


@sources_app.command("list")
def list_sources() -> None:
    """List all skill sources."""
    _require_api_key()
    anyio.run(_list_sources_async)


async def _list_sources_async() -> None:
    # Check if we're online
    online = await is_online()

    if not online:
        # Offline mode - show cached sources
        console.print("[yellow]⚠ Offline mode - showing cached data[/yellow]")
        cache = CacheManager()
        try:
            cached_sources = cache.get_all_sources()
            if not cached_sources:
                console.print("No cached sources available.")
                return

            # Convert to dict format for rendering
            sources = [
                {
                    "id": s.server_id or f"local-{s.id}",
                    "name": s.name,
                    "source_type": s.source_type,
                    "url": s.url,
                    "sync_status": s.sync_status,
                    "last_synced_at": s.last_synced_at,
                }
                for s in cached_sources
            ]
            _render_sources_table(sources)
        finally:
            cache.close()
        return

    async with create_client() as client:
        response = await _request(client, "GET", "/api/sources")

    if response.status_code != 200:
        _fail_request("list sources", response)

    sources = response.json()
    if not sources:
        console.print("No sources configured.")
        return

    # Cache the sources
    cache = CacheManager()
    try:
        for source in sources:
            last_synced_at = None
            if source.get("last_synced_at"):
                last_synced_at = datetime.fromisoformat(source["last_synced_at"].replace("Z", "+00:00"))
            cache.cache_source(
                server_id=source["id"],
                name=source["name"],
                source_type=source["source_type"],
                url=source["url"],
                description=source.get("description"),
                sync_status=source.get("sync_status"),
                last_synced_at=last_synced_at,
            )
    finally:
        cache.close()

    _render_sources_table(sources)


@sources_app.command("add")
def add_source(
    name: str = typer.Argument(..., help="Source name"),
    url: str = typer.Argument(..., help="Git repository URL"),
    description: str | None = DESCRIPTION_OPTION,
) -> None:
    """Add a new skill source."""
    _require_api_key()
    anyio.run(_add_source_async, name, url, description)


async def _add_source_async(
    name: str,
    url: str,
    description: str | None,
) -> None:
    # Check if we're online
    online = await is_online()

    if not online:
        # Offline mode - create locally for later sync
        console.print("[yellow]⚠ Offline mode - creating source locally[/yellow]")
        cache = CacheManager()
        try:
            cached_source = cache.create_source_offline(name, url, "git", description)
            console.print(f"Created source '{name}' locally (cache_id={cached_source.id}).")
            console.print("[dim]Note: Run 'jefe sync push' when online to sync to server.[/dim]")
            console.print("[yellow]⚠ Source sync requires server connection.[/yellow]")
        except ValueError as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(code=1) from e
        finally:
            cache.close()
        return

    payload: dict[str, object] = {
        "name": name,
        "source_type": "git",
        "url": url,
        "description": description,
    }

    async with create_client() as client:
        response = await _request(client, "POST", "/api/sources", json=payload)

    if response.status_code != 201:
        _fail_request("create source", response)

    source = response.json()

    # Cache the created source
    cache = CacheManager()
    try:
        cache.cache_source(
            server_id=source["id"],
            name=source["name"],
            source_type=source["source_type"],
            url=source["url"],
            description=source.get("description"),
            sync_status=source.get("sync_status"),
        )
    finally:
        cache.close()

    console.print(f"[green]Created source {source['name']} (id={source['id']}).[/green]")
    console.print(f"Run [cyan]jefe sources sync {source['name']}[/cyan] to fetch skills.")


@sources_app.command("sync")
def sync_sources(
    name_or_id: str | None = typer.Argument(None, help="Source name or id (syncs all if omitted)"),
) -> None:
    """Sync skill sources to fetch latest skills."""
    _require_api_key()
    anyio.run(_sync_sources_async, name_or_id)


async def _sync_sources_async(name_or_id: str | None) -> None:
    async with create_client() as client:
        if name_or_id is None:
            # Sync all sources
            response = await _request(client, "GET", "/api/sources")
            if response.status_code != 200:
                _fail_request("list sources", response)

            sources = response.json()
            if not sources:
                console.print("No sources to sync.")
                return

            console.print(f"Syncing {len(sources)} source(s)...")

            failed = []
            for source in sources:
                source_id = source["id"]
                source_name = source["name"]

                console.print(f"\n[cyan]Syncing {source_name}...[/cyan]")
                sync_response = await _request(
                    client, "POST", f"/api/sources/{source_id}/sync"
                )

                if sync_response.status_code == 200:
                    result = sync_response.json()
                    console.print(f"[green]✓[/green] {result['message']}")
                    console.print(f"  Skills updated: {result['skills_updated']}")
                else:
                    failed.append(source_name)
                    console.print(f"[red]✗[/red] Sync failed ({sync_response.status_code})")
                    if sync_response.text:
                        console.print(f"  {sync_response.text}")

            if failed:
                console.print(f"\n[yellow]Failed to sync:[/yellow] {', '.join(failed)}")
            else:
                console.print("\n[green]All sources synced successfully![/green]")
        else:
            # Sync specific source
            source_id = await _resolve_source_id(client, name_or_id)

            console.print("[cyan]Syncing source...[/cyan]")
            response = await _request(client, "POST", f"/api/sources/{source_id}/sync")

            if response.status_code != 200:
                _fail_request("sync source", response)

            result = response.json()
            console.print(f"[green]✓[/green] {result['message']}")
            console.print(f"Skills updated: {result['skills_updated']}")


@sources_app.command("remove")
def remove_source(
    name_or_id: str = typer.Argument(..., help="Source name or id"),
) -> None:
    """Remove a skill source."""
    _require_api_key()
    anyio.run(_remove_source_async, name_or_id)


async def _remove_source_async(name_or_id: str) -> None:
    async with create_client() as client:
        source_id = await _resolve_source_id(client, name_or_id)
        response = await _request(client, "DELETE", f"/api/sources/{source_id}")

    if response.status_code != 204:
        _fail_request("delete source", response)

    console.print(f"[green]Removed source {name_or_id}.[/green]")
