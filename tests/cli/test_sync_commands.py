"""Tests for sync CLI commands."""

from unittest.mock import AsyncMock, patch

import httpx
from typer.testing import CliRunner

from jefe.cli import app
from jefe.cli.sync.protocol import (
    ConflictResolution,
    EntityType,
    SyncConflict,
    SyncResult,
)

runner = CliRunner()


def _make_client(handler) -> httpx.AsyncClient:
    transport = httpx.MockTransport(handler)
    return httpx.AsyncClient(base_url="http://test", transport=transport)


def test_sync_status_online_no_changes() -> None:
    """Test sync status with no pending changes."""
    with (
        patch("jefe.cli.commands.sync.get_api_key", return_value="key"),
        patch("jefe.cli.commands.sync.is_online", new_callable=AsyncMock) as mock_online,
        patch("jefe.cli.commands.sync.CacheManager") as mock_cache,
    ):
        mock_online.return_value = True
        mock_cache_inst = mock_cache.return_value
        mock_cache_inst.get_all_dirty_items.return_value = ([], [], [], [])

        result = runner.invoke(app, ["sync", "status"])

    assert result.exit_code == 0
    assert "Online" in result.stdout
    assert "No pending changes" in result.stdout


def test_sync_status_online_with_changes() -> None:
    """Test sync status with pending changes."""

    class MockProject:
        def __init__(self, name: str):
            self.name = name

    class MockSkill:
        def __init__(self, name: str):
            self.name = name

    with (
        patch("jefe.cli.commands.sync.get_api_key", return_value="key"),
        patch("jefe.cli.commands.sync.is_online", new_callable=AsyncMock) as mock_online,
        patch("jefe.cli.commands.sync.CacheManager") as mock_cache,
    ):
        mock_online.return_value = True
        mock_cache_inst = mock_cache.return_value
        mock_cache_inst.get_all_dirty_items.return_value = (
            [MockProject("project1"), MockProject("project2")],
            [MockSkill("skill1")],
            [],
            [],
        )

        result = runner.invoke(app, ["sync", "status"])

    assert result.exit_code == 0
    assert "Online" in result.stdout
    assert "Pending Changes" in result.stdout
    assert "project1" in result.stdout
    assert "skill1" in result.stdout
    assert "Total pending changes: 3" in result.stdout


def test_sync_status_offline() -> None:
    """Test sync status when server is offline."""
    with (
        patch("jefe.cli.commands.sync.get_api_key", return_value="key"),
        patch("jefe.cli.commands.sync.is_online", new_callable=AsyncMock) as mock_online,
    ):
        mock_online.return_value = False

        result = runner.invoke(app, ["sync", "status"])

    assert result.exit_code == 0
    assert "Offline" in result.stdout


def test_sync_push_success() -> None:
    """Test successful push command."""
    with (
        patch("jefe.cli.commands.sync.get_api_key", return_value="key"),
        patch("jefe.cli.commands.sync.is_online", new_callable=AsyncMock) as mock_online,
        patch("jefe.cli.commands.sync.SyncProtocol") as mock_protocol,
    ):
        mock_online.return_value = True
        mock_protocol_inst = mock_protocol.return_value
        mock_protocol_inst.push = AsyncMock(
            return_value=SyncResult(success=True, pushed=5)
        )

        result = runner.invoke(app, ["sync", "push"])

    assert result.exit_code == 0
    assert "Pushed 5 items" in result.stdout


def test_sync_push_no_changes() -> None:
    """Test push with no changes."""
    with (
        patch("jefe.cli.commands.sync.get_api_key", return_value="key"),
        patch("jefe.cli.commands.sync.is_online", new_callable=AsyncMock) as mock_online,
        patch("jefe.cli.commands.sync.SyncProtocol") as mock_protocol,
    ):
        mock_online.return_value = True
        mock_protocol_inst = mock_protocol.return_value
        mock_protocol_inst.push = AsyncMock(
            return_value=SyncResult(success=True, pushed=0)
        )

        result = runner.invoke(app, ["sync", "push"])

    assert result.exit_code == 0
    assert "No changes to push" in result.stdout


def test_sync_push_with_conflicts() -> None:
    """Test push with conflicts."""
    from datetime import UTC, datetime

    conflicts = [
        SyncConflict(
            entity_type=EntityType.PROJECT,
            local_id=1,
            server_id=10,
            local_updated_at=datetime.now(UTC),
            server_updated_at=datetime.now(UTC),
            resolution=ConflictResolution.LOCAL_WINS,
        )
    ]

    with (
        patch("jefe.cli.commands.sync.get_api_key", return_value="key"),
        patch("jefe.cli.commands.sync.is_online", new_callable=AsyncMock) as mock_online,
        patch("jefe.cli.commands.sync.SyncProtocol") as mock_protocol,
    ):
        mock_online.return_value = True
        mock_protocol_inst = mock_protocol.return_value
        mock_protocol_inst.push = AsyncMock(
            return_value=SyncResult(success=True, pushed=2, conflicts=conflicts)
        )

        result = runner.invoke(app, ["sync", "push"])

    assert result.exit_code == 0
    assert "Pushed 2 items" in result.stdout
    assert "Conflicts detected" in result.stdout
    assert "project" in result.stdout
    assert "Local Wins" in result.stdout


