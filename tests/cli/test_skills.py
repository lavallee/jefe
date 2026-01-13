"""Tests for skills CLI commands."""

import json
from unittest.mock import patch

import httpx
from typer.testing import CliRunner

from jefe.cli import app

runner = CliRunner()


def _make_client(handler) -> httpx.AsyncClient:
    transport = httpx.MockTransport(handler)
    return httpx.AsyncClient(base_url="http://test", transport=transport)


def test_skills_search_command() -> None:
    """Search skills via CLI."""

    def handler(request: httpx.Request) -> httpx.Response:
        # First try by tag
        if "tag=git" in str(request.url):
            return httpx.Response(
                200,
                json=[
                    {
                        "id": 1,
                        "name": "git-commit",
                        "display_name": "Git Commit Helper",
                        "version": "1.0.0",
                        "author": "Anthropic",
                        "description": "Help write git commit messages",
                        "tags": ["git", "commit"],
                        "source_id": 1,
                        "metadata_json": {},
                    }
                ],
            )
        return httpx.Response(200, json=[])

    client = _make_client(handler)
    with (
        patch("jefe.cli.commands.skills.get_api_key", return_value="key"),
        patch("jefe.cli.commands.skills.create_client", return_value=client),
    ):
        result = runner.invoke(app, ["skills", "search", "git"])

    assert result.exit_code == 0
    assert "git-commit" in result.stdout


def test_skills_search_no_results() -> None:
    """Search skills with no results."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    client = _make_client(handler)
    with (
        patch("jefe.cli.commands.skills.get_api_key", return_value="key"),
        patch("jefe.cli.commands.skills.create_client", return_value=client),
    ):
        result = runner.invoke(app, ["skills", "search", "nonexistent"])

    assert result.exit_code == 0
    assert "No skills found" in result.stdout


def test_skills_list_command() -> None:
    """List available skills via CLI."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/skills"
        return httpx.Response(
            200,
            json=[
                {
                    "id": 1,
                    "name": "pdf",
                    "display_name": "PDF Generator",
                    "version": "1.0.0",
                    "author": "Anthropic",
                    "description": "Generate PDF documents",
                    "tags": ["pdf"],
                    "source_id": 1,
                    "metadata_json": {},
                },
                {
                    "id": 2,
                    "name": "git-commit",
                    "display_name": "Git Commit Helper",
                    "version": "1.0.0",
                    "author": "Anthropic",
                    "description": "Help write git commit messages",
                    "tags": ["git"],
                    "source_id": 1,
                    "metadata_json": {},
                },
            ],
        )

    client = _make_client(handler)
    with (
        patch("jefe.cli.commands.skills.get_api_key", return_value="key"),
        patch("jefe.cli.commands.skills.create_client", return_value=client),
    ):
        result = runner.invoke(app, ["skills", "list"])

    assert result.exit_code == 0
    assert "pdf" in result.stdout
    assert "git-commit" in result.stdout


def test_skills_list_empty() -> None:
    """List skills when none available."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    client = _make_client(handler)
    with (
        patch("jefe.cli.commands.skills.get_api_key", return_value="key"),
        patch("jefe.cli.commands.skills.create_client", return_value=client),
    ):
        result = runner.invoke(app, ["skills", "list"])

    assert result.exit_code == 0
    assert "No skills available" in result.stdout


def test_skills_list_installed() -> None:
    """List installed skills via CLI."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/skills/installed"
        return httpx.Response(
            200,
            json=[
                {
                    "id": 1,
                    "scope": "global",
                    "installed_path": "/path/to/skill",
                    "pinned_version": "1.0.0",
                    "skill": {
                        "id": 1,
                        "name": "pdf",
                        "display_name": "PDF Generator",
                        "version": "1.0.0",
                    },
                    "harness": {"id": 1, "name": "claude-code"},
                    "project": None,
                }
            ],
        )

    client = _make_client(handler)
    with (
        patch("jefe.cli.commands.skills.get_api_key", return_value="key"),
        patch("jefe.cli.commands.skills.create_client", return_value=client),
    ):
        result = runner.invoke(app, ["skills", "list", "--installed"])

    assert result.exit_code == 0
    assert "pdf" in result.stdout
    assert "global" in result.stdout
    assert "claude-code" in result.stdout


def test_skills_list_installed_with_project_filter() -> None:
    """List installed skills filtered by project."""
    call_count = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["count"] += 1

        # First call: list projects
        if request.url.path == "/api/projects":
            return httpx.Response(
                200,
                json=[
                    {
                        "id": 1,
                        "name": "my-project",
                        "description": None,
                        "manifestations": [],
                    }
                ],
            )

        # Second call: list installed skills for project
        if request.url.path == "/api/skills/installed":
            assert "project=1" in str(request.url)
            return httpx.Response(
                200,
                json=[
                    {
                        "id": 1,
                        "scope": "project",
                        "installed_path": "/path/to/skill",
                        "pinned_version": "1.0.0",
                        "skill": {"id": 1, "name": "pdf"},
                        "harness": {"id": 1, "name": "claude-code"},
                        "project": {"id": 1, "name": "my-project"},
                    }
                ],
            )

        return httpx.Response(404, text="Not found")

    client = _make_client(handler)
    with (
        patch("jefe.cli.commands.skills.get_api_key", return_value="key"),
        patch("jefe.cli.commands.skills.create_client", return_value=client),
    ):
        result = runner.invoke(app, ["skills", "list", "--installed", "--project", "my-project"])

    assert result.exit_code == 0
    assert "pdf" in result.stdout
    assert "my-project" in result.stdout


