"""Tests for semantic translation module."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from jefe.data.database import get_engine
from jefe.data.models.base import Base
from jefe.data.models.translation_log import TranslationType
from jefe.server.llm.openrouter import (
    OpenRouterError,
    OpenRouterRateLimitError,
)
from jefe.server.services.translation import TranslationError
from jefe.server.services.translation.prompts import (
    HARNESS_CONTEXT,
    HARNESS_DISPLAY_NAMES,
    MAX_TRANSLATION_TOKENS,
    RECOMMENDED_MODEL,
    TRANSLATION_TEMPERATURE,
    build_semantic_translation_prompt,
)
from jefe.server.services.translation.semantic import (
    SemanticTranslationResult,
    translate_semantic,
)
from jefe.server.services.translation.service import TranslationService


@pytest.fixture(scope="function")
def test_db_path(tmp_path: Path) -> Path:
    """Create a temporary database file path."""
    return tmp_path / "semantic_translation.db"


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

    async with async_session() as sess:
        yield sess

    await engine.dispose()


@pytest.fixture
async def translation_service(session: AsyncSession) -> TranslationService:
    """Create a TranslationService instance."""
    return TranslationService(session)


@pytest.fixture
def mock_openrouter_response() -> dict[str, Any]:
    """Mock response from OpenRouter API."""
    return {
        "id": "gen-123",
        "model": "anthropic/claude-sonnet-4",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": """<!-- Translated from Claude Code format to Codex CLI format -->

# Overview

This is the translated project overview.

## Getting Started