def test_sync_push_failure() -> None:
    """Test push failure."""
    with (
        patch("jefe.cli.commands.sync.get_api_key", return_value="key"),
        patch("jefe.cli.commands.sync.is_online", new_callable=AsyncMock) as mock_online,
        patch("jefe.cli.commands.sync.SyncProtocol") as mock_protocol,
    ):
        mock_online.return_value = True
        mock_protocol_inst = mock_protocol.return_value
        mock_protocol_inst.push = AsyncMock(
            return_value=SyncResult(success=False, error_message="Connection error")
        )

        result = runner.invoke(app, ["sync", "push"])

    assert result.exit_code == 1
    assert "Push failed" in result.stdout
    assert "Connection error" in result.stdout


def test_sync_push_offline() -> None:
    """Test push when offline."""
    with (
        patch("jefe.cli.commands.sync.get_api_key", return_value="key"),
        patch("jefe.cli.commands.sync.is_online", new_callable=AsyncMock) as mock_online,
    ):
        mock_online.return_value = False

        result = runner.invoke(app, ["sync", "push"])

    assert result.exit_code == 1
    assert "offline" in result.stdout.lower()


def test_sync_pull_success() -> None:
    """Test successful pull command."""
    with (
        patch("jefe.cli.commands.sync.get_api_key", return_value="key"),
        patch("jefe.cli.commands.sync.is_online", new_callable=AsyncMock) as mock_online,
        patch("jefe.cli.commands.sync.SyncProtocol") as mock_protocol,
    ):
        mock_online.return_value = True
        mock_protocol_inst = mock_protocol.return_value
        mock_protocol_inst.pull = AsyncMock(
            return_value=SyncResult(success=True, pulled=3)
        )

        result = runner.invoke(app, ["sync", "pull"])

    assert result.exit_code == 0
    assert "Pulled 3 items" in result.stdout


def test_sync_pull_no_changes() -> None:
    """Test pull with no new changes."""
    with (
        patch("jefe.cli.commands.sync.get_api_key", return_value="key"),
        patch("jefe.cli.commands.sync.is_online", new_callable=AsyncMock) as mock_online,
        patch("jefe.cli.commands.sync.SyncProtocol") as mock_protocol,
    ):
        mock_online.return_value = True
        mock_protocol_inst = mock_protocol.return_value
        mock_protocol_inst.pull = AsyncMock(
            return_value=SyncResult(success=True, pulled=0)
        )

        result = runner.invoke(app, ["sync", "pull"])

    assert result.exit_code == 0
    assert "No new changes" in result.stdout


def test_sync_pull_with_conflicts() -> None:
    """Test pull with conflicts."""
    from datetime import UTC, datetime

    conflicts = [
        SyncConflict(
            entity_type=EntityType.SKILL,
            local_id=2,
            server_id=20,
            local_updated_at=datetime.now(UTC),
            server_updated_at=datetime.now(UTC),
            resolution=ConflictResolution.SERVER_WINS,
        )
    ]

    with (
        patch("jefe.cli.commands.sync.get_api_key", return_value="key"),
        patch("jefe.cli.commands.sync.is_online", new_callable=AsyncMock) as mock_online,
        patch("jefe.cli.commands.sync.SyncProtocol") as mock_protocol,
    ):
        mock_online.return_value = True
        mock_protocol_inst = mock_protocol.return_value
        mock_protocol_inst.pull = AsyncMock(
            return_value=SyncResult(success=True, pulled=4, conflicts=conflicts)
        )

        result = runner.invoke(app, ["sync", "pull"])

    assert result.exit_code == 0
    assert "Pulled 4 items" in result.stdout
    assert "Conflicts detected" in result.stdout
    assert "skill" in result.stdout
    assert "Server Wins" in result.stdout


def test_sync_pull_failure() -> None:
    """Test pull failure."""
    with (
        patch("jefe.cli.commands.sync.get_api_key", return_value="key"),
        patch("jefe.cli.commands.sync.is_online", new_callable=AsyncMock) as mock_online,
        patch("jefe.cli.commands.sync.SyncProtocol") as mock_protocol,
    ):
        mock_online.return_value = True
        mock_protocol_inst = mock_protocol.return_value
        mock_protocol_inst.pull = AsyncMock(
            return_value=SyncResult(success=False, error_message="Network timeout")
        )

        result = runner.invoke(app, ["sync", "pull"])

    assert result.exit_code == 1
    assert "Pull failed" in result.stdout
    assert "Network timeout" in result.stdout


def test_sync_pull_offline() -> None:
    """Test pull when offline."""
    with (
        patch("jefe.cli.commands.sync.get_api_key", return_value="key"),
        patch("jefe.cli.commands.sync.is_online", new_callable=AsyncMock) as mock_online,
    ):
        mock_online.return_value = False

        result = runner.invoke(app, ["sync", "pull"])

    assert result.exit_code == 1
    assert "offline" in result.stdout.lower()


