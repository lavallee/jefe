"""Harness discovery CLI commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import anyio
import httpx
import typer
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from jefe.cli.client import create_client, get_api_key, get_server_url

harnesses_app = typer.Typer(name="harnesses", help="View and discover harness configs")
console = Console()
PROJECT_OPTION = typer.Option(None, "--project", help="Limit discovery to a project path")


def _require_api_key() -> None:
    if not get_api_key():
        console.print("[red]API key not configured.[/red] Set it with:")
        console.print("  jefe config set api_key <key>")
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


def _render_harnesses(harnesses: list[dict[str, object]]) -> None:
    if not harnesses:
        console.print("No harnesses registered.")
        return

    table = Table(title="Harnesses", show_header=True, header_style="bold magenta")
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Display Name", style="green")
    table.add_column("Version", style="yellow")

    for harness in harnesses:
        table.add_row(
            str(harness.get("name", "")),
            str(harness.get("display_name", "")),
            str(harness.get("version", "")),
        )

    console.print(table)


def _render_harness_details(harness: dict[str, object]) -> None:
    table = Table(title="Harness Details", show_header=False)
    table.add_column("Field", style="cyan", no_wrap=True)
    table.add_column("Value", style="green")
    table.add_row("Name", str(harness.get("name", "")))
    table.add_row("Display Name", str(harness.get("display_name", "")))
    table.add_row("Version", str(harness.get("version", "")))
    console.print(table)


def _render_configs(configs: list[dict[str, object]], show_content: bool = False) -> None:
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

    if show_content:
        for config in configs:
            _render_config_content(config)


def _render_config_content(config: dict[str, object]) -> None:
    content = config.get("content")
    if content is None:
        return

    path = str(config.get("path", ""))
    lexer = _lexer_for_path(path)
    if isinstance(content, dict):
        payload = json.dumps(content, indent=2, sort_keys=True)
        lexer = "json"
    else:
        payload = str(content)

    syntax = Syntax(payload, lexer, line_numbers=False, word_wrap=True)
    title = f"{config.get('harness', 'config')}:{config.get('kind', '')}"
    console.print(Panel(syntax, title=title, expand=False))


def _lexer_for_path(path: str) -> str:
    suffix = Path(path).suffix.lower()
    return {
        ".json": "json",
        ".toml": "toml",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".md": "markdown",
        ".markdown": "markdown",
    }.get(suffix, "text")


async def _resolve_project_id_by_path(
    client: httpx.AsyncClient, project_path: Path
) -> int:
    response = await _request(client, "GET", "/api/projects")
    if response.status_code != 200:
        _fail_request("list projects", response)

    target = project_path.expanduser().resolve()
    for project in response.json():
        for manifestation in project.get("manifestations", []):
            if manifestation.get("type") != "local":
                continue
            manifest_path = Path(manifestation.get("path", "")).expanduser().resolve()
            if manifest_path == target:
                return int(project["id"])

    console.print(f"[red]No project found for path:[/red] {target}")
    raise typer.Exit(code=1)


@harnesses_app.command("list")
def list_harnesses() -> None:
    """List available harnesses."""
    _require_api_key()
    anyio.run(_list_harnesses_async)


async def _list_harnesses_async() -> None:
    async with create_client() as client:
        response = await _request(client, "GET", "/api/harnesses")

    if response.status_code != 200:
        _fail_request("list harnesses", response)

    _render_harnesses(response.json())


@harnesses_app.command("discover")
def discover_configs(
    project: Path | None = PROJECT_OPTION,
) -> None:
    """Discover configs for all harnesses."""
    _require_api_key()
    anyio.run(_discover_configs_async, project)


async def _discover_configs_async(project: Path | None) -> None:
    params: dict[str, int] | None = None
    async with create_client() as client:
        if project is not None:
            project_id = await _resolve_project_id_by_path(client, project)
            params = {"project_id": project_id}
        response = await _request(client, "POST", "/api/harnesses/discover", params=params)

    if response.status_code != 200:
        _fail_request("discover configs", response)

    _render_configs(response.json(), show_content=True)


@harnesses_app.command("show")
def show_harness(
    harness_name: str = typer.Argument(..., help="Harness name (e.g. claude-code)"),
    project_id: int | None = typer.Option(None, "--project-id", help="Filter by project id"),
) -> None:
    """Show harness details and configs."""
    _require_api_key()
    anyio.run(_show_harness_async, harness_name, project_id)


async def _show_harness_async(harness_name: str, project_id: int | None) -> None:
    async with create_client() as client:
        harness_response = await _request(client, "GET", f"/api/harnesses/{harness_name}")
        if harness_response.status_code != 200:
            _fail_request("load harness", harness_response)

        params = {"project_id": project_id} if project_id is not None else None
        config_response = await _request(
            client,
            "GET",
            f"/api/harnesses/{harness_name}/configs",
            params=params,
        )

    if config_response.status_code != 200:
        _fail_request("load configs", config_response)

    _render_harness_details(harness_response.json())
    _render_configs(config_response.json(), show_content=True)


@harnesses_app.command("adapters")
def list_available_adapters() -> None:
    """List available harness adapters."""
    from jefe.adapters import get_adapters

    adapters = get_adapters()

    if not adapters:
        console.print("[yellow]No adapters registered.[/yellow]")
        return

    table = Table(title="Available Adapters", show_header=True, header_style="bold magenta")
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Display Name", style="green")
    table.add_column("Version", style="yellow")

    for adapter in sorted(adapters, key=lambda a: a.name):
        table.add_row(adapter.name, adapter.display_name, adapter.version)

    console.print(table)
    console.print(f"\n[dim]Total: {len(adapters)} adapter(s)[/dim]")