Run the tests with pytest.
""",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
    }


class TestBuildSemanticTranslationPrompt:
    """Test prompt building functions."""

    def test_build_instructions_prompt(self) -> None:
        """Test building prompt for instruction translation."""
        content = "# Project Overview\n\nThis is my project."
        prompt = build_semantic_translation_prompt(
            content=content,
            source_harness="claude-code",
            target_harness="codex_cli",
            config_kind="instructions",
        )

        # Check prompt contains source and target info
        assert "Claude Code" in prompt
        assert "OpenAI Codex CLI" in prompt
        assert content in prompt
        assert "Translate the above content" in prompt

    def test_build_settings_prompt(self) -> None:
        """Test building prompt for settings translation."""
        content = '{"apiKey": "test", "model": "gpt-4"}'
        prompt = build_semantic_translation_prompt(
            content=content,
            source_harness="claude-code",
            target_harness="codex_cli",
            config_kind="settings",
        )

        # Check prompt contains settings-specific instructions
        assert "settings file" in prompt.lower()
        assert content in prompt
        assert "JSON" in prompt or "TOML" in prompt

    def test_harness_context_included(self) -> None:
        """Test that harness context is included in prompts."""
        prompt = build_semantic_translation_prompt(
            content="# Test",
            source_harness="claude-code",
            target_harness="gemini_cli",
            config_kind="instructions",
        )

        # Check context information is included
        assert "CLAUDE.md" in prompt
        assert "GEMINI.md" in prompt

    def test_all_harnesses_have_context(self) -> None:
        """Test that all supported harnesses have context defined."""
        for harness in ["claude-code", "codex_cli", "opencode", "gemini_cli"]:
            assert harness in HARNESS_CONTEXT
            assert harness in HARNESS_DISPLAY_NAMES


class TestSemanticTranslationResult:
    """Test SemanticTranslationResult class."""

    def test_result_creation(self) -> None:
        """Test creating a translation result."""
        result = SemanticTranslationResult(
            output="Translated content",
            model_used="anthropic/claude-sonnet-4",
        )

        assert result.output == "Translated content"
        assert result.model_used == "anthropic/claude-sonnet-4"


class TestTranslateSemantic:
    """Test the translate_semantic function."""

    @pytest.mark.asyncio
    async def test_same_harness_returns_original(self) -> None:
        """Test that translating to same harness returns original content."""
        content = "# Test Content"

        result = await translate_semantic(
            content=content,
            source_harness="claude-code",
            target_harness="claude-code",
            api_key="test-key",
        )

        assert result.output == content
        assert result.model_used == "passthrough"

    @pytest.mark.asyncio
    async def test_translate_semantic_success(
        self, mock_openrouter_response: dict[str, Any]
    ) -> None:
        """Test successful semantic translation."""
        content = "# Original Content\n\nThis is the original."

        with patch(
            "jefe.server.services.translation.semantic.OpenRouterClient"
        ) as mock_cls:
            mock_instance = AsyncMock()
            mock_instance.complete = AsyncMock(
                return_value=mock_openrouter_response["choices"][0]["message"][
                    "content"
                ]
            )
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_cls.return_value = mock_instance

            result = await translate_semantic(
                content=content,
                source_harness="claude-code",
                target_harness="codex_cli",
                api_key="test-key",
            )

        assert result.output is not None
        assert "Overview" in result.output
        assert result.model_used == RECOMMENDED_MODEL

    @pytest.mark.asyncio
    async def test_translate_semantic_with_custom_model(
        self, mock_openrouter_response: dict[str, Any]  # noqa: ARG002
    ) -> None:
        """Test semantic translation with custom model."""
        content = "# Test"
        custom_model = "anthropic/claude-3-opus"

        with patch(
            "jefe.server.services.translation.semantic.OpenRouterClient"
        ) as mock_cls:
            mock_instance = AsyncMock()
            mock_instance.complete = AsyncMock(return_value="# Translated\n")
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_cls.return_value = mock_instance

            result = await translate_semantic(
                content=content,
                source_harness="claude-code",
                target_harness="codex_cli",
                api_key="test-key",
                model=custom_model,
            )

        assert result.model_used == custom_model
        mock_cls.assert_called_once_with(api_key="test-key", model=custom_model)

    @pytest.mark.asyncio
    async def test_translate_semantic_api_error(self) -> None:
        """Test handling of API errors during translation."""
        content = "# Test"

        with patch(
            "jefe.server.services.translation.semantic.OpenRouterClient"
        ) as mock_cls:
            mock_instance = AsyncMock()
            mock_instance.complete = AsyncMock(
                side_effect=OpenRouterError("API error")
            )
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_cls.return_value = mock_instance

            with pytest.raises(TranslationError) as exc_info:
                await translate_semantic(
                    content=content,
                    source_harness="claude-code",
                    target_harness="codex_cli",
                    api_key="test-key",
                )

            assert "LLM translation failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_translate_semantic_rate_limit_error(self) -> None:
        """Test handling of rate limit errors."""
        content = "# Test"

        with patch(
            "jefe.server.services.translation.semantic.OpenRouterClient"
        ) as mock_cls:
            mock_instance = AsyncMock()
            mock_instance.complete = AsyncMock(
                side_effect=OpenRouterRateLimitError("Rate limit exceeded")
            )
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_cls.return_value = mock_instance

            with pytest.raises(TranslationError) as exc_info:
                await translate_semantic(
                    content=content,
                    source_harness="claude-code",
                    target_harness="codex_cli",
                    api_key="test-key",
                )

            assert "LLM translation failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_output_cleanup_removes_code_blocks(self) -> None:
        """Test that code blocks are removed from output."""
        content = "# Test"
        wrapped_response = "```markdown\n# Translated Content\n```"

        with patch(
            "jefe.server.services.translation.semantic.OpenRouterClient"
        ) as mock_cls:
            mock_instance = AsyncMock()
            mock_instance.complete = AsyncMock(return_value=wrapped_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_cls.return_value = mock_instance

            result = await translate_semantic(
                content=content,
                source_harness="claude-code",
                target_harness="codex_cli",
                api_key="test-key",
            )

        # Should not contain the markdown code block markers
        assert not result.output.startswith("```")
        assert "# Translated Content" in result.output


class TestTranslationServiceSemantic:
    """Test semantic translation through TranslationService."""

    @pytest.mark.asyncio
    async def test_service_semantic_translation(
        self, translation_service: TranslationService
    ) -> None:
        """Test semantic translation through the service."""
        content = "# Original Content"

        with patch(
            "jefe.server.services.translation.service.translate_semantic"
        ) as mock_translate:
            mock_translate.return_value = SemanticTranslationResult(
                output="# Translated Content\n",
                model_used="anthropic/claude-sonnet-4",
            )

            result = await translation_service.translate(
                content=content,
                source_harness="claude-code",
                target_harness="codex_cli",
                translation_type="semantic",
                api_key="test-key",
            )

        assert result.output == "# Translated Content\n"
        assert result.log_id is not None

        # Verify the log was created with SEMANTIC type
        logs = await translation_service.get_history()
        assert len(logs) == 1
        assert logs[0].translation_type == TranslationType.SEMANTIC
        assert logs[0].model_name == "anthropic/claude-sonnet-4"

    @pytest.mark.asyncio
    async def test_service_semantic_with_custom_model(
        self, translation_service: TranslationService
    ) -> None:
        """Test semantic translation with custom model through service."""
        content = "# Original"
        custom_model = "anthropic/claude-3-opus"

        with patch(
            "jefe.server.services.translation.service.translate_semantic"
        ) as mock_translate:
            mock_translate.return_value = SemanticTranslationResult(
                output="# Translated\n",
                model_used=custom_model,
            )

            await translation_service.translate(
                content=content,
                source_harness="claude-code",
                target_harness="codex_cli",
                translation_type="semantic",
                model=custom_model,
            )

        # Verify model was passed to translate_semantic
        mock_translate.assert_called_once()
        call_kwargs = mock_translate.call_args.kwargs
        assert call_kwargs["model"] == custom_model

        # Verify log has correct model
        logs = await translation_service.get_history()
        assert logs[0].model_name == custom_model

    @pytest.mark.asyncio
    async def test_service_syntax_vs_semantic_logs_different_types(
        self, translation_service: TranslationService
    ) -> None:
        """Test that syntax and semantic translations log different types."""
        content = "# Test Content"

        # Perform syntax translation
        await translation_service.translate(
            content=content,
            source_harness="claude-code",
            target_harness="codex_cli",
            translation_type="syntax",
        )

        # Perform semantic translation
        with patch(
            "jefe.server.services.translation.service.translate_semantic"
        ) as mock_translate:
            mock_translate.return_value = SemanticTranslationResult(
                output="# Translated\n",
                model_used="anthropic/claude-sonnet-4",
            )

            await translation_service.translate(
                content=content,
                source_harness="claude-code",
                target_harness="codex_cli",
                translation_type="semantic",
                api_key="test-key",
            )

        # Check both translations are logged correctly
        logs = await translation_service.get_history()
        assert len(logs) == 2

        # Find syntax and semantic logs
        syntax_logs = [log for log in logs if log.translation_type == TranslationType.SYNTAX]
        semantic_logs = [log for log in logs if log.translation_type == TranslationType.SEMANTIC]

        assert len(syntax_logs) == 1
        assert len(semantic_logs) == 1

        # Verify syntax log model name format
        assert "claude-code-to-codex_cli" in syntax_logs[0].model_name

    @pytest.mark.asyncio
    async def test_service_semantic_error_propagation(
        self, translation_service: TranslationService
    ) -> None:
        """Test that semantic translation errors are properly propagated."""
        content = "# Test"

        with patch(
            "jefe.server.services.translation.service.translate_semantic"
        ) as mock_translate:
            mock_translate.side_effect = TranslationError("LLM error")

            with pytest.raises(TranslationError) as exc_info:
                await translation_service.translate(
                    content=content,
                    source_harness="claude-code",
                    target_harness="codex_cli",
                    translation_type="semantic",
                )

            assert "LLM error" in str(exc_info.value)


class TestPromptConstants:
    """Test prompt configuration constants."""

    def test_recommended_model_is_valid(self) -> None:
        """Test that recommended model is a valid OpenRouter model ID."""
        assert "/" in RECOMMENDED_MODEL  # OpenRouter format: provider/model

    def test_translation_temperature_is_reasonable(self) -> None:
        """Test translation temperature is in reasonable range."""
        assert 0.0 <= TRANSLATION_TEMPERATURE <= 1.0

    def test_max_tokens_is_reasonable(self) -> None:
        """Test max tokens is in reasonable range."""
        assert 1000 <= MAX_TRANSLATION_TOKENS <= 8192