def test_sync_full_success() -> None:
    """Test full sync command."""
    with (
        patch("jefe.cli.commands.sync.get_api_key", return_value="key"),
        patch("jefe.cli.commands.sync.is_online", new_callable=AsyncMock) as mock_online,
        patch("jefe.cli.commands.sync.SyncProtocol") as mock_protocol,
    ):
        mock_online.return_value = True
        mock_protocol_inst = mock_protocol.return_value
        mock_protocol_inst.sync = AsyncMock(
            return_value=SyncResult(success=True, pushed=2, pulled=3)
        )

        result = runner.invoke(app, ["sync"])

    assert result.exit_code == 0
    assert "Sync complete" in result.stdout
    assert "Pushed: 2 items" in result.stdout
    assert "Pulled: 3 items" in result.stdout


def test_sync_full_no_changes() -> None:
    """Test full sync with no changes."""
    with (
        patch("jefe.cli.commands.sync.get_api_key", return_value="key"),
        patch("jefe.cli.commands.sync.is_online", new_callable=AsyncMock) as mock_online,
        patch("jefe.cli.commands.sync.SyncProtocol") as mock_protocol,
    ):
        mock_online.return_value = True
        mock_protocol_inst = mock_protocol.return_value
        mock_protocol_inst.sync = AsyncMock(
            return_value=SyncResult(success=True, pushed=0, pulled=0)
        )

        result = runner.invoke(app, ["sync"])

    assert result.exit_code == 0
    assert "Sync complete" in result.stdout
    assert "No changes to synchronize" in result.stdout


def test_sync_full_with_conflicts() -> None:
    """Test full sync with conflicts."""
    from datetime import UTC, datetime

    conflicts = [
        SyncConflict(
            entity_type=EntityType.HARNESS_CONFIG,
            local_id=3,
            server_id=30,
            local_updated_at=datetime.now(UTC),
            server_updated_at=datetime.now(UTC),
            resolution=ConflictResolution.SERVER_WINS,
        ),
        SyncConflict(
            entity_type=EntityType.INSTALLED_SKILL,
            local_id=4,
            server_id=40,
            local_updated_at=datetime.now(UTC),
            server_updated_at=datetime.now(UTC),
            resolution=ConflictResolution.LOCAL_WINS,
        ),
    ]

    with (
        patch("jefe.cli.commands.sync.get_api_key", return_value="key"),
        patch("jefe.cli.commands.sync.is_online", new_callable=AsyncMock) as mock_online,
        patch("jefe.cli.commands.sync.SyncProtocol") as mock_protocol,
    ):
        mock_online.return_value = True
        mock_protocol_inst = mock_protocol.return_value
        mock_protocol_inst.sync = AsyncMock(
            return_value=SyncResult(success=True, pushed=2, pulled=3, conflicts=conflicts)
        )

        result = runner.invoke(app, ["sync"])

    assert result.exit_code == 0
    assert "Sync complete" in result.stdout
    assert "Conflicts detected" in result.stdout
    assert "harness_config" in result.stdout
    assert "installed_skill" in result.stdout


def test_sync_full_failure() -> None:
    """Test full sync failure."""
    with (
        patch("jefe.cli.commands.sync.get_api_key", return_value="key"),
        patch("jefe.cli.commands.sync.is_online", new_callable=AsyncMock) as mock_online,
        patch("jefe.cli.commands.sync.SyncProtocol") as mock_protocol,
    ):
        mock_online.return_value = True
        mock_protocol_inst = mock_protocol.return_value
        mock_protocol_inst.sync = AsyncMock(
            return_value=SyncResult(success=False, error_message="Server error")
        )

        result = runner.invoke(app, ["sync"])

    assert result.exit_code == 1
    assert "Sync failed" in result.stdout
    assert "Server error" in result.stdout


def test_sync_full_offline() -> None:
    """Test full sync when offline."""
    with (
        patch("jefe.cli.commands.sync.get_api_key", return_value="key"),
        patch("jefe.cli.commands.sync.is_online", new_callable=AsyncMock) as mock_online,
    ):
        mock_online.return_value = False

        result = runner.invoke(app, ["sync"])

    assert result.exit_code == 1
    assert "offline" in result.stdout.lower()


def test_sync_commands_require_api_key() -> None:
    """Test that sync commands require API key."""
    with patch("jefe.cli.commands.sync.get_api_key", return_value=None):
        result = runner.invoke(app, ["sync", "status"])
        assert result.exit_code == 1
        assert "API key not configured" in result.stdout

        result = runner.invoke(app, ["sync", "push"])
        assert result.exit_code == 1
        assert "API key not configured" in result.stdout

        result = runner.invoke(app, ["sync", "pull"])
        assert result.exit_code == 1
        assert "API key not configured" in result.stdout

        result = runner.invoke(app, ["sync"])
        assert result.exit_code == 1
        assert "API key not configured" in result.stdout
