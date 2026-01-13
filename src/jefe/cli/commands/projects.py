"""Project registry CLI commands."""

from pathlib import Path
from typing import Any

import anyio
import httpx
import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from jefe.cli.cache.manager import CacheManager
from jefe.cli.client import create_client, get_api_key, get_server_url, is_online

projects_app = typer.Typer(name="projects", help="Manage project registry")
console = Console()
PATH_OPTION = typer.Option(None, "--path", help="Local path to the project")
REMOTE_OPTION = typer.Option(None, "--remote", help="Remote repository URL")
DESCRIPTION_OPTION = typer.Option(None, "--description", help="Optional description")
RECIPE_OPTION = typer.Option(None, "--recipe", help="Path to recipe YAML file")


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


def _render_projects_table(projects: list[dict[str, Any]]) -> None:
    table = Table(title="Projects", show_header=True, header_style="bold magenta")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Name", style="green")
    table.add_column("Description", style="white")
    table.add_column("Manifestations", style="yellow")

    for project in projects:
        description = str(project.get("description") or "-")
        manifestations = project.get("manifestations")
        count = len(manifestations) if isinstance(manifestations, list) else 0
        table.add_row(
            str(project["id"]),
            str(project["name"]),
            description,
            str(count),
        )

    console.print(table)


def _render_manifestations(manifestations: list[dict[str, Any]]) -> None:
    if not manifestations:
        console.print("No manifestations registered.")
        return

    table = Table(title="Manifestations", show_header=True, header_style="bold magenta")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Type", style="green")
    table.add_column("Path", style="white")
    table.add_column("Machine", style="dim")
    table.add_column("Last Seen", style="yellow")

    for item in manifestations:
        table.add_row(
            str(item.get("id", "")),
            str(item.get("type", "")),
            str(item.get("path", "")),
            str(item.get("machine_id") or "-"),
            str(item.get("last_seen") or "-"),
        )

    console.print(table)


def _render_configs(configs: list[dict[str, Any]]) -> None:
    if not configs:
        console.print("No configs discovered.")
        return

    table = Table(title="Configs", show_header=True, header_style="bold magenta")
    table.add_column("Harness", style="cyan", no_wrap=True)
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

    console.print(table)


async def _resolve_project_id(client: httpx.AsyncClient, name_or_id: str) -> int:
    if name_or_id.isdigit():
        return int(name_or_id)

    response = await _request(client, "GET", "/api/projects")
    if response.status_code != 200:
        _fail_request("list projects", response)

    projects = response.json()
    for project in projects:
        if project.get("name") == name_or_id:
            return int(project["id"])

    console.print(f"[red]Project '{name_or_id}' not found.[/red]")
    raise typer.Exit(code=1)


@projects_app.command("list")
def list_projects() -> None:
    """List registered projects."""
    _require_api_key()
    anyio.run(_list_projects_async)


async def _list_projects_async() -> None:
    # Check if server is online
    online = await is_online()

    if not online:
        # Fall back to cache
        console.print("[yellow]⚠ Offline mode - showing cached data[/yellow]")
        cache = CacheManager()
        try:
            cached_projects = cache.get_all_projects()
            if not cached_projects:
                console.print("No cached projects available.")
                return

            # Convert cached projects to dict format for rendering
            projects: list[dict[str, Any]] = [
                {
                    "id": p.server_id,
                    "name": p.name,
                    "description": p.description,
                    "manifestations": [],  # Not cached yet
                }
                for p in cached_projects
            ]
            _render_projects_table(projects)
        finally:
            cache.close()
        return

    # Online - fetch from server
    async with create_client() as client:
        response = await _request(client, "GET", "/api/projects")

    if response.status_code != 200:
        _fail_request("list projects", response)

    projects = response.json()
    if not projects:
        console.print("No projects registered.")
        return

    # Cache the projects
    cache = CacheManager()
    try:
        for project in projects:
            cache.cache_project(
                server_id=project["id"],
                name=project["name"],
                description=project.get("description"),
            )
    finally:
        cache.close()

    _render_projects_table(projects)


@projects_app.command("add")
def add_project(
    name: str = typer.Argument(..., help="Project name"),
    path: Path | None = PATH_OPTION,
    remote: str | None = REMOTE_OPTION,
    description: str | None = DESCRIPTION_OPTION,
) -> None:
    """Register a new project."""
    _require_api_key()
    anyio.run(_add_project_async, name, path, remote, description)


