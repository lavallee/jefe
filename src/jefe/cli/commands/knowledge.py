"""Knowledge CLI commands."""

from typing import Any

import anyio
import httpx
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from jefe.cli.client import create_client, get_api_key, get_server_url, is_online

knowledge_app = typer.Typer(name="knowledge", help="Manage knowledge base entries")
console = Console()


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


def _render_entries_table(entries: list[dict[str, Any]]) -> None:
    """Render knowledge entries in a table."""
    table = Table(title="Knowledge Entries", show_header=True, header_style="bold magenta")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Title", style="green")
    table.add_column("Tags", style="yellow")
    table.add_column("Summary", style="dim")

    for entry in entries:
        tags_str = ", ".join(entry.get("tags", [])) if entry.get("tags") else "-"
        summary = entry.get("summary", "")[:60]
        if len(entry.get("summary", "")) > 60:
            summary += "..."

        table.add_row(
            str(entry["id"]),
            str(entry.get("title", "-")),
            tags_str,
            summary,
        )

    console.print(table)


def _render_entry_detail(entry: dict[str, Any]) -> None:
    """Render detailed entry information in a panel."""
    tags_str = ", ".join(entry.get("tags", [])) if entry.get("tags") else "None"

    lines = [
        f"[bold cyan]ID:[/bold cyan] {entry['id']}",
        f"[bold green]Title:[/bold green] {entry.get('title', '-')}",
        f"[bold blue]URL:[/bold blue] {entry.get('source_url', '-')}",
        f"[bold yellow]Tags:[/bold yellow] {tags_str}",
        "",
        "[bold magenta]Summary:[/bold magenta]",
        f"{entry.get('summary', 'No summary available')}",
    ]

    # Include full content if available
    if "content" in entry:
        lines.extend([
            "",
            "[bold magenta]Full Content:[/bold magenta]",
            f"{entry['content'][:500]}{'...' if len(entry.get('content', '')) > 500 else ''}",
        ])

    content = "\n".join(lines)
    console.print(Panel(content, title=f"Knowledge Entry {entry['id']}", border_style="green"))


@knowledge_app.command("ingest")
def ingest_url(
    url: str = typer.Argument(..., help="URL to ingest into knowledge base"),
    content_type: str = typer.Option(None, "--content-type", help="Content type hint (html/markdown)"),
) -> None:
    """Ingest a URL into the knowledge base.

    Fetches the URL, extracts content, generates a summary and tags using AI,
    and stores it in the knowledge base.
    """
    _require_api_key()
    anyio.run(_ingest_url_async, url, content_type)


async def _ingest_url_async(url: str, content_type: str | None) -> None:
    """Async implementation of ingest command."""
    online = await is_online()

    if not online:
        console.print("[red]Cannot ingest URLs while offline.[/red]")
        console.print("Please connect to the server and try again.")
        raise typer.Exit(code=1)

    async with create_client() as client:
        console.print(f"[cyan]Ingesting URL:[/cyan] {url}")

        # Prepare request payload
        payload: dict[str, Any] = {"source_url": url}
        if content_type:
            payload["content_type"] = content_type

        # Call the ingest API endpoint
        response = await _request(
            client,
            "POST",
            "/api/knowledge/ingest",
            json=payload,
        )

        if response.status_code == 200:
            entry = response.json()
            console.print(f"[green]✓[/green] Successfully ingested entry {entry['id']}")
            _render_entry_detail(entry)
        else:
            _fail_request("ingest URL", response)


@knowledge_app.command("search")
def search_entries(
    query: str = typer.Argument(None, help="Search query text"),
    tags: str = typer.Option(None, "--tags", help="Comma-separated tags to filter by"),
    limit: int = typer.Option(20, "--limit", help="Maximum number of results"),
) -> None:
    """Search knowledge base entries.

    Search by query text and/or filter by tags. Returns matching entries
    with their summaries.
    """
    _require_api_key()
    anyio.run(_search_entries_async, query, tags, limit)


async def _search_entries_async(query: str | None, tags_str: str | None, limit: int) -> None:
    """Async implementation of search command."""
    online = await is_online()

    if not online:
        console.print("[red]Cannot search while offline.[/red]")
        console.print("Please connect to the server and try again.")
        raise typer.Exit(code=1)

    async with create_client() as client:
        # Build query parameters
        params: dict[str, Any] = {"limit": limit}
        if query:
            params["q"] = query
        if tags_str:
            params["tags"] = tags_str

        # Call the search API endpoint
        response = await _request(
            client,
            "GET",
            "/api/knowledge",
            params=params,
        )

        if response.status_code == 200:
            entries = response.json()

            if not entries:
                console.print("[yellow]No entries found.[/yellow]")
                return

            console.print(f"[green]Found {len(entries)} entries[/green]")
            _render_entries_table(entries)
        else:
            _fail_request("search entries", response)


@knowledge_app.command("show")
def show_entry(
    entry_id: int = typer.Argument(..., help="Entry ID to display"),
) -> None:
    """Show detailed information about a knowledge entry.

    Displays the full content, summary, tags, and metadata for a specific entry.
    """
    _require_api_key()
    anyio.run(_show_entry_async, entry_id)


async def _show_entry_async(entry_id: int) -> None:
    """Async implementation of show command."""
    online = await is_online()

    if not online:
        console.print("[red]Cannot show entry details while offline.[/red]")
        console.print("Please connect to the server and try again.")
        raise typer.Exit(code=1)

    async with create_client() as client:
        # Call the get entry API endpoint
        response = await _request(
            client,
            "GET",
            f"/api/knowledge/{entry_id}",
        )

        if response.status_code == 200:
            entry = response.json()
            _render_entry_detail(entry)
        elif response.status_code == 404:
            console.print(f"[red]Entry {entry_id} not found.[/red]")
            raise typer.Exit(code=1)
        else:
            _fail_request(f"get entry {entry_id}", response)
