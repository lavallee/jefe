"""Tests for conflict resolution CLI commands."""

from datetime import UTC, datetime
from unittest.mock import patch

from typer.testing import CliRunner

from jefe.cli import app
from jefe.cli.cache.models import (
    CachedConflict,
    ConflictEntityType,
    ConflictResolutionType,
)

runner = CliRunner()


def test_sync_conflicts_no_conflicts() -> None:
    """Test sync conflicts command with no pending conflicts."""
    with (
        patch("jefe.cli.commands.sync.get_api_key", return_value="key"),
        patch("jefe.cli.commands.sync.CacheManager") as mock_cache,
    ):
        mock_cache_inst = mock_cache.return_value
        mock_cache_inst.conflicts.get_unresolved.return_value = []

        result = runner.invoke(app, ["sync", "conflicts"])

    assert result.exit_code == 0
    assert "No pending conflicts" in result.stdout


def test_sync_conflicts_with_conflicts() -> None:
    """Test sync conflicts command with pending conflicts."""

    conflict = CachedConflict(
        id=1,
        entity_type=ConflictEntityType.PROJECT,
        local_id=10,
        server_id=20,
        local_updated_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
        server_updated_at=datetime(2024, 1, 1, 13, 0, 0, tzinfo=UTC),
        resolution=ConflictResolutionType.UNRESOLVED,
        local_data='{"name": "local-project"}',
        server_data='{"name": "server-project"}',
    )

    with (
        patch("jefe.cli.commands.sync.get_api_key", return_value="key"),
        patch("jefe.cli.commands.sync.CacheManager") as mock_cache,
    ):
        mock_cache_inst = mock_cache.return_value
        mock_cache_inst.conflicts.get_unresolved.return_value = [conflict]

        result = runner.invoke(app, ["sync", "conflicts"])

    assert result.exit_code == 0
    assert "Pending Conflicts" in result.stdout
    assert "project" in result.stdout
    assert "10" in result.stdout
    assert "20" in result.stdout
    assert "Total conflicts: 1" in result.stdout


def test_sync_resolve_not_found() -> None:
    """Test sync resolve command with non-existent conflict."""
    with (
        patch("jefe.cli.commands.sync.get_api_key", return_value="key"),
        patch("jefe.cli.commands.sync.CacheManager") as mock_cache,
    ):
        mock_cache_inst = mock_cache.return_value
        mock_cache_inst.conflicts.get_by_id.return_value = None

        result = runner.invoke(app, ["sync", "resolve", "999", "--keep-local"])

    assert result.exit_code == 1
    assert "not found" in result.stdout


def test_sync_resolve_keep_local() -> None:
    """Test sync resolve command with --keep-local flag."""

    conflict = CachedConflict(
        id=1,
        entity_type=ConflictEntityType.PROJECT,
        local_id=10,
        server_id=20,
        local_updated_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
        server_updated_at=datetime(2024, 1, 1, 13, 0, 0, tzinfo=UTC),
        resolution=ConflictResolutionType.UNRESOLVED,
        local_data='{"name": "local-project", "description": "local desc"}',
        server_data='{"name": "server-project", "description": "server desc"}',
    )

    with (
        patch("jefe.cli.commands.sync.get_api_key", return_value="key"),
        patch("jefe.cli.commands.sync.CacheManager") as mock_cache,
    ):
        mock_cache_inst = mock_cache.return_value
        mock_cache_inst.conflicts.get_by_id.return_value = conflict
        mock_cache_inst.conflicts.resolve.return_value = conflict

        result = runner.invoke(app, ["sync", "resolve", "1", "--keep-local"])

    assert result.exit_code == 0
    assert "resolved" in result.stdout.lower()
    assert "local" in result.stdout.lower()
    mock_cache_inst.conflicts.resolve.assert_called_once_with(
        1, ConflictResolutionType.LOCAL_WINS
    )