async def _add_project_async(
    name: str,
    path: Path | None,
    remote: str | None,
    description: str | None,
) -> None:
    if path is not None and not path.exists():
        console.print(f"[red]Path does not exist:[/red] {path}")
        raise typer.Exit(code=1)

    # Check if we're online
    online = await is_online()

    if not online:
        # Offline mode - create locally for later sync
        console.print("[yellow]⚠ Offline mode - creating project locally[/yellow]")
        cache = CacheManager()
        try:
            cached_project = cache.create_project_offline(name, description)
            console.print(f"Created project '{name}' locally (cache_id={cached_project.id}).")
            console.print("[dim]Note: Run 'jefe sync push' when online to sync to server.[/dim]")
            if remote:
                console.print("[yellow]⚠ Remote URL saved but not registered (requires server)[/yellow]")
        except ValueError as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(code=1) from e
        finally:
            cache.close()
        return

    payload: dict[str, object] = {"name": name, "description": description}
    if path is not None:
        payload["path"] = str(path)

    async with create_client() as client:
        response = await _request(client, "POST", "/api/projects", json=payload)
        if response.status_code != 201:
            _fail_request("create project", response)

        project = response.json()

        if remote:
            manifest_payload = {"type": "remote", "path": remote}
            manifest_response = await _request(
                client,
                "POST",
                f"/api/projects/{project['id']}/manifestations",
                json=manifest_payload,
            )
            if manifest_response.status_code != 201:
                _fail_request("add remote", manifest_response)

    # Cache the created project
    cache = CacheManager()
    try:
        cache.cache_project(
            server_id=project["id"],
            name=project["name"],
            description=project.get("description"),
        )
    finally:
        cache.close()

    console.print(f"Created project {project['name']} (id={project['id']}).")
    if remote:
        console.print(f"Added remote {remote}.")


@projects_app.command("show")
def show_project(
    name_or_id: str = typer.Argument(..., help="Project name or id"),
) -> None:
    """Show project details."""
    _require_api_key()
    anyio.run(_show_project_async, name_or_id)


async def _show_project_async(name_or_id: str) -> None:
    # Check if server is online
    online = await is_online()

    if not online:
        # Fall back to cache
        console.print("[yellow]⚠ Offline mode - showing cached data[/yellow]")
        cache = CacheManager()
        try:
            # Try to find project in cache
            cached_project = None
            if name_or_id.isdigit():
                cached_project = cache.projects.get_by_server_id(int(name_or_id))
            else:
                cached_project = cache.get_project(name_or_id)

            if not cached_project:
                console.print(f"[red]Project '{name_or_id}' not found in cache.[/red]")
                console.print("Connect to server to see full project list.")
                raise typer.Exit(code=1)

            console.print(
                f"[bold]{cached_project.name}[/bold] (id={cached_project.server_id})"
            )
            if cached_project.description:
                console.print(cached_project.description)
            console.print(
                "[dim]Note: Manifestations and configs require server connection[/dim]"
            )
        finally:
            cache.close()
        return

    # Online - fetch from server
    async with create_client() as client:
        project_id = await _resolve_project_id(client, name_or_id)
        response = await _request(client, "GET", f"/api/projects/{project_id}")

    if response.status_code != 200:
        _fail_request("load project", response)

    project = response.json()

    # Cache the project
    cache = CacheManager()
    try:
        cache.cache_project(
            server_id=project["id"],
            name=project["name"],
            description=project.get("description"),
        )
    finally:
        cache.close()

    console.print(f"[bold]{project['name']}[/bold] (id={project['id']})")
    if project.get("description"):
        console.print(project["description"])
    _render_manifestations(project.get("manifestations", []))
    _render_configs(project.get("configs", []))


@projects_app.command("remove")
def remove_project(
    name_or_id: str = typer.Argument(..., help="Project name or id"),
) -> None:
    """Remove a project."""
    _require_api_key()
    anyio.run(_remove_project_async, name_or_id)


async def _remove_project_async(name_or_id: str) -> None:
    async with create_client() as client:
        project_id = await _resolve_project_id(client, name_or_id)
        response = await _request(client, "DELETE", f"/api/projects/{project_id}")

    if response.status_code != 204:
        _fail_request("delete project", response)

    console.print(f"Removed project {name_or_id}.")


RECIPE_REQUIRED = typer.Option(..., "--recipe", "-r", help="Path to recipe YAML file")
NAME_OPTION = typer.Option(None, "--name", "-n", help="Project name (defaults to current directory name)")
PATH_INIT_OPTION = typer.Option(None, "--path", "-p", help="Project path (defaults to current directory)")


@projects_app.command("init")
def init_project(
    recipe: Path = RECIPE_REQUIRED,
    name: str | None = NAME_OPTION,
    path: Path | None = PATH_INIT_OPTION,
    description: str | None = DESCRIPTION_OPTION,
) -> None:
    """Initialize a project with a recipe."""
    _require_api_key()
    anyio.run(_init_project_async, recipe, name, path, description)