def test_skills_show_command() -> None:
    """Show skill details via CLI."""
    call_count = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["count"] += 1

        # First call: resolve skill ID by name
        if request.url.path == "/api/skills" and call_count["count"] == 1:
            return httpx.Response(
                200,
                json=[
                    {
                        "id": 1,
                        "name": "pdf",
                        "display_name": "PDF Generator",
                        "version": "1.0.0",
                        "author": "Anthropic",
                        "description": "Generate PDF documents",
                        "tags": ["pdf", "documents"],
                        "source_id": 1,
                        "metadata_json": {"category": "productivity"},
                    }
                ],
            )

        # Second call: get skill details
        if request.url.path == "/api/skills/1":
            return httpx.Response(
                200,
                json={
                    "id": 1,
                    "name": "pdf",
                    "display_name": "PDF Generator",
                    "version": "1.0.0",
                    "author": "Anthropic",
                    "description": "Generate PDF documents",
                    "tags": ["pdf", "documents"],
                    "source_id": 1,
                    "metadata_json": {"category": "productivity"},
                },
            )

        return httpx.Response(404, text="Not found")

    client = _make_client(handler)
    with (
        patch("jefe.cli.commands.skills.get_api_key", return_value="key"),
        patch("jefe.cli.commands.skills.create_client", return_value=client),
    ):
        result = runner.invoke(app, ["skills", "show", "pdf"])

    assert result.exit_code == 0
    assert "pdf" in result.stdout
    assert "PDF Generator" in result.stdout
    assert "Generate PDF documents" in result.stdout


def test_skills_install_global() -> None:
    """Install skill globally via CLI."""
    call_count = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["count"] += 1

        # First call: resolve skill ID
        if request.url.path == "/api/skills" and call_count["count"] == 1:
            return httpx.Response(200, json=[{"id": 1, "name": "pdf"}])

        # Second call: list harnesses
        if request.url.path == "/api/harnesses":
            return httpx.Response(200, json=[{"id": 1, "name": "claude-code"}])

        # Third call: install skill
        if request.url.path == "/api/skills/install":
            payload = json.loads(request.content.decode())
            assert payload["skill_id"] == 1
            assert payload["harness_id"] == 1
            assert payload["scope"] == "global"
            assert payload["project_id"] is None
            return httpx.Response(
                201,
                json={
                    "id": 1,
                    "scope": "global",
                    "installed_path": "/path/to/skill",
                    "pinned_version": "1.0.0",
                },
            )

        return httpx.Response(404, text="Not found")

    client = _make_client(handler)
    with (
        patch("jefe.cli.commands.skills.get_api_key", return_value="key"),
        patch("jefe.cli.commands.skills.create_client", return_value=client),
    ):
        result = runner.invoke(app, ["skills", "install", "pdf", "--harness", "claude-code", "--global"])

    assert result.exit_code == 0
    assert "Installed skill 'pdf' globally" in result.stdout


def test_skills_install_project() -> None:
    """Install skill to project via CLI."""
    call_count = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["count"] += 1

        # First call: resolve skill ID
        if request.url.path == "/api/skills" and call_count["count"] == 1:
            return httpx.Response(200, json=[{"id": 1, "name": "pdf"}])

        # Second call: list harnesses
        if request.url.path == "/api/harnesses":
            return httpx.Response(200, json=[{"id": 1, "name": "claude-code"}])

        # Third call: list projects
        if request.url.path == "/api/projects":
            return httpx.Response(200, json=[{"id": 1, "name": "my-project"}])

        # Fourth call: install skill
        if request.url.path == "/api/skills/install":
            payload = json.loads(request.content.decode())
            assert payload["skill_id"] == 1
            assert payload["harness_id"] == 1
            assert payload["scope"] == "project"
            assert payload["project_id"] == 1
            return httpx.Response(
                201,
                json={
                    "id": 1,
                    "scope": "project",
                    "installed_path": "/path/to/skill",
                    "pinned_version": "1.0.0",
                },
            )

        return httpx.Response(404, text="Not found")

    client = _make_client(handler)
    with (
        patch("jefe.cli.commands.skills.get_api_key", return_value="key"),
        patch("jefe.cli.commands.skills.create_client", return_value=client),
    ):
        result = runner.invoke(
            app,
            ["skills", "install", "pdf", "--harness", "claude-code", "--project", "my-project"],
        )

    assert result.exit_code == 0
    assert "Installed skill 'pdf' to project 'my-project'" in result.stdout


def test_skills_install_invalid_scope() -> None:
    """Install skill with invalid scope options."""
    # Test with both --global and --project
    result = runner.invoke(
        app,
        ["skills", "install", "pdf", "--harness", "claude-code", "--global", "--project", "my-project"],
    )
    assert result.exit_code == 1
    assert "Cannot specify both --global and --project" in result.stdout

    # Test with neither --global nor --project
    result = runner.invoke(
        app,
        ["skills", "install", "pdf", "--harness", "claude-code"],
    )
    assert result.exit_code == 1
    assert "Must specify either --global or --project" in result.stdout


def test_skills_uninstall_command() -> None:
    """Uninstall skill via CLI."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/skills/installed/1"
        return httpx.Response(204)

    client = _make_client(handler)
    with (
        patch("jefe.cli.commands.skills.get_api_key", return_value="key"),
        patch("jefe.cli.commands.skills.create_client", return_value=client),
    ):
        result = runner.invoke(app, ["skills", "uninstall", "1"])

    assert result.exit_code == 0
    assert "Uninstalled skill (install_id=1)" in result.stdout


def test_skills_command_without_api_key() -> None:
    """Skills commands require API key."""
    with patch("jefe.cli.commands.skills.get_api_key", return_value=None):
        result = runner.invoke(app, ["skills", "list"])

    assert result.exit_code == 1
    assert "API key not configured" in result.stdout
