"""Tests for cache manager."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from jefe.cli.cache.manager import CacheManager
from jefe.cli.cache.models import CacheBase, ConfigScope, InstallScope


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
def manager(mock_get_session):
    """Create a cache manager for testing."""
    mgr = CacheManager(ttl_seconds=300)
    yield mgr
    mgr.close()


def test_cache_manager_cache_project(manager):
    """Test caching a project."""
    project = manager.cache_project(
        server_id=1,
        name="test-project",
        description="A test project",
    )

    assert project.server_id == 1
    assert project.name == "test-project"
    assert project.description == "A test project"
    assert project.dirty is False
    assert project.last_synced is not None


def test_cache_manager_cache_project_update(manager):
    """Test updating an existing cached project."""
    # Create initial project
    manager.cache_project(server_id=1, name="project", description="First")

    # Update it
    updated = manager.cache_project(server_id=1, name="project", description="Second")

    assert updated.description == "Second"
    assert updated.dirty is False

    # Verify only one project exists
    all_projects = manager.get_all_projects()
    assert len(all_projects) == 1


def test_cache_manager_get_project(manager):
    """Test getting a cached project."""
    manager.cache_project(server_id=1, name="findme")

    result = manager.get_project("findme")
    assert result is not None
    assert result.name == "findme"


def test_cache_manager_mark_project_dirty(manager):
    """Test marking a project as dirty."""
    project = manager.cache_project(server_id=1, name="clean-project")
    assert project.dirty is False

    manager.mark_project_dirty(project)

    result = manager.get_project("clean-project")
    assert result is not None
    assert result.dirty is True


def test_cache_manager_is_project_fresh(manager):
    """Test checking project freshness."""
    project = manager.cache_project(server_id=1, name="fresh")
    assert manager.is_project_fresh(project) is True

    # Artificially age the project
    project.last_synced = datetime.now(timezone.utc) - timedelta(seconds=400)
    manager.projects.set(project)

    assert manager.is_project_fresh(project) is False


def test_cache_manager_cache_skill(manager):
    """Test caching a skill."""
    skill = manager.cache_skill(
        server_id=10,
        source_id=5,
        name="test-skill",
        display_name="Test Skill",
        description="A test skill",
        version="1.0.0",
        author="Test Author",
        tags=["python", "cli"],
        metadata={"complexity": "low"},
    )

    assert skill.server_id == 10
    assert skill.source_id == 5
    assert skill.name == "test-skill"
    assert skill.display_name == "Test Skill"
    assert skill.version == "1.0.0"
    assert skill.get_tags_list() == ["python", "cli"]
    assert skill.get_metadata_dict() == {"complexity": "low"}


def test_cache_manager_cache_skill_update(manager):
    """Test updating an existing cached skill."""
    manager.cache_skill(server_id=10, source_id=1, name="skill", version="1.0.0")
    updated = manager.cache_skill(server_id=10, source_id=1, name="skill", version="2.0.0")

    assert updated.version == "2.0.0"
    all_skills = manager.get_all_skills()
    assert len(all_skills) == 1


def test_cache_manager_get_skill(manager):
    """Test getting a cached skill."""
    manager.cache_skill(server_id=10, source_id=1, name="findme")

    result = manager.get_skill("findme")
    assert result is not None
    assert result.name == "findme"


def test_cache_manager_mark_skill_dirty(manager):
    """Test marking a skill as dirty."""
    skill = manager.cache_skill(server_id=10, source_id=1, name="skill")
    assert skill.dirty is False

    manager.mark_skill_dirty(skill)

    result = manager.get_skill("skill")
    assert result is not None
    assert result.dirty is True


def test_cache_manager_cache_installed_skill(manager):
    """Test caching an installed skill."""
    installed = manager.cache_installed_skill(
        server_id=100,
        skill_id=10,
        harness_id=20,
        scope=InstallScope.GLOBAL,
        installed_path="/path/to/skill",
        pinned_version="1.2.3",
    )

    assert installed.server_id == 100
    assert installed.skill_id == 10
    assert installed.harness_id == 20
    assert installed.scope == InstallScope.GLOBAL
    assert installed.installed_path == "/path/to/skill"
    assert installed.pinned_version == "1.2.3"


def test_cache_manager_get_installed_skills_by_scope(manager):
    """Test getting installed skills by scope."""
    manager.cache_installed_skill(
        server_id=1,
        skill_id=10,
        harness_id=1,
        scope=InstallScope.GLOBAL,
        installed_path="/global",
    )
    manager.cache_installed_skill(
        server_id=2,
        skill_id=20,
        harness_id=2,
        scope=InstallScope.PROJECT,
        project_id=5,
        installed_path="/project",
    )

    global_skills = manager.get_installed_skills_by_scope(InstallScope.GLOBAL)
    assert len(global_skills) == 1
    assert global_skills[0].installed_path == "/global"

    project_skills = manager.get_installed_skills_by_scope(InstallScope.PROJECT, project_id=5)
    assert len(project_skills) == 1
    assert project_skills[0].installed_path == "/project"


def test_cache_manager_mark_installed_skill_dirty(manager):
    """Test marking an installed skill as dirty."""
    installed = manager.cache_installed_skill(
        server_id=100,
        skill_id=10,
        harness_id=20,
        scope=InstallScope.GLOBAL,
        installed_path="/path",
    )
    assert installed.dirty is False

    manager.mark_installed_skill_dirty(installed)
    assert installed.dirty is True


def test_cache_manager_cache_harness_config(manager):
    """Test caching a harness config."""
    config = manager.cache_harness_config(
        server_id=50,
        harness_id=1,
        scope=ConfigScope.GLOBAL,
        kind="shell",
        path="/path/to/config",
        content="export VAR=value",
        content_hash="abc123",
    )

    assert config.server_id == 50
    assert config.harness_id == 1
    assert config.scope == ConfigScope.GLOBAL
    assert config.kind == "shell"
    assert config.path == "/path/to/config"
    assert config.content == "export VAR=value"
    assert config.content_hash == "abc123"


def test_cache_manager_get_harness_configs_by_scope(manager):
    """Test getting harness configs by scope."""
    manager.cache_harness_config(
        server_id=1,
        harness_id=1,
        scope=ConfigScope.GLOBAL,
        kind="shell",
        path="/global",
    )
    manager.cache_harness_config(
        server_id=2,
        harness_id=2,
        scope=ConfigScope.PROJECT,
        project_id=10,
        kind="env",
        path="/project",
    )

    global_configs = manager.get_harness_configs_by_scope(ConfigScope.GLOBAL)
    assert len(global_configs) == 1
    assert global_configs[0].path == "/global"

    project_configs = manager.get_harness_configs_by_scope(ConfigScope.PROJECT, project_id=10)
    assert len(project_configs) == 1
    assert project_configs[0].path == "/project"


def test_cache_manager_mark_harness_config_dirty(manager):
    """Test marking a harness config as dirty."""
    config = manager.cache_harness_config(
        server_id=50,
        harness_id=1,
        scope=ConfigScope.GLOBAL,
        kind="shell",
        path="/path",
    )
    assert config.dirty is False

    manager.mark_harness_config_dirty(config)
    assert config.dirty is True


def test_cache_manager_get_all_dirty_items(manager):
    """Test getting all dirty items across entity types."""
    # Create some clean and dirty items
    project = manager.cache_project(server_id=1, name="project1")
    manager.mark_project_dirty(project)

    skill = manager.cache_skill(server_id=10, source_id=1, name="skill1")
    manager.mark_skill_dirty(skill)

    installed = manager.cache_installed_skill(
        server_id=100,
        skill_id=10,
        harness_id=1,
        scope=InstallScope.GLOBAL,
        installed_path="/path",
    )
    manager.mark_installed_skill_dirty(installed)

    config = manager.cache_harness_config(
        server_id=50,
        harness_id=1,
        scope=ConfigScope.GLOBAL,
        kind="shell",
        path="/path",
    )
    manager.mark_harness_config_dirty(config)

    # Add some clean items
    manager.cache_project(server_id=2, name="project2")
    manager.cache_skill(server_id=11, source_id=1, name="skill2")

    # Get all dirty items
    dirty_projects, dirty_skills, dirty_installed, dirty_configs = (
        manager.get_all_dirty_items()
    )

    assert len(dirty_projects) == 1
    assert dirty_projects[0].name == "project1"
    assert len(dirty_skills) == 1
    assert dirty_skills[0].name == "skill1"
    assert len(dirty_installed) == 1
    assert len(dirty_configs) == 1


def test_cache_manager_clear_all_dirty(manager):
    """Test clearing all dirty flags."""
    # Create dirty items
    project = manager.cache_project(server_id=1, name="project")
    manager.mark_project_dirty(project)

    skill = manager.cache_skill(server_id=10, source_id=1, name="skill")
    manager.mark_skill_dirty(skill)

    # Clear all dirty flags
    manager.clear_all_dirty()

    # Verify all dirty flags are cleared
    dirty_projects, dirty_skills, dirty_installed, dirty_configs = (
        manager.get_all_dirty_items()
    )

    assert len(dirty_projects) == 0
    assert len(dirty_skills) == 0
    assert len(dirty_installed) == 0
    assert len(dirty_configs) == 0


def test_cache_manager_close(manager):
    """Test closing the cache manager."""
    # This should not raise any exceptions
    manager.close()
