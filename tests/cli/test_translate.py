"""Tests for translate CLI commands."""

from pathlib import Path
from unittest.mock import patch

import httpx
from typer.testing import CliRunner

from jefe.cli import app

runner = CliRunner()


def _make_client(handler) -> httpx.AsyncClient:
    """Create a mock HTTP client with the given handler."""
    transport = httpx.MockTransport(handler)
    return httpx.AsyncClient(base_url="http://test", transport=transport)


def test_translate_command_with_dry_run(tmp_path: Path) -> None:
    """Test translate command with dry-run flag."""
    # Create test file
    test_file = tmp_path / "CLAUDE.md"
    test_file.write_text("# Instructions\n\nOriginal content")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/translate"
        assert request.method == "POST"
        data = request.read().decode("utf-8")
        assert "claude-code" in data
        assert "codex-cli" in data
        return httpx.Response(
            200,
            json={
                "output": "# Instructions\n\nTranslated content",
                "diff": "--- claude-code\n+++ codex-cli\n@@ -1 +1 @@\n-Original content\n+Translated content",
                "log_id": 123,
            },
        )

    client = _make_client(handler)
    with (
        patch("jefe.cli.commands.translate.get_api_key", return_value="key"),
        patch("jefe.cli.commands.translate.create_client", return_value=client),
    ):
        result = runner.invoke(
            app,
            [
                "translate",
                "file",
                str(test_file),
                "--from",
                "claude-code",
                "--to",
                "codex-cli",
                "--dry-run",
            ],
        )

    assert result.exit_code == 0
    assert "Dry run" in result.stdout
    assert "claude-code" in result.stdout
    assert "codex-cli" in result.stdout
    # File should not be modified in dry-run mode
    assert test_file.read_text() == "# Instructions\n\nOriginal content"


def test_translate_command_with_confirmation(tmp_path: Path) -> None:
    """Test translate command with confirmation prompt."""
    # Create test file
    test_file = tmp_path / "CLAUDE.md"
    test_file.write_text("# Instructions\n\nOriginal content")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/translate"
        return httpx.Response(
            200,
            json={
                "output": "# Instructions\n\nTranslated content",
                "diff": "--- claude-code\n+++ codex-cli\n@@ -1 +1 @@\n-Original content\n+Translated content",
                "log_id": 123,
            },
        )

    client = _make_client(handler)
    with (
        patch("jefe.cli.commands.translate.get_api_key", return_value="key"),
        patch("jefe.cli.commands.translate.create_client", return_value=client),
    ):
        # Confirm the prompt
        result = runner.invoke(
            app,
            [
                "translate",
                "file",
                str(test_file),
                "--from",
                "claude-code",
                "--to",
                "codex-cli",
            ],
            input="y\n",
        )

    assert result.exit_code == 0
    assert "Translation applied" in result.stdout
    # File should be modified
    assert test_file.read_text() == "# Instructions\n\nTranslated content"


def test_translate_command_with_yes_flag(tmp_path: Path) -> None:
    """Test translate command with --yes flag to skip confirmation."""
    # Create test file
    test_file = tmp_path / "CLAUDE.md"
    test_file.write_text("# Instructions\n\nOriginal content")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/translate"
        return httpx.Response(
            200,
            json={
                "output": "# Instructions\n\nTranslated content",
                "diff": "--- claude-code\n+++ codex-cli\n@@ -1 +1 @@\n-Original content\n+Translated content",
                "log_id": 123,
            },
        )

    client = _make_client(handler)
    with (
        patch("jefe.cli.commands.translate.get_api_key", return_value="key"),
        patch("jefe.cli.commands.translate.create_client", return_value=client),
    ):
        result = runner.invoke(
            app,
            [
                "translate",
                "file",
                str(test_file),
                "--from",
                "claude-code",
                "--to",
                "codex-cli",
                "--yes",
            ],
        )

    assert result.exit_code == 0
    assert "Translation applied" in result.stdout
    # File should be modified
    assert test_file.read_text() == "# Instructions\n\nTranslated content"


def test_translate_command_with_output_file(tmp_path: Path) -> None:
    """Test translate command with --output flag."""
    # Create test file
    test_file = tmp_path / "CLAUDE.md"
    test_file.write_text("# Instructions\n\nOriginal content")
    output_file = tmp_path / "AGENTS.md"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/translate"
        return httpx.Response(
            200,
            json={
                "output": "# Instructions\n\nTranslated content",
                "diff": "--- claude-code\n+++ codex-cli\n@@ -1 +1 @@\n-Original content\n+Translated content",
                "log_id": 123,
            },
        )

    client = _make_client(handler)
    with (
        patch("jefe.cli.commands.translate.get_api_key", return_value="key"),
        patch("jefe.cli.commands.translate.create_client", return_value=client),
    ):
        result = runner.invoke(
            app,
            [
                "translate",
                "file",
                str(test_file),
                "--from",
                "claude-code",
                "--to",
                "codex-cli",
                "--output",
                str(output_file),
                "--yes",
            ],
        )

    assert result.exit_code == 0
    assert "Translation applied" in result.stdout
    # Original file should be unchanged
    assert test_file.read_text() == "# Instructions\n\nOriginal content"
    # Output file should have translated content
    assert output_file.read_text() == "# Instructions\n\nTranslated content"


def test_translate_command_missing_file() -> None:
    """Test translate command with non-existent file."""
    with (
        patch("jefe.cli.commands.translate.get_api_key", return_value="key"),
    ):
        result = runner.invoke(
            app,
            [
                "translate",
                "file",
                "/nonexistent/file.md",
                "--from",
                "claude-code",
                "--to",
                "codex-cli",
            ],
        )

    assert result.exit_code == 1
    assert "File not found" in result.stdout