def test_sync_resolve_keep_server() -> None:
    """Test sync resolve command with --keep-server flag."""

    conflict = CachedConflict(
        id=1,
        entity_type=ConflictEntityType.SKILL,
        local_id=10,
        server_id=20,
        local_updated_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
        server_updated_at=datetime(2024, 1, 1, 13, 0, 0, tzinfo=UTC),
        resolution=ConflictResolutionType.UNRESOLVED,
        local_data='{"name": "local-skill"}',
        server_data='{"name": "server-skill"}',
    )

    with (
        patch("jefe.cli.commands.sync.get_api_key", return_value="key"),
        patch("jefe.cli.commands.sync.CacheManager") as mock_cache,
    ):
        mock_cache_inst = mock_cache.return_value
        mock_cache_inst.conflicts.get_by_id.return_value = conflict
        mock_cache_inst.conflicts.resolve.return_value = conflict

        result = runner.invoke(app, ["sync", "resolve", "1", "--keep-server"])

    assert result.exit_code == 0
    assert "resolved" in result.stdout.lower()
    assert "server" in result.stdout.lower()
    mock_cache_inst.conflicts.resolve.assert_called_once_with(
        1, ConflictResolutionType.SERVER_WINS
    )


def test_sync_resolve_both_flags_error() -> None:
    """Test sync resolve command with both --keep-local and --keep-server."""
    with patch("jefe.cli.commands.sync.get_api_key", return_value="key"):
        result = runner.invoke(
            app, ["sync", "resolve", "1", "--keep-local", "--keep-server"]
        )

    assert result.exit_code == 1
    assert "Cannot specify both" in result.stdout


def test_sync_resolve_already_resolved() -> None:
    """Test sync resolve command on already resolved conflict."""

    conflict = CachedConflict(
        id=1,
        entity_type=ConflictEntityType.PROJECT,
        local_id=10,
        server_id=20,
        local_updated_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
        server_updated_at=datetime(2024, 1, 1, 13, 0, 0, tzinfo=UTC),
        resolution=ConflictResolutionType.LOCAL_WINS,
        local_data='{"name": "local-project"}',
        server_data='{"name": "server-project"}',
    )

    with (
        patch("jefe.cli.commands.sync.get_api_key", return_value="key"),
        patch("jefe.cli.commands.sync.CacheManager") as mock_cache,
    ):
        mock_cache_inst = mock_cache.return_value
        mock_cache_inst.conflicts.get_by_id.return_value = conflict

        result = runner.invoke(app, ["sync", "resolve", "1", "--keep-local"])

    assert result.exit_code == 0
    assert "already resolved" in result.stdout


def test_sync_resolve_interactive_with_diff() -> None:
    """Test sync resolve command shows diff in interactive mode."""

    conflict = CachedConflict(
        id=1,
        entity_type=ConflictEntityType.PROJECT,
        local_id=10,
        server_id=20,
        local_updated_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
        server_updated_at=datetime(2024, 1, 1, 13, 0, 0, tzinfo=UTC),
        resolution=ConflictResolutionType.UNRESOLVED,
        local_data='{"name": "local-project", "description": "local"}',
        server_data='{"name": "server-project", "description": "server"}',
    )

    with (
        patch("jefe.cli.commands.sync.get_api_key", return_value="key"),
        patch("jefe.cli.commands.sync.CacheManager") as mock_cache,
    ):
        mock_cache_inst = mock_cache.return_value
        mock_cache_inst.conflicts.get_by_id.return_value = conflict
        mock_cache_inst.conflicts.resolve.return_value = conflict

        result = runner.invoke(
            app, ["sync", "resolve", "1", "--keep-local"], catch_exceptions=False
        )

    assert result.exit_code == 0
    assert "Conflict 1:" in result.stdout
    assert "Entity Type: project" in result.stdout
    assert "Differences:" in result.stdout
    assert "name:" in result.stdout
    assert "local-project" in result.stdout
    assert "server-project" in result.stdout
