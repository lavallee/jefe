"""Translation service for syntax and semantic translation with audit logging."""

from __future__ import annotations

import difflib
import logging
from pathlib import Path
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from jefe.data.models.translation_log import TranslationLog, TranslationType
from jefe.data.repositories.translation_log import TranslationLogRepository
from jefe.server.services.translation.semantic import translate_semantic
from jefe.server.services.translation.syntax import (
    HarnessName,
    TranslationError,
    translate_syntax,
)

logger = logging.getLogger(__name__)


class TranslationResult:
    """Result of a translation operation with diff."""

    def __init__(self, output: str, diff: str, log_id: int) -> None:
        """
        Initialize translation result.

        Args:
            output: The translated content
            diff: Unified diff showing changes
            log_id: ID of the created translation log
        """
        self.output = output
        self.diff = diff
        self.log_id = log_id


class TranslationService:
    """Service for managing translations with audit logging."""

    def __init__(self, session: AsyncSession) -> None:
        """
        Initialize the translation service.

        Args:
            session: Database session for logging
        """
        self.session = session
        self.log_repo = TranslationLogRepository(session)

    async def translate(
        self,
        content: str,
        source_harness: HarnessName,
        target_harness: HarnessName,
        config_kind: Literal["settings", "instructions"] = "instructions",
        project_id: int | None = None,
        *,
        translation_type: Literal["syntax", "semantic"] = "syntax",
        api_key: str | None = None,
        model: str | None = None,
    ) -> TranslationResult:
        """
        Translate content between harness formats with logging.

        Args:
            content: The raw content to translate
            source_harness: The harness the content is from
            target_harness: The harness to translate to
            config_kind: Whether this is a settings or instructions config
            project_id: Optional project ID to associate with this translation
            translation_type: Type of translation - "syntax" for rule-based,
                              "semantic" for LLM-powered style adaptation
            api_key: Optional OpenRouter API key for semantic translation
            model: Optional model override for semantic translation

        Returns:
            TranslationResult with output, diff, and log ID

        Raises:
            TranslationError: If translation fails or validation fails
        """
        # Validate harnesses
        self._validate_harness(source_harness)
        self._validate_harness(target_harness)

        # Perform translation based on type
        if translation_type == "semantic":
            output, model_used = await self._translate_semantic(
                content, source_harness, target_harness, config_kind, api_key, model
            )
            log_type = TranslationType.SEMANTIC
            log_model_name = model_used
        else:
            output = self._translate_syntax(
                content, source_harness, target_harness, config_kind
            )
            log_type = TranslationType.SYNTAX
            log_model_name = f"{source_harness}-to-{target_harness}"

        # Generate diff
        diff = self._generate_diff(content, output, source_harness, target_harness)

        # Log the translation
        log = await self.log_repo.create(
            input_text=content,
            output_text=output,
            translation_type=log_type,
            model_name=log_model_name,
            project_id=project_id,
        )

        logger.info(
            "Translation completed: type=%s, model=%s, log_id=%d",
            translation_type,
            log_model_name,
            log.id,
        )

        return TranslationResult(output=output, diff=diff, log_id=log.id)

    def _translate_syntax(
        self,
        content: str,
        source_harness: HarnessName,
        target_harness: HarnessName,
        config_kind: Literal["settings", "instructions"],
    ) -> str:
        """Perform syntax-based translation."""
        try:
            return translate_syntax(content, source_harness, target_harness, config_kind)
        except TranslationError:
            raise
        except Exception as e:
            raise TranslationError(f"Unexpected error during translation: {e}") from e

    async def _translate_semantic(
        self,
        content: str,
        source_harness: HarnessName,
        target_harness: HarnessName,
        config_kind: Literal["settings", "instructions"],
        api_key: str | None,
        model: str | None,
    ) -> tuple[str, str]:
        """Perform semantic translation using LLM.

        Returns:
            Tuple of (translated_content, model_used)
        """
        try:
            result = await translate_semantic(
                content=content,
                source_harness=source_harness,
                target_harness=target_harness,
                config_kind=config_kind,
                api_key=api_key,
                model=model,
            )
            return result.output, result.model_used
        except TranslationError:
            raise
        except Exception as e:
            raise TranslationError(f"Unexpected error during semantic translation: {e}") from e

    async def get_history(
        self,
        project_id: int | None = None,
        translation_type: TranslationType | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[TranslationLog]:
        """
        Retrieve translation history with optional filters.

        Args:
            project_id: Filter by project ID
            translation_type: Filter by translation type
            limit: Maximum number of logs to return
            offset: Number of logs to skip

        Returns:
            List of TranslationLog objects
        """
        if project_id is not None:
            return await self.log_repo.list_by_project(
                project_id=project_id, limit=limit, offset=offset
            )
        elif translation_type is not None:
            return await self.log_repo.list_by_type(
                translation_type=translation_type, limit=limit, offset=offset
            )
        else:
            return await self.log_repo.list_all(limit=limit, offset=offset)

    async def apply_translation(
        self,
        file_path: Path,
        content: str,
    ) -> None:
        """
        Write translated content to a file.

        Args:
            file_path: Path to write the translated content
            content: The translated content to write

        Raises:
            TranslationError: If file writing fails
        """
        try:
            # Ensure parent directory exists
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Write content to file
            file_path.write_text(content, encoding="utf-8")
        except Exception as e:
            raise TranslationError(f"Failed to write file {file_path}: {e}") from e

    def _validate_harness(self, harness: str) -> None:
        """
        Validate that a harness name is supported.

        Args:
            harness: Harness name to validate

        Raises:
            TranslationError: If harness is not supported
        """
        # Valid harness names (including aliases)
        valid_harnesses = {
            "claude-code",
            "claude_code",
            "claudecode",
            "codex_cli",
            "codex-cli",
            "codex",
            "opencode",
            "open-code",
            "gemini_cli",
            "gemini-cli",
            "gemini",
        }

        if harness.lower().replace("-", "_").replace(" ", "_") not in {
            h.replace("-", "_") for h in valid_harnesses
        }:
            raise TranslationError(
                f"Unsupported harness: {harness}. "
                f"Valid harnesses: claude-code, codex_cli, opencode, gemini_cli"
            )

    def _generate_diff(
        self,
        original: str,
        translated: str,
        source_harness: str,
        target_harness: str,
    ) -> str:
        """
        Generate a unified diff between original and translated content.

        Args:
            original: Original content
            translated: Translated content
            source_harness: Source harness name
            target_harness: Target harness name

        Returns:
            Unified diff string
        """
        original_lines = original.splitlines(keepends=True)
        translated_lines = translated.splitlines(keepends=True)

        diff_lines = difflib.unified_diff(
            original_lines,
            translated_lines,
            fromfile=f"{source_harness}",
            tofile=f"{target_harness}",
            lineterm="",
        )

        return "".join(diff_lines)
