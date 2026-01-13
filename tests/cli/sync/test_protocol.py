"""Tests for sync protocol."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from jefe.cli.cache.manager import CacheManager
from jefe.cli.cache.models import CacheBase, ConfigScope, InstallScope
from jefe.cli.sync.protocol import (
    ConflictResolution,
    EntityType,
    SyncClient,
    SyncConflict,
    SyncProtocol,
    SyncResult,
)


@pytest.fixture
def in_memory_engine():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    CacheBase.metadata.create_all(engine)
    return engine


@pytest.fixture
def mock_get_session(in_memory_engine):
    """Mock get_cache_session to use in-memory database."""
    SessionLocal = sessionmaker(bind=in_memory_engine)

    def _get_session():
        return SessionLocal()

    with patch("jefe.cli.cache.repositories.get_cache_session", side_effect=_get_session):
        with patch("jefe.cli.cache.repositories.init_cache_db"):
            yield


@pytest.fixture
def cache_manager(mock_get_session):
    """Create a cache manager for testing."""
    mgr = CacheManager(ttl_seconds=300)
    yield mgr
    mgr.close()


@pytest.fixture
def sync_protocol(cache_manager):
    """Create a sync protocol instance for testing."""
    protocol = SyncProtocol(cache_manager=cache_manager)
    yield protocol
    protocol.close()


class TestSyncConflict:
    """Tests for SyncConflict dataclass."""

    def test_sync_conflict_to_dict(self):
        """Test converting a sync conflict to dict."""
        now = datetime.now(UTC)
        conflict = SyncConflict(
            entity_type=EntityType.PROJECT,
            local_id=1,
            server_id=2,
            local_updated_at=now,
            server_updated_at=now + timedelta(hours=1),
            resolution=ConflictResolution.SERVER_WINS,
        )

        result = conflict.to_dict()

        assert result["entity_type"] == "project"
        assert result["local_id"] == 1
        assert result["server_id"] == 2
        assert result["resolution"] == "server_wins"


class TestSyncResult:
    """Tests for SyncResult dataclass."""

    def test_sync_result_success(self):
        """Test a successful sync result."""
        result = SyncResult(success=True, pushed=5, pulled=3)

        assert result.success is True
        assert result.pushed == 5
        assert result.pulled == 3
        assert result.had_conflicts is False

    def test_sync_result_with_conflicts(self):
        """Test sync result with conflicts."""
        conflict = SyncConflict(
            entity_type=EntityType.PROJECT,
            local_id=1,
            server_id=2,
            local_updated_at=datetime.now(UTC),
            server_updated_at=datetime.now(UTC),
            resolution=ConflictResolution.LOCAL_WINS,
        )
        result = SyncResult(success=True, conflicts=[conflict])

        assert result.had_conflicts is True

    def test_sync_result_failure(self):
        """Test a failed sync result."""
        result = SyncResult(success=False, error_message="Connection refused")

        assert result.success is False
        assert result.error_message == "Connection refused"


class TestSyncClient:
    """Tests for SyncClient."""

    @pytest.mark.asyncio
    async def test_sync_client_not_initialized(self):
        """Test that SyncClient raises error when not used as context manager."""
        client = SyncClient()

        with pytest.raises(RuntimeError, match="not initialized"):
            await client.push({})

    @pytest.mark.asyncio
    async def test_sync_client_push(self):
        """Test pushing data through the sync client."""
        with patch("jefe.cli.sync.protocol.create_client") as mock_create:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"success": True}
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_create.return_value = mock_client

            async with SyncClient() as client:
                result = await client.push({"projects": []})

            assert result["success"] is True
            mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_sync_client_pull(self):
        """Test pulling data through the sync client."""
        with patch("jefe.cli.sync.protocol.create_client") as mock_create:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "success": True,
                "server_time": datetime.now(UTC).isoformat(),
                "projects": [],
            }
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_create.return_value = mock_client

            async with SyncClient() as client:
                result = await client.pull()

            assert result["success"] is True
            mock_client.post.assert_called_once()


class TestSyncProtocol:
    """Tests for SyncProtocol."""

    def test_clear_conflicts(self, sync_protocol):
        """Test clearing tracked conflicts."""
        sync_protocol._conflicts = [
            SyncConflict(
                entity_type=EntityType.PROJECT,
                local_id=1,
                server_id=2,
                local_updated_at=datetime.now(UTC),
                server_updated_at=datetime.now(UTC),
                resolution=ConflictResolution.LOCAL_WINS,
            )
        ]

        sync_protocol.clear_conflicts()

        assert len(sync_protocol.conflicts) == 0

    @pytest.mark.asyncio
    async def test_push_offline(self, sync_protocol):
        """Test push when offline."""
        with patch("jefe.cli.sync.protocol.is_online", return_value=False):
            result = await sync_protocol.push()

        assert result.success is False
        assert "not reachable" in result.error_message

    @pytest.mark.asyncio
    async def test_push_nothing_dirty(self, sync_protocol):
        """Test push when no dirty items exist."""
        with patch("jefe.cli.sync.protocol.is_online", return_value=True):
            result = await sync_protocol.push()

        assert result.success is True
        assert result.pushed == 0

    @pytest.mark.asyncio
    async def test_push_with_dirty_project(self, sync_protocol, cache_manager):
        """Test push with a dirty project."""
        # Create and mark a project as dirty
        project = cache_manager.cache_project(
            server_id=1, name="test-project", description="Test"
        )
        cache_manager.mark_project_dirty(project)

        mock_client = AsyncMock()
        mock_client.push = AsyncMock(
            return_value={
                "success": True,
                "projects_synced": 1,
                "skills_synced": 0,
                "installed_skills_synced": 0,
                "harness_configs_synced": 0,
                "conflicts": [],
                "server_id_mappings": {},
            }
        )

        with patch("jefe.cli.sync.protocol.is_online", return_value=True):
            with patch("jefe.cli.sync.protocol.SyncClient") as MockSyncClient:
                MockSyncClient.return_value.__aenter__.return_value = mock_client
                MockSyncClient.return_value.__aexit__.return_value = None
                result = await sync_protocol.push()

        assert result.success is True
        assert result.pushed == 1

    @pytest.mark.asyncio
    async def test_pull_offline(self, sync_protocol):
        """Test pull when offline."""
        with patch("jefe.cli.sync.protocol.is_online", return_value=False):
            result = await sync_protocol.pull()

        assert result.success is False
        assert "not reachable" in result.error_message

    @pytest.mark.asyncio
    async def test_pull_success(self, sync_protocol):
        """Test successful pull."""
        server_time = datetime.now(UTC).isoformat()
        mock_response = {
            "success": True,
            "server_time": server_time,
            "projects": [
                {
                    "server_id": 1,
                    "name": "new-project",
                    "description": "From server",
                    "updated_at": server_time,
                }
            ],
            "skills": [],
            "installed_skills": [],
            "harness_configs": [],
        }

        mock_client = AsyncMock()
        mock_client.pull = AsyncMock(return_value=mock_response)

        with patch("jefe.cli.sync.protocol.is_online", return_value=True):
            with patch("jefe.cli.sync.protocol.SyncClient") as MockSyncClient:
                MockSyncClient.return_value.__aenter__.return_value = mock_client
                MockSyncClient.return_value.__aexit__.return_value = None
                result = await sync_protocol.pull()

        assert result.success is True
        assert result.pulled == 1

    @pytest.mark.asyncio
    async def test_sync_full(self, sync_protocol):
        """Test full sync (push + pull)."""
        server_time = datetime.now(UTC).isoformat()

        mock_client = AsyncMock()
        mock_client.push = AsyncMock(
            return_value={
                "success": True,
                "projects_synced": 0,
                "skills_synced": 0,
                "installed_skills_synced": 0,
                "harness_configs_synced": 0,
                "conflicts": [],
                "server_id_mappings": {},
            }
        )
        mock_client.pull = AsyncMock(
            return_value={
                "success": True,
                "server_time": server_time,
                "projects": [],
                "skills": [],
                "installed_skills": [],
                "harness_configs": [],
            }
        )

        with patch("jefe.cli.sync.protocol.is_online", return_value=True):
            with patch("jefe.cli.sync.protocol.SyncClient") as MockSyncClient:
                MockSyncClient.return_value.__aenter__.return_value = mock_client
                MockSyncClient.return_value.__aexit__.return_value = None
                result = await sync_protocol.sync()

        assert result.success is True

    def test_build_push_request(self, sync_protocol, cache_manager):
        """Test building push request from dirty items."""
        # Create dirty items
        project = cache_manager.cache_project(server_id=1, name="project")
        cache_manager.mark_project_dirty(project)

        skill = cache_manager.cache_skill(
            server_id=10, source_id=1, name="skill", tags=["python"]
        )
        cache_manager.mark_skill_dirty(skill)

        dirty = cache_manager.get_all_dirty_items()
        request = sync_protocol._build_push_request(*dirty)

        assert len(request["projects"]) == 1
        assert len(request["skills"]) == 1
        assert request["projects"][0]["name"] == "project"
        assert request["skills"][0]["name"] == "skill"

    def test_process_push_response_with_conflicts(self, sync_protocol):
        """Test processing push response with conflicts."""
        now = datetime.now(UTC)
        response = {
            "success": True,
            "conflicts": [
                {
                    "entity_type": "project",
                    "local_id": 1,
                    "server_id": 2,
                    "local_updated_at": now.isoformat(),
                    "server_updated_at": (now + timedelta(hours=1)).isoformat(),
                    "resolution": "server_wins",
                }
            ],
        }

        conflicts = sync_protocol._process_push_response(response)

        assert len(conflicts) == 1
        assert conflicts[0].entity_type == EntityType.PROJECT
        assert conflicts[0].resolution == ConflictResolution.SERVER_WINS


class TestSyncProtocolConflictResolution:
    """Tests for conflict resolution in sync protocol."""

    @pytest.mark.asyncio
    async def test_pull_project_no_conflict(self, sync_protocol, cache_manager):
        """Test pulling a project with no conflict."""
        server_time = datetime.now(UTC)

        data = {
            "server_id": 1,
            "name": "new-project",
            "description": "From server",
            "updated_at": server_time.isoformat(),
        }

        conflict = sync_protocol._update_project_from_server(data)

        assert conflict is None
        project = cache_manager.get_project("new-project")
        assert project is not None
        assert project.name == "new-project"

    @pytest.mark.asyncio
    async def test_pull_project_server_wins(self, sync_protocol, cache_manager):
        """Test pulling a project where server wins conflict."""
        old_time = datetime.now(UTC) - timedelta(hours=2)
        new_time = datetime.now(UTC)

        # Create local dirty project with old timestamp
        project = cache_manager.cache_project(server_id=1, name="local-project")
        project.updated_at = old_time
        cache_manager.mark_project_dirty(project)
        cache_manager.projects.set(project)

        # Simulate server update with newer timestamp
        data = {
            "server_id": 1,
            "name": "server-project",
            "description": "Server version",
            "updated_at": new_time.isoformat(),
        }

        conflict = sync_protocol._update_project_from_server(data)

        assert conflict is not None
        assert conflict.resolution == ConflictResolution.SERVER_WINS

        # Verify server data was applied
        updated = cache_manager.projects.get_by_server_id(1)
        assert updated.name == "server-project"

    @pytest.mark.asyncio
    async def test_pull_project_local_wins(self, sync_protocol, cache_manager):
        """Test pulling a project where local wins conflict."""
        old_time = datetime.now(UTC) - timedelta(hours=2)
        new_time = datetime.now(UTC)

        # Create local dirty project with new timestamp
        project = cache_manager.cache_project(server_id=1, name="local-project")
        project.updated_at = new_time
        cache_manager.mark_project_dirty(project)
        cache_manager.projects.set(project)

        # Simulate server update with older timestamp
        data = {
            "server_id": 1,
            "name": "server-project",
            "description": "Server version",
            "updated_at": old_time.isoformat(),
        }

        conflict = sync_protocol._update_project_from_server(data)

        assert conflict is not None
        assert conflict.resolution == ConflictResolution.LOCAL_WINS

        # Verify local data was preserved
        updated = cache_manager.projects.get_by_server_id(1)
        assert updated.name == "local-project"

    @pytest.mark.asyncio
    async def test_pull_skill_server_wins(self, sync_protocol, cache_manager):
        """Test pulling a skill where server wins conflict."""
        old_time = datetime.now(UTC) - timedelta(hours=2)
        new_time = datetime.now(UTC)

        skill = cache_manager.cache_skill(
            server_id=10, source_id=1, name="local-skill", version="1.0.0"
        )
        skill.updated_at = old_time
        cache_manager.mark_skill_dirty(skill)
        cache_manager.skills.set(skill)

        data = {
            "server_id": 10,
            "source_id": 1,
            "name": "server-skill",
            "version": "2.0.0",
            "updated_at": new_time.isoformat(),
        }

        conflict = sync_protocol._update_skill_from_server(data)

        assert conflict is not None
        assert conflict.resolution == ConflictResolution.SERVER_WINS

        updated = cache_manager.skills.get_by_server_id(10)
        assert updated.name == "server-skill"

    @pytest.mark.asyncio
    async def test_pull_installed_skill(self, sync_protocol, cache_manager):
        """Test pulling an installed skill."""
        server_time = datetime.now(UTC)

        data = {
            "server_id": 100,
            "skill_id": 10,
            "harness_id": 1,
            "scope": "global",
            "installed_path": "/path/to/skill",
            "updated_at": server_time.isoformat(),
        }

        conflict = sync_protocol._update_installed_skill_from_server(data)

        assert conflict is None
        installed = cache_manager.installed_skills.get_by_server_id(100)
        assert installed is not None
        assert installed.scope == InstallScope.GLOBAL

    @pytest.mark.asyncio
    async def test_pull_harness_config(self, sync_protocol, cache_manager):
        """Test pulling a harness config."""
        server_time = datetime.now(UTC)

        data = {
            "server_id": 50,
            "harness_id": 1,
            "scope": "project",
            "kind": "shell",
            "path": "/config/path",
            "content": "some config",
            "project_id": 5,
            "updated_at": server_time.isoformat(),
        }

        conflict = sync_protocol._update_harness_config_from_server(data)

        assert conflict is None
        config = cache_manager.harness_configs.get_by_server_id(50)
        assert config is not None
        assert config.scope == ConfigScope.PROJECT
        assert config.project_id == 5


class TestSyncProtocolServerIdMappings:
    """Tests for server ID mapping in sync protocol."""

    def test_apply_server_id_mappings(self, sync_protocol, cache_manager):
        """Test applying server ID mappings from push response."""
        # Create items without server IDs
        project = cache_manager.cache_project(server_id=None, name="new-project")
        # Manually set server_id to None to simulate new item
        project.server_id = None
        cache_manager.projects.set(project)

        mappings = {"project": {str(project.id): 100}}

        sync_protocol._apply_server_id_mappings(
            mappings, [project], [], [], []
        )

        # Verify server ID was set
        updated = cache_manager.get_project("new-project")
        assert updated.server_id == 100