def test_translate_command_missing_from_option(tmp_path: Path) -> None:
    """Test translate command without --from option."""
    test_file = tmp_path / "CLAUDE.md"
    test_file.write_text("# Instructions")

    with (
        patch("jefe.cli.commands.translate.get_api_key", return_value="key"),
    ):
        result = runner.invoke(
            app,
            [
                "translate",
                "file",
                str(test_file),
                "--to",
                "codex-cli",
            ],
        )

    assert result.exit_code == 1
    assert "Missing required option" in result.stdout


def test_translate_command_missing_to_option(tmp_path: Path) -> None:
    """Test translate command without --to option."""
    test_file = tmp_path / "CLAUDE.md"
    test_file.write_text("# Instructions")

    with (
        patch("jefe.cli.commands.translate.get_api_key", return_value="key"),
    ):
        result = runner.invoke(
            app,
            [
                "translate",
                "file",
                str(test_file),
                "--from",
                "claude-code",
            ],
        )

    assert result.exit_code == 1
    assert "Missing required option" in result.stdout


def test_translate_command_api_error(tmp_path: Path) -> None:
    """Test translate command with API error."""
    test_file = tmp_path / "CLAUDE.md"
    test_file.write_text("# Instructions\n\nOriginal content")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={"detail": "Invalid harness name"},
        )

    client = _make_client(handler)
    with (
        patch("jefe.cli.commands.translate.get_api_key", return_value="key"),
        patch("jefe.cli.commands.translate.create_client", return_value=client),
    ):
        result = runner.invoke(
            app,
            [
                "translate",
                "file",
                str(test_file),
                "--from",
                "invalid",
                "--to",
                "codex-cli",
            ],
        )

    assert result.exit_code == 1
    assert "Invalid harness name" in result.stdout


def test_translate_history_command() -> None:
    """Test translate history command."""
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/translate/log"
        assert "limit=10" in str(request.url)
        return httpx.Response(
            200,
            json=[
                {
                    "id": 1,
                    "model_name": "claude-code-to-codex-cli",
                    "translation_type": "SYNTAX",
                    "created_at": "2026-01-13T10:00:00",
                    "input_text": "# Instructions\n\nOriginal",
                    "output_text": "# Instructions\n\nTranslated",
                    "project_id": None,
                },
                {
                    "id": 2,
                    "model_name": "codex-cli-to-gemini-cli",
                    "translation_type": "SYNTAX",
                    "created_at": "2026-01-13T11:00:00",
                    "input_text": "# Another",
                    "output_text": "# Translated",
                    "project_id": 1,
                },
            ],
        )

    client = _make_client(handler)
    with (
        patch("jefe.cli.commands.translate.get_api_key", return_value="key"),
        patch("jefe.cli.commands.translate.create_client", return_value=client),
    ):
        result = runner.invoke(app, ["translate", "history"])

    assert result.exit_code == 0
    assert "Recent Translations" in result.stdout
    assert "claude-code-to-codex-cli" in result.stdout
    assert "codex-cli-to-gemini-cli" in result.stdout


def test_translate_history_command_with_limit() -> None:
    """Test translate history command with custom limit."""
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/translate/log"
        assert "limit=5" in str(request.url)
        return httpx.Response(200, json=[])

    client = _make_client(handler)
    with (
        patch("jefe.cli.commands.translate.get_api_key", return_value="key"),
        patch("jefe.cli.commands.translate.create_client", return_value=client),
    ):
        result = runner.invoke(app, ["translate", "history", "--limit", "5"])

    assert result.exit_code == 0


def test_translate_history_command_empty() -> None:
    """Test translate history command with no history."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    client = _make_client(handler)
    with (
        patch("jefe.cli.commands.translate.get_api_key", return_value="key"),
        patch("jefe.cli.commands.translate.create_client", return_value=client),
    ):
        result = runner.invoke(app, ["translate", "history"])

    assert result.exit_code == 0
    assert "No translation history found" in result.stdout


def test_translate_command_no_api_key() -> None:
    """Test translate command without API key configured."""
    with patch("jefe.cli.commands.translate.get_api_key", return_value=None):
        result = runner.invoke(
            app,
            [
                "translate",
                "file",
                "file.md",
                "--from",
                "claude-code",
                "--to",
                "codex-cli",
            ],
        )

    assert result.exit_code == 1
    assert "API key not configured" in result.stdout


def test_translate_command_cancelled_confirmation(tmp_path: Path) -> None:
    """Test translate command when user cancels confirmation."""
    test_file = tmp_path / "CLAUDE.md"
    test_file.write_text("# Instructions\n\nOriginal content")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "output": "# Instructions\n\nTranslated content",
                "diff": "--- claude-code\n+++ codex-cli\n@@ -1 +1 @@\n-Original content\n+Translated content",
                "log_id": 123,
            },
        )

    client = _make_client(handler)
    with (
        patch("jefe.cli.commands.translate.get_api_key", return_value="key"),
        patch("jefe.cli.commands.translate.create_client", return_value=client),
    ):
        # Reject the prompt
        result = runner.invoke(
            app,
            [
                "translate",
                "file",
                str(test_file),
                "--from",
                "claude-code",
                "--to",
                "codex-cli",
            ],
            input="n\n",
        )

    assert result.exit_code == 0
    assert "Cancelled" in result.stdout
    # File should not be modified
    assert test_file.read_text() == "# Instructions\n\nOriginal content"
