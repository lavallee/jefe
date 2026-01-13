"""Tests for cache models."""

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from jefe.cli.cache.models import (
    CacheBase,
    CachedHarnessConfig,
    CachedInstalledSkill,
    CachedProject,
    CachedSkill,
    ConfigScope,
    InstallScope,
)


@pytest.fixture
def in_memory_db():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    CacheBase.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


def test_cached_project_create(in_memory_db: Session):
    """Test creating a cached project."""
    project = CachedProject(
        name="test-project",
        description="A test project",
        server_id=1,
        dirty=False,
    )
    in_memory_db.add(project)
    in_memory_db.commit()

    # Verify it was created
    result = in_memory_db.query(CachedProject).filter_by(name="test-project").first()
    assert result is not None
    assert result.name == "test-project"
    assert result.description == "A test project"
    assert result.server_id == 1
    assert result.dirty is False
    assert result.created_at is not None
    assert result.updated_at is not None


def test_cached_project_unique_name(in_memory_db: Session):
    """Test that project names are unique."""
    project1 = CachedProject(name="unique-project", server_id=1)
    in_memory_db.add(project1)
    in_memory_db.commit()

    # Try to create another project with the same name
    project2 = CachedProject(name="unique-project", server_id=2)
    in_memory_db.add(project2)

    with pytest.raises(IntegrityError):
        in_memory_db.commit()


def test_cached_skill_create(in_memory_db: Session):
    """Test creating a cached skill."""
    skill = CachedSkill(
        name="test-skill",
        display_name="Test Skill",
        description="A test skill",
        version="1.0.0",
        author="Test Author",
        source_id=1,
        server_id=10,
        dirty=False,
    )
    in_memory_db.add(skill)
    in_memory_db.commit()

    result = in_memory_db.query(CachedSkill).filter_by(name="test-skill").first()
    assert result is not None
    assert result.name == "test-skill"
    assert result.display_name == "Test Skill"
    assert result.version == "1.0.0"
    assert result.author == "Test Author"
    assert result.server_id == 10


def test_cached_skill_tags(in_memory_db: Session):
    """Test skill tags serialization/deserialization."""
    skill = CachedSkill(name="tagged-skill", server_id=1)
    skill.set_tags_list(["python", "cli", "utility"])
    in_memory_db.add(skill)
    in_memory_db.commit()

    result = in_memory_db.query(CachedSkill).filter_by(name="tagged-skill").first()
    assert result is not None
    tags = result.get_tags_list()
    assert tags == ["python", "cli", "utility"]


def test_cached_skill_metadata(in_memory_db: Session):
    """Test skill metadata serialization/deserialization."""
    skill = CachedSkill(name="metadata-skill", server_id=1)
    metadata = {"complexity": "medium", "runtime": "nodejs", "requires_auth": True}
    skill.set_metadata_dict(metadata)
    in_memory_db.add(skill)
    in_memory_db.commit()

    result = in_memory_db.query(CachedSkill).filter_by(name="metadata-skill").first()
    assert result is not None
    retrieved_metadata = result.get_metadata_dict()
    assert retrieved_metadata == metadata


def test_cached_installed_skill_create(in_memory_db: Session):
    """Test creating a cached installed skill."""
    installed = CachedInstalledSkill(
        skill_id=1,
        harness_id=2,
        scope=InstallScope.GLOBAL,
        project_id=None,
        installed_path="/path/to/skill",
        pinned_version="1.2.3",
        server_id=100,
        dirty=False,
    )
    in_memory_db.add(installed)
    in_memory_db.commit()

    result = (
        in_memory_db.query(CachedInstalledSkill)
        .filter_by(installed_path="/path/to/skill")
        .first()
    )
    assert result is not None
    assert result.skill_id == 1
    assert result.harness_id == 2
    assert result.scope == InstallScope.GLOBAL
    assert result.project_id is None
    assert result.pinned_version == "1.2.3"


def test_cached_installed_skill_project_scope(in_memory_db: Session):
    """Test creating a project-scoped installed skill."""
    installed = CachedInstalledSkill(
        skill_id=5,
        harness_id=3,
        scope=InstallScope.PROJECT,
        project_id=42,
        installed_path="/projects/myproject/.skills/test",
        server_id=200,
    )
    in_memory_db.add(installed)
    in_memory_db.commit()

    result = in_memory_db.query(CachedInstalledSkill).filter_by(skill_id=5).first()
    assert result is not None
    assert result.scope == InstallScope.PROJECT
    assert result.project_id == 42


def test_cached_harness_config_create(in_memory_db: Session):
    """Test creating a cached harness config."""
    config = CachedHarnessConfig(
        harness_id=1,
        scope=ConfigScope.GLOBAL,
        kind="shell",
        path="/path/to/config",
        content="export VAR=value",
        content_hash="abc123",
        project_id=None,
        server_id=50,
        dirty=False,
    )
    in_memory_db.add(config)
    in_memory_db.commit()

    result = (
        in_memory_db.query(CachedHarnessConfig).filter_by(path="/path/to/config").first()
    )
    assert result is not None
    assert result.harness_id == 1
    assert result.scope == ConfigScope.GLOBAL
    assert result.kind == "shell"
    assert result.content == "export VAR=value"
    assert result.content_hash == "abc123"


def test_cached_harness_config_project_scope(in_memory_db: Session):
    """Test creating a project-scoped harness config."""
    config = CachedHarnessConfig(
        harness_id=2,
        scope=ConfigScope.PROJECT,
        kind="python",
        path="/projects/test/.config",
        content="python_version=3.11",
        project_id=99,
        server_id=60,
    )
    in_memory_db.add(config)
    in_memory_db.commit()

    result = in_memory_db.query(CachedHarnessConfig).filter_by(harness_id=2).first()
    assert result is not None
    assert result.scope == ConfigScope.PROJECT
    assert result.project_id == 99


def test_sync_metadata_fields(in_memory_db: Session):
    """Test sync metadata fields are properly set."""
    now = datetime.now()
    project = CachedProject(
        name="sync-test",
        server_id=123,
        dirty=True,
        last_synced=now,
    )
    in_memory_db.add(project)
    in_memory_db.commit()

    result = in_memory_db.query(CachedProject).filter_by(name="sync-test").first()
    assert result is not None
    assert result.server_id == 123
    assert result.dirty is True
    assert result.last_synced is not None
    # Verify timestamps are within a reasonable range
    assert (result.last_synced - now).total_seconds() < 1


def test_nullable_server_id(in_memory_db: Session):
    """Test that server_id can be null for unsynced items."""
    project = CachedProject(
        name="local-only",
        server_id=None,
        dirty=True,
    )
    in_memory_db.add(project)
    in_memory_db.commit()

    result = in_memory_db.query(CachedProject).filter_by(name="local-only").first()
    assert result is not None
    assert result.server_id is None
    assert result.dirty is True
