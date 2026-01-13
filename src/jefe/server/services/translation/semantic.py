"""Semantic translation using LLM for style-adapted translations.

This module provides LLM-powered translation that adapts prompting style
while preserving meaning when converting between harness formats.
"""

from __future__ import annotations

import logging
from typing import Literal

from jefe.server.llm.openrouter import OpenRouterClient, OpenRouterError
from jefe.server.services.translation.prompts import (
    MAX_TRANSLATION_TOKENS,
    RECOMMENDED_MODEL,
    TRANSLATION_TEMPERATURE,
    build_semantic_translation_prompt,
)
from jefe.server.services.translation.syntax import HarnessName, TranslationError

logger = logging.getLogger(__name__)


class SemanticTranslationResult:
    """Result of a semantic translation operation."""

    def __init__(self, output: str, model_used: str) -> None:
        """
        Initialize semantic translation result.

        Args:
            output: The translated content
            model_used: The model that performed the translation
        """
        self.output = output
        self.model_used = model_used


async def translate_semantic(
    content: str,
    source_harness: HarnessName,
    target_harness: HarnessName,
    config_kind: Literal["settings", "instructions"] = "instructions",
    *,
    api_key: str | None = None,
    model: str | None = None,
) -> SemanticTranslationResult:
    """Translate content using LLM for semantic adaptation.

    This function uses an LLM to translate content between harness formats,
    adapting the prompting style while preserving meaning.

    Args:
        content: The content to translate
        source_harness: The source harness name
        target_harness: The target harness name
        config_kind: Whether this is settings or instructions
        api_key: Optional OpenRouter API key (falls back to env var)
        model: Optional model override (defaults to recommended model)

    Returns:
        SemanticTranslationResult with output and model used

    Raises:
        TranslationError: If translation fails
    """
    if source_harness == target_harness:
        logger.info("Source and target harness are the same, returning original content")
        return SemanticTranslationResult(output=content, model_used="passthrough")

    # Build the translation prompt
    prompt = build_semantic_translation_prompt(
        content=content,
        source_harness=source_harness,
        target_harness=target_harness,
        config_kind=config_kind,
    )

    # Use specified model or default
    model_to_use = model or RECOMMENDED_MODEL

    logger.info(
        "Starting semantic translation from %s to %s using model %s",
        source_harness,
        target_harness,
        model_to_use,
    )

    try:
        async with OpenRouterClient(api_key=api_key, model=model_to_use) as client:
            output = await client.complete(
                prompt=prompt,
                max_tokens=MAX_TRANSLATION_TOKENS,
                temperature=TRANSLATION_TEMPERATURE,
            )
    except OpenRouterError as e:
        logger.error("OpenRouter API error during translation: %s", e)
        raise TranslationError(f"LLM translation failed: {e}") from e
    except Exception as e:
        logger.error("Unexpected error during semantic translation: %s", e)
        raise TranslationError(f"Unexpected error during translation: {e}") from e

    # Clean up the output (remove potential markdown code blocks if present)
    output = _clean_output(output)

    logger.info(
        "Semantic translation completed: %d chars input -> %d chars output",
        len(content),
        len(output),
    )

    return SemanticTranslationResult(output=output, model_used=model_to_use)


def _clean_output(output: str) -> str:
    """Clean up LLM output by removing markdown code blocks if present.

    Args:
        output: The raw LLM output

    Returns:
        Cleaned output suitable for direct use
    """
    output = output.strip()

    # Check if wrapped in markdown code blocks
    if output.startswith("```"):
        lines = output.split("\n")
        # Find first and last code block markers
        start_idx = 0
        end_idx = len(lines)

        # Skip the opening ```markdown or ```json or similar
        if lines[0].startswith("```"):
            start_idx = 1

        # Skip the closing ```
        if lines and lines[-1].strip() == "```":
            end_idx = len(lines) - 1

        output = "\n".join(lines[start_idx:end_idx]).strip()

    # Ensure proper line ending
    if output and not output.endswith("\n"):
        output += "\n"

    return output
