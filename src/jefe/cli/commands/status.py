"""Status CLI command."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any, cast

import anyio
import httpx
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from jefe.cli.client import create_client, get_api_key, get_server_url
from jefe.cli.config import get_config_value, set_config_value

status_app = typer.Typer(name="status", help="Show registry status")
console = Console()
CACHE_KEY = "status_cache"


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
        raise _OfflineError(str(exc)) from exc


def _fail_request(action: str, response: httpx.Response) -> None:
    console.print(f"[red]Failed to {action} ({response.status_code}).[/red]")
    if response.text:
        console.print(response.text)
    raise typer.Exit(code=1)


class _OfflineError(Exception):
    """Raised when the server cannot be reached."""


@status_app.callback(invoke_without_command=True)
def show_status(
    project: str | None = typer.Option(
        None, "--project", help="Project name or id for detailed status"
    )
) -> None:
    """Show current project and config counts."""
    _require_api_key()
    anyio.run(_show_status_async, project)


async def _show_status_async(project: str | None) -> None:
    try:
        data = await _collect_status_data(project)
        _save_cached_status(data)
        _render_status(data, project, offline=False, offline_message=None)
    except _OfflineError as exc:
        cached = _load_cached_status()
        if cached is None:
            console.print(f"[red]Unable to reach server at {get_server_url()}.[/red]")
            console.print(f"[dim]{exc}[/dim]")
            console.print("[dim]No cached status data available.[/dim]")
            raise typer.Exit(code=1) from exc
        _render_status(cached, project, offline=True, offline_message=str(exc))


async def _collect_status_data(project: str | None) -> dict[str, Any]:
    async with create_client() as client:
        health = await _request(client, "GET", "/health")
        status_response = await _request(client, "GET", "/api/status")
        projects_response = await _request(client, "GET", "/api/projects")
        harnesses_response = await _request(client, "GET", "/api/harnesses")

        if status_response.status_code != 200:
            _fail_request("load status", status_response)
        if projects_response.status_code != 200:
            _fail_request("list projects", projects_response)
        if harnesses_response.status_code != 200:
            _fail_request("list harnesses", harnesses_response)

        harnesses = harnesses_response.json()
        harness_configs: dict[str, list[dict[str, Any]]] = {}
        for harness in harnesses:
            name = str(harness.get("name", ""))
            if not name:
                continue
            config_response = await _request(client, "GET", f"/api/harnesses/{name}/configs")
            if config_response.status_code != 200:
                _fail_request(f"load configs for {name}", config_response)
            harness_configs[name] = config_response.json()

        project_details: dict[str, dict[str, Any]] = {}
        if project is not None:
            project_id = await _resolve_project_id(project, projects_response.json())
            detail_response = await _request(client, "GET", f"/api/projects/{project_id}")
            if detail_response.status_code != 200:
                _fail_request("load project", detail_response)
            project_details[str(project_id)] = detail_response.json()

    health_payload = health.json() if health.status_code == 200 else {}
    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "health": {
            "status_code": health.status_code,
            "payload": health_payload,
        },
        "overview": status_response.json(),
        "projects": projects_response.json(),
        "harnesses": harnesses,
        "harness_configs": harness_configs,
        "project_details": project_details,
    }


async def _resolve_project_id(name_or_id: str, projects: list[dict[str, Any]]) -> int:
    if name_or_id.isdigit():
        return int(name_or_id)

    for project in projects:
        if project.get("name") == name_or_id:
            return int(project["id"])

    console.print(f"[red]Project '{name_or_id}' not found.[/red]")
    raise typer.Exit(code=1)


def _load_cached_status() -> dict[str, Any] | None:
    cached = get_config_value(CACHE_KEY)
    if isinstance(cached, dict):
        return cast(dict[str, Any], cached)
    return None


def _save_cached_status(data: dict[str, Any]) -> None:
    set_config_value(CACHE_KEY, data)


def _render_status(
    data: dict[str, Any],
    project: str | None,
    *,
    offline: bool,
    offline_message: str | None,
) -> None:
    health = data.get("health", {})
    status_code = health.get("status_code", 0)
    payload = health.get("payload", {}) if isinstance(health, dict) else {}
    version = str(payload.get("version", "-"))
    status_label = "Online" if status_code == 200 else f"Unhealthy ({status_code})"
    if offline:
        status_label = "Offline (cached)"

    connection_table = Table(show_header=False)
    connection_table.add_column("Field", style="cyan", no_wrap=True)
    connection_table.add_column("Value", style="green")
    connection_table.add_row("Server", get_server_url())
    connection_table.add_row("Status", status_label)
    connection_table.add_row("Version", version)
    if offline:
        cached_at = str(data.get("timestamp", "-"))
        connection_table.add_row("Cached", cached_at)
    console.print(Panel(connection_table, title="Connection", border_style="bright_blue"))

    if offline:
        console.print("[yellow]Offline:[/yellow] showing cached data.")
        if offline_message:
            console.print(f"[dim]{offline_message}[/dim]")

    if project is not None:
        _render_project_status(data, project, offline=offline)
        return

    _render_overview(data.get("overview", {}))
    _render_harnesses(data.get("harnesses", []), data.get("harness_configs", {}))
    _render_recent_activity(data.get("projects", []))


def _render_overview(overview: dict[str, Any]) -> None:
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("Projects", str(overview.get("projects", 0)))
    table.add_row("Manifestations", str(overview.get("manifestations", 0)))
    table.add_row("Configs", str(overview.get("configs", 0)))
    table.add_row("Harnesses", str(overview.get("harnesses", 0)))
    console.print(Panel(table, title="Overview", border_style="magenta"))


def _render_harnesses(
    harnesses: list[dict[str, Any]],
    harness_configs: dict[str, list[dict[str, Any]]],
) -> None:
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Harness", style="cyan", no_wrap=True)
    table.add_column("Version", style="green")
    table.add_column("Configs", style="yellow", justify="right")
    table.add_column("Project", style="dim", justify="right")

    for harness in harnesses:
        name = str(harness.get("name", ""))
        configs = harness_configs.get(name, [])
        project_count = sum(1 for config in configs if config.get("scope") == "project")
        table.add_row(
            name,
            str(harness.get("version", "")),
            str(len(configs)),
            str(project_count),
        )

    console.print(Panel(table, title="Harnesses", border_style="magenta"))


def _render_recent_activity(projects: list[dict[str, Any]]) -> None:
    activity = list(_collect_recent_activity(projects))
    if not activity:
        console.print(Panel("No recent activity recorded.", title="Recent Activity"))
        return

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Project", style="cyan")
    table.add_column("Type", style="green")
    table.add_column("Path", style="white")
    table.add_column("Last Seen", style="yellow")
    for entry in activity:
        table.add_row(entry["project"], entry["type"], entry["path"], entry["last_seen"])

    console.print(Panel(table, title="Recent Activity", border_style="magenta"))


def _collect_recent_activity(
    projects: list[dict[str, Any]], limit: int = 5
) -> Iterable[dict[str, str]]:
    items: list[tuple[datetime, dict[str, str]]] = []
    for project in projects:
        project_name = str(project.get("name", ""))
        for manifestation in project.get("manifestations", []) or []:
            last_seen = manifestation.get("last_seen")
            if not last_seen:
                continue
            parsed = _parse_datetime(str(last_seen))
            if parsed is None:
                continue
            items.append(
                (
                    parsed,
                    {
                        "project": project_name,
                        "type": str(manifestation.get("type", "")),
                        "path": str(manifestation.get("path", "")),
                        "last_seen": str(last_seen),
                    },
                )
            )

    items.sort(key=lambda item: item[0], reverse=True)
    for _, entry in items[:limit]:
        yield entry


def _parse_datetime(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _render_project_status(data: dict[str, Any], project: str, *, offline: bool) -> None:
    details = _find_project_detail(data, project)
    if details is None:
        console.print(f"[red]No status data found for project '{project}'.[/red]")
        if offline:
            console.print("[dim]Refresh status when the server is online.[/dim]")
        raise typer.Exit(code=1)

    summary = Table(show_header=False)
    summary.add_column("Field", style="cyan", no_wrap=True)
    summary.add_column("Value", style="green")
    summary.add_row("Name", str(details.get("name", "")))
    summary.add_row("ID", str(details.get("id", "")))
    summary.add_row("Description", str(details.get("description") or "-"))
    manifestations = details.get("manifestations", []) or []
    configs = details.get("configs", []) or []
    summary.add_row("Manifestations", str(len(manifestations)))
    summary.add_row("Configs", str(len(configs)))
    console.print(Panel(summary, title="Project", border_style="magenta"))

    _render_project_configs(configs)
    _render_project_activity(details)


def _find_project_detail(data: dict[str, Any], project: str) -> dict[str, Any] | None:
    project_details = data.get("project_details", {})
    if isinstance(project_details, dict):
        for entry in project_details.values():
            if not isinstance(entry, dict):
                continue
            if str(entry.get("id")) == project or entry.get("name") == project:
                return cast(dict[str, Any], entry)

    for entry in data.get("projects", []) or []:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("id")) == project or entry.get("name") == project:
            return cast(dict[str, Any], entry)

    return None


def _render_project_configs(configs: list[dict[str, Any]]) -> None:
    if not configs:
        console.print(Panel("No configs discovered.", title="Project Configs"))
        return

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Harness", style="cyan")
    table.add_column("Scope", style="green")
    table.add_column("Kind", style="yellow")
    table.add_column("Path", style="white")
    for config in configs:
        table.add_row(
            str(config.get("harness", "")),
            str(config.get("scope", "")),
            str(config.get("kind", "")),
            str(config.get("path", "")),
        )
    console.print(Panel(table, title="Project Configs", border_style="magenta"))


def _render_project_activity(details: dict[str, Any]) -> None:
    manifestations = details.get("manifestations", []) or []
    project_name = details.get("name")
    activity = list(
        _collect_recent_activity([{"name": project_name, "manifestations": manifestations}])
    )
    if not activity:
        console.print(Panel("No recent activity recorded.", title="Project Activity"))
        return

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Type", style="cyan")
    table.add_column("Path", style="white")
    table.add_column("Last Seen", style="yellow")
    for entry in activity:
        table.add_row(entry["type"], entry["path"], entry["last_seen"])
    console.print(Panel(table, title="Project Activity", border_style="magenta"))
