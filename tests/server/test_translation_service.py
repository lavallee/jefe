"""Tests for translation service."""

from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from jefe.data.database import get_engine
from jefe.data.models.base import Base
from jefe.data.models.project import Project
from jefe.data.models.translation_log import TranslationType
from jefe.data.repositories.project import ProjectRepository
from jefe.server.services.translation import TranslationError
from jefe.server.services.translation.service import TranslationService


@pytest.fixture(scope="function")
def test_db_path(tmp_path: Path) -> Path:
    """Create a temporary database file path."""
    return tmp_path / "translation_service.db"


@pytest.fixture(scope="function")
async def session(test_db_path: Path) -> AsyncSession:
    """Create an async session with all tables."""
    engine = get_engine(f"sqlite+aiosqlite:///{test_db_path}")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        yield session

    await engine.dispose()


@pytest.fixture
async def translation_service(session: AsyncSession) -> TranslationService:
    """Create a TranslationService instance."""
    return TranslationService(session)


@pytest.fixture
async def test_project(session: AsyncSession) -> Project:
    """Create a test project."""
    project_repo = ProjectRepository(session)
    return await project_repo.create(name="test-project", description="Test project")


class TestTranslationService:
    """Tests for TranslationService."""

    async def test_translate_basic(
        self, translation_service: TranslationService
    ) -> None:
        """Test basic translation between harnesses."""
        content = """# Project Overview

This is a test project.

## Getting Started

Run the tests.
"""
        result = await translation_service.translate(
            content=content,
            source_harness="claude-code",
            target_harness="codex_cli",
            config_kind="instructions",
        )

        # Check output contains translation
        assert result.output is not None
        assert len(result.output) > 0
        assert "<!-- Translated from Claude Code format to Codex CLI format -->" in result.output

        # Check diff is generated
        assert result.diff is not None
        assert "claude-code" in result.diff
        assert "codex_cli" in result.diff

        # Check log was created
        assert result.log_id is not None

    async def test_translate_with_project(
        self, translation_service: TranslationService, test_project: Project
    ) -> None:
        """Test translation associated with a project."""
        content = "# Overview\n\nProject content."

        result = await translation_service.translate(
            content=content,
            source_harness="codex_cli",
            target_harness="claude-code",
            config_kind="instructions",
            project_id=test_project.id,
        )

        assert result.log_id is not None

        # Verify the log has the project association
        logs = await translation_service.get_history(project_id=test_project.id)
        assert len(logs) == 1
        assert logs[0].id == result.log_id
        assert logs[0].project_id == test_project.id

    async def test_translate_settings(
        self, translation_service: TranslationService
    ) -> None:
        """Test translation of settings files."""
        content = '{"apiKey": "test", "maxTokens": 1000}'

        result = await translation_service.translate(
            content=content,
            source_harness="claude-code",
            target_harness="codex_cli",
            config_kind="settings",
        )

        # Should convert to TOML
        assert result.output is not None
        assert "api_key" in result.output
        assert "max_tokens" in result.output

    async def test_translate_same_harness(
        self, translation_service: TranslationService
    ) -> None:
        """Test that translating to the same harness returns unchanged content."""
        content = "# Test\n\nContent"

        result = await translation_service.translate(
            content=content,
            source_harness="claude-code",
            target_harness="claude-code",
        )

        # Content should be unchanged
        assert result.output == content

        # Diff should be minimal or empty
        assert result.diff is not None

    async def test_translate_invalid_harness_source(
        self, translation_service: TranslationService
    ) -> None:
        """Test translation with invalid source harness."""
        content = "# Test"

        with pytest.raises(TranslationError) as exc_info:
            await translation_service.translate(
                content=content,
                source_harness="invalid-harness",
                target_harness="claude-code",
            )

        assert "Unsupported harness" in str(exc_info.value)

    async def test_translate_invalid_harness_target(
        self, translation_service: TranslationService
    ) -> None:
        """Test translation with invalid target harness."""
        content = "# Test"

        with pytest.raises(TranslationError) as exc_info:
            await translation_service.translate(
                content=content,
                source_harness="claude-code",
                target_harness="invalid-harness",
            )

        assert "Unsupported harness" in str(exc_info.value)

    async def test_translate_invalid_json_settings(
        self, translation_service: TranslationService
    ) -> None:
        """Test translation with invalid JSON settings."""
        content = '{"invalid json'

        with pytest.raises(TranslationError) as exc_info:
            await translation_service.translate(
                content=content,
                source_harness="claude-code",
                target_harness="codex_cli",
                config_kind="settings",
            )

        assert "Failed to parse JSON" in str(exc_info.value)

    async def test_get_history_all(
        self, translation_service: TranslationService
    ) -> None:
        """Test retrieving all translation history."""
        # Create multiple translations
        for i in range(3):
            await translation_service.translate(
                content=f"# Test {i}",
                source_harness="claude-code",
                target_harness="codex_cli",
            )

        logs = await translation_service.get_history()
        assert len(logs) == 3

    async def test_get_history_with_pagination(
        self, translation_service: TranslationService
    ) -> None:
        """Test retrieving history with pagination."""
        # Create multiple translations
        for i in range(5):
            await translation_service.translate(
                content=f"# Test {i}",
                source_harness="claude-code",
                target_harness="codex_cli",
            )

        # Get first page
        logs_page1 = await translation_service.get_history(limit=2, offset=0)
        assert len(logs_page1) == 2

        # Get second page
        logs_page2 = await translation_service.get_history(limit=2, offset=2)
        assert len(logs_page2) == 2

        # Verify they're different
        assert logs_page1[0].id != logs_page2[0].id

    async def test_get_history_by_project(
        self, translation_service: TranslationService, test_project: Project
    ) -> None:
        """Test retrieving history filtered by project."""
        # Create translation with project
        await translation_service.translate(
            content="# Project Test",
            source_harness="claude-code",
            target_harness="codex_cli",
            project_id=test_project.id,
        )

        # Create translation without project
        await translation_service.translate(
            content="# No Project",
            source_harness="claude-code",
            target_harness="codex_cli",
        )

        # Filter by project
        logs = await translation_service.get_history(project_id=test_project.id)
        assert len(logs) == 1
        assert logs[0].project_id == test_project.id

    async def test_get_history_by_type(
        self, translation_service: TranslationService
    ) -> None:
        """Test retrieving history filtered by translation type."""
        # Create syntax translations
        await translation_service.translate(
            content="# Test",
            source_harness="claude-code",
            target_harness="codex_cli",
        )

        # Filter by type
        logs = await translation_service.get_history(
            translation_type=TranslationType.SYNTAX
        )
        assert len(logs) >= 1
        assert all(log.translation_type == TranslationType.SYNTAX for log in logs)

    async def test_apply_translation(
        self, translation_service: TranslationService, tmp_path: Path
    ) -> None:
        """Test writing translated content to a file."""
        content = "# Translated Content\n\nThis is the translated version."
        output_file = tmp_path / "output" / "CLAUDE.md"

        await translation_service.apply_translation(
            file_path=output_file,
            content=content,
            allowed_base_dir=tmp_path,
        )

        # Verify file was created
        assert output_file.exists()

        # Verify content matches
        written_content = output_file.read_text(encoding="utf-8")
        assert written_content == content

    async def test_apply_translation_creates_directory(
        self, translation_service: TranslationService, tmp_path: Path
    ) -> None:
        """Test that apply_translation creates parent directories."""
        content = "# Test"
        output_file = tmp_path / "nested" / "deep" / "directory" / "file.md"

        await translation_service.apply_translation(
            file_path=output_file,
            content=content,
            allowed_base_dir=tmp_path,
        )

        # Verify directory was created
        assert output_file.parent.exists()
        assert output_file.exists()

    async def test_apply_translation_overwrites_existing(
        self, translation_service: TranslationService, tmp_path: Path
    ) -> None:
        """Test that apply_translation overwrites existing files."""
        output_file = tmp_path / "existing.md"
        output_file.write_text("Old content", encoding="utf-8")

        new_content = "# New Content"
        await translation_service.apply_translation(
            file_path=output_file,
            content=new_content,
            allowed_base_dir=tmp_path,
        )

        written_content = output_file.read_text(encoding="utf-8")
        assert written_content == new_content

    async def test_apply_translation_invalid_path(
        self, translation_service: TranslationService, tmp_path: Path
    ) -> None:
        """Test apply_translation with an invalid path."""
        # Try to write to a file in a read-only location (simulated)
        output_file = tmp_path / "readonly" / "file.md"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.parent.chmod(0o444)  # Make directory read-only

        with pytest.raises(TranslationError) as exc_info:
            await translation_service.apply_translation(
                file_path=output_file,
                content="# Test",
                allowed_base_dir=tmp_path,
            )

        assert "Failed to write file" in str(exc_info.value)

        # Clean up
        output_file.parent.chmod(0o755)

    async def test_apply_translation_blocks_path_traversal(
        self, translation_service: TranslationService, tmp_path: Path
    ) -> None:
        """Test that path traversal attacks are blocked."""
        # Try to write outside the allowed base directory using path traversal
        malicious_file = tmp_path / ".." / "malicious.md"

        with pytest.raises(TranslationError) as exc_info:
            await translation_service.apply_translation(
                file_path=malicious_file,
                content="# Malicious",
                allowed_base_dir=tmp_path,
            )

        assert "outside allowed directory" in str(exc_info.value)

    async def test_apply_translation_blocks_absolute_path_outside_base(
        self, translation_service: TranslationService, tmp_path: Path
    ) -> None:
        """Test that absolute paths outside allowed directory are blocked."""
        malicious_file = Path("/etc/malicious.md")

        with pytest.raises(TranslationError) as exc_info:
            await translation_service.apply_translation(
                file_path=malicious_file,
                content="# Malicious",
                allowed_base_dir=tmp_path,
            )

        # Could be blocked by either "outside allowed" or "system directory" check
        error_msg = str(exc_info.value)
        assert "outside allowed directory" in error_msg or "system directory" in error_msg

    async def test_apply_translation_blocks_sensitive_paths(
        self, translation_service: TranslationService
    ) -> None:
        """Test that writes to sensitive system directories are blocked."""
        # Even if we allow the parent directory, system paths should be blocked
        import os
        import platform

        # Only test if not running as root (where /etc might be writable)
        if os.geteuid() != 0:
            # Use the appropriate /etc path for the platform
            etc_path = "/private/etc" if platform.system() == "Darwin" else "/etc"
            with pytest.raises(TranslationError) as exc_info:
                await translation_service.apply_translation(
                    file_path=Path(f"{etc_path}/passwd.backup"),
                    content="# Malicious",
                    allowed_base_dir=Path("/"),  # Allow root but block /etc
                )

            assert "system directory" in str(exc_info.value)

    async def test_diff_generation(
        self, translation_service: TranslationService
    ) -> None:
        """Test that diff is properly generated."""
        content = """# Project Overview

Original content here.
"""
        result = await translation_service.translate(
            content=content,
            source_harness="claude-code",
            target_harness="codex_cli",
        )

        # Check diff contains both harness names
        assert "claude-code" in result.diff
        assert "codex_cli" in result.diff

        # Check diff shows changes (should have + and - lines if content changed)
        if content != result.output:
            assert ("+" in result.diff or "-" in result.diff)

    async def test_translation_logs_model_name(
        self, translation_service: TranslationService
    ) -> None:
        """Test that translation logs record the model name correctly."""
        await translation_service.translate(
            content="# Test",
            source_harness="claude-code",
            target_harness="gemini_cli",
        )

        logs = await translation_service.get_history()
        assert len(logs) == 1
        assert logs[0].model_name == "claude-code-to-gemini_cli"

    async def test_translation_preserves_content_integrity(
        self, translation_service: TranslationService
    ) -> None:
        """Test that translation preserves content integrity."""
        content = """# Project Overview

This project contains:
- Feature A
- Feature B

## Code Blocks

```python
def example():
    return "test"
```

## Links

Visit [example.com](https://example.com) for more.
"""
        result = await translation_service.translate(
            content=content,
            source_harness="claude-code",
            target_harness="codex_cli",
        )

        # Core content should be preserved
        assert "Feature A" in result.output
        assert "Feature B" in result.output
        assert "def example():" in result.output
        assert "example.com" in result.output

    async def test_multiple_translations_in_sequence(
        self, translation_service: TranslationService
    ) -> None:
        """Test performing multiple translations in sequence."""
        content = "# Original"

        # Translate claude -> codex
        result1 = await translation_service.translate(
            content=content,
            source_harness="claude-code",
            target_harness="codex_cli",
        )

        # Translate codex -> gemini
        result2 = await translation_service.translate(
            content=result1.output,
            source_harness="codex_cli",
            target_harness="gemini_cli",
        )

        # Both should have logs
        logs = await translation_service.get_history()
        assert len(logs) == 2
        assert logs[0].id == result1.log_id
        assert logs[1].id == result2.log_id
