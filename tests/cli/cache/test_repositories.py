"""Tests for cache repositories."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from jefe.cli.cache.models import (
    CacheBase,
    CachedHarnessConfig,
    CachedInstalledSkill,
    CachedProject,
    CachedSkill,
    ConfigScope,
    InstallScope,
)
from jefe.cli.cache.repositories import (
    HarnessConfigRepository,
    InstalledSkillRepository,
    ProjectRepository,
    SkillRepository,
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

    with (
        patch("jefe.cli.cache.repositories.get_cache_session", side_effect=_get_session),
        patch("jefe.cli.cache.repositories.init_cache_db"),
    ):
        yield


def test_project_repository_get_by_server_id(mock_get_session):
    """Test getting a project by server ID."""
    repo = ProjectRepository()
    project = CachedProject(name="test-project", server_id=100, dirty=False)
    repo.set(project)

    result = repo.get_by_server_id(100)
    assert result is not None
    assert result.name == "test-project"
    assert result.server_id == 100
    repo.close()


def test_project_repository_get_by_name(mock_get_session):
    """Test getting a project by name."""
    repo = ProjectRepository()
    project = CachedProject(name="unique-project", server_id=200, dirty=False)
    repo.set(project)

    result = repo.get_by_name("unique-project")
    assert result is not None
    assert result.name == "unique-project"
    assert result.server_id == 200
    repo.close()


def test_project_repository_get_all(mock_get_session):
    """Test getting all projects."""
    repo = ProjectRepository()
    project1 = CachedProject(name="project1", server_id=1)
    project2 = CachedProject(name="project2", server_id=2)
    repo.set_many([project1, project2])

    results = repo.get_all()
    assert len(results) == 2
    assert {p.name for p in results} == {"project1", "project2"}
    repo.close()


def test_repository_is_fresh_within_ttl(mock_get_session):
    """Test is_fresh returns True for items within TTL."""
    repo = ProjectRepository(ttl_seconds=300)
    project = CachedProject(
        name="fresh-project",
        server_id=1,
        last_synced=datetime.now(UTC),
        dirty=False,
    )
    repo.set(project)

    assert repo.is_fresh(project) is True
    repo.close()


def test_repository_is_fresh_outside_ttl(mock_get_session):
    """Test is_fresh returns False for items outside TTL."""
    repo = ProjectRepository(ttl_seconds=300)
    old_time = datetime.now(UTC) - timedelta(seconds=400)
    project = CachedProject(
        name="stale-project",
        server_id=1,
        last_synced=old_time,
        dirty=False,
    )
    repo.set(project)

    assert repo.is_fresh(project) is False
    repo.close()


def test_repository_is_fresh_no_sync_time(mock_get_session):
    """Test is_fresh returns False when last_synced is None."""
    repo = ProjectRepository()
    project = CachedProject(
        name="never-synced",
        server_id=1,
        last_synced=None,
        dirty=False,
    )
    repo.set(project)

    assert repo.is_fresh(project) is False
    repo.close()


def test_repository_mark_dirty(mock_get_session):
    """Test marking an item as dirty."""
    repo = ProjectRepository()
    project = CachedProject(name="clean-project", server_id=1, dirty=False)
    repo.set(project)

    repo.mark_dirty(project)
    result = repo.get_by_server_id(1)
    assert result is not None
    assert result.dirty is True
    repo.close()


def test_repository_get_dirty(mock_get_session):
    """Test getting all dirty items."""
    repo = ProjectRepository()
    clean = CachedProject(name="clean", server_id=1, dirty=False)
    dirty1 = CachedProject(name="dirty1", server_id=2, dirty=True)
    dirty2 = CachedProject(name="dirty2", server_id=3, dirty=True)
    repo.set_many([clean, dirty1, dirty2])

    results = repo.get_dirty()
    assert len(results) == 2
    assert {p.name for p in results} == {"dirty1", "dirty2"}
    repo.close()


def test_repository_clear_dirty(mock_get_session):
    """Test clearing dirty flag."""
    repo = ProjectRepository()
    project = CachedProject(name="dirty-project", server_id=1, dirty=True)
    repo.set(project)

    repo.clear_dirty(project)
    result = repo.get_by_server_id(1)
    assert result is not None
    assert result.dirty is False
    assert result.last_synced is not None
    repo.close()


def test_repository_clear_all_dirty(mock_get_session):
    """Test clearing all dirty flags."""
    repo = ProjectRepository()
    dirty1 = CachedProject(name="dirty1", server_id=1, dirty=True)
    dirty2 = CachedProject(name="dirty2", server_id=2, dirty=True)
    repo.set_many([dirty1, dirty2])

    repo.clear_all_dirty()
    results = repo.get_dirty()
    assert len(results) == 0
    repo.close()


def test_repository_delete(mock_get_session):
    """Test deleting an item."""
    repo = ProjectRepository()
    project = CachedProject(name="to-delete", server_id=1)
    repo.set(project)

    assert repo.get_by_server_id(1) is not None
    repo.delete(project)
    assert repo.get_by_server_id(1) is None
    repo.close()


def test_skill_repository_get_by_name(mock_get_session):
    """Test getting a skill by name."""
    repo = SkillRepository()
    skill = CachedSkill(name="test-skill", server_id=1)
    repo.set(skill)

    result = repo.get_by_name("test-skill")
    assert result is not None
    assert result.name == "test-skill"
    repo.close()


def test_skill_repository_get_by_source(mock_get_session):
    """Test getting skills by source ID."""
    repo = SkillRepository()
    skill1 = CachedSkill(name="skill1", server_id=1, source_id=10)
    skill2 = CachedSkill(name="skill2", server_id=2, source_id=10)
    skill3 = CachedSkill(name="skill3", server_id=3, source_id=20)
    repo.set_many([skill1, skill2, skill3])

    results = repo.get_by_source(10)
    assert len(results) == 2
    assert {s.name for s in results} == {"skill1", "skill2"}
    repo.close()


def test_installed_skill_repository_get_by_skill_id(mock_get_session):
    """Test getting installed skills by skill ID."""
    repo = InstalledSkillRepository()
    installed1 = CachedInstalledSkill(
        skill_id=1,
        harness_id=1,
        scope=InstallScope.GLOBAL,
        installed_path="/path1",
        server_id=100,
    )
    installed2 = CachedInstalledSkill(
        skill_id=1,
        harness_id=2,
        scope=InstallScope.PROJECT,
        installed_path="/path2",
        server_id=101,
    )
    repo.set_many([installed1, installed2])

    results = repo.get_by_skill_id(1)
    assert len(results) == 2
    repo.close()


def test_installed_skill_repository_get_by_scope(mock_get_session):
    """Test getting installed skills by scope."""
    repo = InstalledSkillRepository()
    global_skill = CachedInstalledSkill(
        skill_id=1,
        harness_id=1,
        scope=InstallScope.GLOBAL,
        installed_path="/global",
        server_id=1,
    )
    project_skill = CachedInstalledSkill(
        skill_id=2,
        harness_id=2,
        scope=InstallScope.PROJECT,
        project_id=10,
        installed_path="/project",
        server_id=2,
    )
    repo.set_many([global_skill, project_skill])

    global_results = repo.get_by_scope(InstallScope.GLOBAL)
    assert len(global_results) == 1
    assert global_results[0].installed_path == "/global"

    project_results = repo.get_by_scope(InstallScope.PROJECT, project_id=10)
    assert len(project_results) == 1
    assert project_results[0].installed_path == "/project"
    repo.close()


def test_harness_config_repository_get_by_harness_id(mock_get_session):
    """Test getting configs by harness ID."""
    repo = HarnessConfigRepository()
    config1 = CachedHarnessConfig(
        harness_id=1,
        scope=ConfigScope.GLOBAL,
        kind="shell",
        path="/config1",
        server_id=1,
    )
    config2 = CachedHarnessConfig(
        harness_id=1,
        scope=ConfigScope.GLOBAL,
        kind="env",
        path="/config2",
        server_id=2,
    )
    repo.set_many([config1, config2])

    results = repo.get_by_harness_id(1)
    assert len(results) == 2
    repo.close()


def test_harness_config_repository_get_by_scope(mock_get_session):
    """Test getting configs by scope."""
    repo = HarnessConfigRepository()
    global_config = CachedHarnessConfig(
        harness_id=1,
        scope=ConfigScope.GLOBAL,
        kind="shell",
        path="/global",
        server_id=1,
    )
    project_config = CachedHarnessConfig(
        harness_id=2,
        scope=ConfigScope.PROJECT,
        project_id=10,
        kind="env",
        path="/project",
        server_id=2,
    )
    repo.set_many([global_config, project_config])

    global_results = repo.get_by_scope(ConfigScope.GLOBAL)
    assert len(global_results) == 1
    assert global_results[0].path == "/global"

    project_results = repo.get_by_scope(ConfigScope.PROJECT, project_id=10)
    assert len(project_results) == 1
    assert project_results[0].path == "/project"
    repo.close()


def test_harness_config_repository_get_by_path(mock_get_session):
    """Test getting config by path."""
    repo = HarnessConfigRepository()
    config = CachedHarnessConfig(
        harness_id=1,
        scope=ConfigScope.GLOBAL,
        kind="shell",
        path="/unique/path",
        server_id=1,
    )
    repo.set(config)

    result = repo.get_by_path("/unique/path")
    assert result is not None
    assert result.path == "/unique/path"
    repo.close()