async def _init_project_async(  # noqa: C901
    recipe_path: Path,
    name: str | None,
    path: Path | None,
    description: str | None,
) -> None:
    # Validate recipe file exists
    if not recipe_path.exists():
        console.print(f"[red]Recipe file not found:[/red] {recipe_path}")
        raise typer.Exit(code=1)

    # Determine project path and name
    project_path = path if path is not None else Path.cwd()
    if not project_path.exists():
        console.print(f"[red]Project path does not exist:[/red] {project_path}")
        raise typer.Exit(code=1)

    project_name = name if name is not None else project_path.name

    # Check if we're online
    online = await is_online()
    if not online:
        console.print("[red]Init command requires server connection.[/red]")
        console.print("Please start the Jefe server and try again.")
        raise typer.Exit(code=1)

    async with create_client() as client:
        # Step 1: Parse and load recipe
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Loading recipe...", total=None)

            # Read recipe content
            try:
                recipe_content = recipe_path.read_text()
            except OSError as e:
                console.print(f"[red]Failed to read recipe file:[/red] {e}")
                raise typer.Exit(code=1) from e

            # Parse recipe via API
            parse_response = await _request(
                client,
                "POST",
                "/api/recipes/parse",
                json={"content": recipe_content},
            )

            if parse_response.status_code != 200:
                _fail_request("parse recipe", parse_response)

            recipe_data = parse_response.json()
            progress.update(task, description=f"Loaded recipe: {recipe_data['name']}")

        console.print(f"[green]✓[/green] Recipe: {recipe_data['name']}")
        if recipe_data.get("description"):
            console.print(f"  {recipe_data['description']}")

        # Step 2: Check if project exists, create if not
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Checking project...", total=None)

            # Check if project exists
            projects_response = await _request(client, "GET", "/api/projects")
            if projects_response.status_code != 200:
                _fail_request("list projects", projects_response)

            projects = projects_response.json()
            existing_project = None
            for proj in projects:
                if proj.get("name") == project_name:
                    existing_project = proj
                    break

            if existing_project:
                project_id = existing_project["id"]
                progress.update(task, description=f"Using existing project: {project_name}")
            else:
                # Create new project
                create_payload = {
                    "name": project_name,
                    "description": description,
                    "path": str(project_path.resolve()),
                }
                create_response = await _request(
                    client,
                    "POST",
                    "/api/projects",
                    json=create_payload,
                )

                if create_response.status_code != 201:
                    _fail_request("create project", create_response)

                existing_project = create_response.json()
                project_id = existing_project["id"]
                progress.update(task, description=f"Created project: {project_name}")

        console.print(f"[green]✓[/green] Project: {project_name} (id={project_id})")

        # Step 3: Resolve recipe
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Resolving recipe skills...", total=None)

            resolve_response = await _request(
                client,
                "POST",
                "/api/recipes/resolve",
                json={"content": recipe_content},
            )

            if resolve_response.status_code != 200:
                _fail_request("resolve recipe", resolve_response)

            resolved_data = resolve_response.json()

        # Count total skills
        total_skills = sum(len(skills) for skills in resolved_data.values())
        console.print(f"[green]✓[/green] Resolved {total_skills} skills across {len(resolved_data)} harness(es)")

        # Step 4: Install skills for each harness
        harnesses_response = await _request(client, "GET", "/api/harnesses")
        if harnesses_response.status_code != 200:
            _fail_request("list harnesses", harnesses_response)

        harnesses = harnesses_response.json()
        harness_map = {h["name"]: h["id"] for h in harnesses}

        installation_results: dict[str, dict[str, int]] = {}

        for harness_name, skills in resolved_data.items():
            if harness_name == "*":
                # Recipe applies to all harnesses - install to first available or skip
                console.print("[yellow]⚠ Recipe applies to all harnesses - please specify harnesses in recipe[/yellow]")
                continue

            if harness_name not in harness_map:
                console.print(f"[yellow]⚠ Harness '{harness_name}' not registered, skipping[/yellow]")
                continue

            harness_id = harness_map[harness_name]

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task(
                    f"Installing skills for {harness_name}...",
                    total=len(skills),
                )

                installed = 0
                failed = 0
                skipped = 0

                for skill in skills:
                    install_payload = {
                        "skill_id": skill["skill_id"],
                        "harness_id": harness_id,
                        "scope": "project",
                        "project_id": project_id,
                    }

                    install_response = await _request(
                        client,
                        "POST",
                        "/api/skills/install",
                        json=install_payload,
                    )

                    if install_response.status_code == 201:
                        installed += 1
                    elif install_response.status_code == 409:
                        # Already installed
                        skipped += 1
                    else:
                        failed += 1
                        console.print(
                            f"  [red]✗[/red] Failed to install {skill['skill_name']}: "
                            f"{install_response.status_code}"
                        )

                    progress.update(task, advance=1)

            installation_results[harness_name] = {
                "installed": installed,
                "skipped": skipped,
                "failed": failed,
            }

            # Print results for this harness
            if installed > 0:
                console.print(f"[green]✓[/green] {harness_name}: Installed {installed} skill(s)")
            if skipped > 0:
                console.print(f"[dim]  {skipped} already installed[/dim]")
            if failed > 0:
                console.print(f"[red]✗[/red] {harness_name}: Failed to install {failed} skill(s)")

        # Summary
        console.print()
        console.print("[bold]Summary:[/bold]")
        total_installed = sum(r["installed"] for r in installation_results.values())
        total_skipped = sum(r["skipped"] for r in installation_results.values())
        total_failed = sum(r["failed"] for r in installation_results.values())

        console.print(f"  Installed: {total_installed}")
        if total_skipped > 0:
            console.print(f"  Already installed: {total_skipped}")
        if total_failed > 0:
            console.print(f"  Failed: {total_failed}")

        if total_failed > 0:
            raise typer.Exit(code=1)
