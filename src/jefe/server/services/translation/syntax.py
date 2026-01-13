"""Syntax translation between harness configuration formats.

This module handles translating between different AI coding assistant
config formats (CLAUDE.md, AGENTS.md, GEMINI.md, opencode agent files, etc.)
"""

from __future__ import annotations

import json
import re
import tomllib
from typing import Literal

import tomli_w

from jefe.server.services.translation.mappings import (
    HARNESS_ALIASES,
    INSTRUCTION_SECTION_MAPPINGS,
    SETTINGS_KEY_MAPPINGS,
    SettingsFormat,
)

# Supported harnesses
HarnessName = Literal["claude-code", "codex_cli", "opencode", "gemini_cli"]


class TranslationError(Exception):
    """Error during translation between formats."""

    pass


def translate_syntax(
    content: str,
    source_harness: HarnessName,
    target_harness: HarnessName,
    config_kind: Literal["settings", "instructions"] = "instructions",
) -> str:
    """Translate configuration content between harness formats.

    Args:
        content: The raw content to translate
        source_harness: The harness the content is from
        target_harness: The harness to translate to
        config_kind: Whether this is a settings or instructions config

    Returns:
        The translated content

    Raises:
        TranslationError: If translation fails
    """
    # Normalize harness names
    source_harness = _normalize_harness_name(source_harness)
    target_harness = _normalize_harness_name(target_harness)

    if source_harness == target_harness:
        return content

    if config_kind == "settings":
        return _translate_settings(content, source_harness, target_harness)

    return _translate_instructions(content, source_harness, target_harness)


def _normalize_harness_name(name: str) -> HarnessName:
    """Normalize harness name to canonical form."""
    lower_name = name.lower().replace("-", "_").replace(" ", "_")
    if lower_name in HARNESS_ALIASES:
        return HARNESS_ALIASES[lower_name]  # type: ignore[return-value]
    return name  # type: ignore[return-value]


def _translate_instructions(
    content: str,
    source_harness: HarnessName,
    target_harness: HarnessName,
) -> str:
    """Translate markdown instruction files between formats.

    Main instruction file translations:
    - CLAUDE.md <-> AGENTS.md <-> GEMINI.md
    """
    # Parse sections from the source markdown
    sections = _parse_markdown_sections(content)

    # Map section headings to target format
    translated_sections = _map_section_headings(sections, source_harness, target_harness)

    # Add harness-specific header if needed
    translated_sections = _add_harness_header(
        translated_sections, source_harness, target_harness
    )

    # Reconstruct markdown
    return _build_markdown(translated_sections)


def _parse_markdown_sections(content: str) -> list[tuple[str, int, str]]:
    """Parse markdown into sections.

    Returns list of (heading, level, content) tuples.
    Level 0 means content before any heading.
    """
    sections: list[tuple[str, int, str]] = []
    lines = content.split("\n")

    current_heading = ""
    current_level = 0
    current_content: list[str] = []

    heading_pattern = re.compile(r"^(#{1,6})\s+(.+)$")

    for line in lines:
        match = heading_pattern.match(line)
        if match:
            # Save previous section
            if current_heading or current_content:
                sections.append(
                    (current_heading, current_level, "\n".join(current_content).strip())
                )

            # Start new section
            current_level = len(match.group(1))
            current_heading = match.group(2).strip()
            current_content = []
        else:
            current_content.append(line)

    # Don't forget the last section
    if current_heading or current_content:
        sections.append(
            (current_heading, current_level, "\n".join(current_content).strip())
        )

    return sections


def _map_section_headings(
    sections: list[tuple[str, int, str]],
    source_harness: HarnessName,
    target_harness: HarnessName,
) -> list[tuple[str, int, str]]:
    """Map section headings from source to target format."""
    result: list[tuple[str, int, str]] = []

    # Get mapping for source -> target
    mappings = INSTRUCTION_SECTION_MAPPINGS.get(source_harness, {})
    target_mappings = mappings.get(target_harness, {})

    for heading, level, content in sections:
        # Try to find a mapping for this heading
        heading_lower = heading.lower()
        new_heading = heading  # Default to original

        for src_pattern, tgt_heading in target_mappings.items():
            if _heading_matches(heading_lower, src_pattern):
                new_heading = tgt_heading
                break

        result.append((new_heading, level, content))

    return result


def _heading_matches(heading: str, pattern: str) -> bool:
    """Check if a heading matches a pattern (case-insensitive, allows partial match)."""
    pattern_lower = pattern.lower()
    heading_lower = heading.lower()

    # Exact match
    if heading_lower == pattern_lower:
        return True

    # Pattern at start of heading
    if heading_lower.startswith(pattern_lower):
        return True

    # Pattern in heading (for compound headings)
    return pattern_lower in heading_lower


def _add_harness_header(
    sections: list[tuple[str, int, str]],
    source_harness: HarnessName,
    target_harness: HarnessName,
) -> list[tuple[str, int, str]]:
    """Add a comment/note about the translation at the top if appropriate."""
    if not sections:
        return sections

    # Check if first section is preamble (level 0 content before any heading)
    first_heading, first_level, first_content = sections[0]

    if first_level == 0 and not first_heading:
        # There's a preamble, add note after it
        note = _get_translation_note(source_harness, target_harness)
        if note:
            new_content = f"{first_content}\n\n{note}".strip()
            return [(first_heading, first_level, new_content), *sections[1:]]
    else:
        # No preamble, add note as preamble
        note = _get_translation_note(source_harness, target_harness)
        if note:
            return [("", 0, note), *sections]

    return sections


def _get_translation_note(source_harness: HarnessName, target_harness: HarnessName) -> str:
    """Get a note about the translation for the target file."""
    harness_display = {
        "claude-code": "Claude Code",
        "codex_cli": "Codex CLI",
        "opencode": "OpenCode",
        "gemini_cli": "Gemini CLI",
    }

    source_name = harness_display.get(source_harness, source_harness)
    target_name = harness_display.get(target_harness, target_harness)

    return f"<!-- Translated from {source_name} format to {target_name} format -->"


def _build_markdown(sections: list[tuple[str, int, str]]) -> str:
    """Reconstruct markdown from sections."""
    parts: list[str] = []

    for heading, level, content in sections:
        if level > 0 and heading:
            parts.append(f"{'#' * level} {heading}")
        if content:
            parts.append(content)
        parts.append("")  # Blank line between sections

    # Clean up trailing whitespace
    result = "\n".join(parts).strip()
    return result + "\n"


def _translate_settings(
    content: str,
    source_harness: HarnessName,
    target_harness: HarnessName,
) -> str:
    """Translate settings between different formats.

    Format mappings:
    - claude-code: settings.json (JSON)
    - codex_cli: config.toml (TOML)
    - opencode: opencode.json (JSON/JSONC)
    - gemini_cli: settings.json (JSON)
    """
    source_format = _get_settings_format(source_harness)
    target_format = _get_settings_format(target_harness)

    # Parse source content to dict
    source_data = _parse_settings(content, source_format)

    # Map keys between harnesses
    target_data = _map_settings_keys(source_data, source_harness, target_harness)

    # Serialize to target format
    return _serialize_settings(target_data, target_format)


def _get_settings_format(harness: HarnessName) -> SettingsFormat:
    """Get the settings file format for a harness."""
    format_map: dict[HarnessName, SettingsFormat] = {
        "claude-code": "json",
        "codex_cli": "toml",
        "opencode": "json",
        "gemini_cli": "json",
    }
    return format_map.get(harness, "json")


def _parse_settings(content: str, format: SettingsFormat) -> dict[str, object]:
    """Parse settings content to a dictionary."""
    if format == "toml":
        try:
            parsed: dict[str, object] = tomllib.loads(content)
            return parsed
        except Exception as e:
            raise TranslationError(f"Failed to parse TOML: {e}") from e

    # JSON (with simple JSONC support for OpenCode)
    try:
        # Strip line comments for JSONC support
        cleaned = _strip_json_comments(content)
        parsed_json: dict[str, object] = json.loads(cleaned)
        return parsed_json
    except json.JSONDecodeError as e:
        raise TranslationError(f"Failed to parse JSON: {e}") from e


def _strip_json_comments(content: str) -> str:
    """Strip // comments from JSON content (simple JSONC support)."""
    lines = content.split("\n")
    cleaned_lines = []

    for line in lines:
        if "//" in line:
            # Find // outside of strings
            comment_idx = line.find("//")
            quotes_before = line[:comment_idx].count('"')
            if quotes_before % 2 == 0:
                line = line[:comment_idx]
        cleaned_lines.append(line)

    return "\n".join(cleaned_lines)


def _map_settings_keys(
    data: dict[str, object],
    source_harness: HarnessName,
    target_harness: HarnessName,
) -> dict[str, object]:
    """Map settings keys from source to target harness format."""
    result: dict[str, object] = {}

    # Get key mappings
    mappings = SETTINGS_KEY_MAPPINGS.get(source_harness, {})
    target_mappings = mappings.get(target_harness, {})

    for key, value in data.items():
        # Check if there's a mapping for this key
        if key in target_mappings:
            mapped_key = target_mappings[key]
            if mapped_key is not None:  # None means skip this key
                result[mapped_key] = value
        else:
            # Preserve unmapped keys as-is
            result[key] = value

    return result


def _serialize_settings(data: dict[str, object], format: SettingsFormat) -> str:
    """Serialize settings dictionary to the target format."""
    if format == "toml":
        try:
            toml_str: str = tomli_w.dumps(data)
            return toml_str
        except Exception as e:
            raise TranslationError(f"Failed to serialize TOML: {e}") from e

    # JSON
    try:
        return json.dumps(data, indent=2, sort_keys=True) + "\n"
    except Exception as e:
        raise TranslationError(f"Failed to serialize JSON: {e}") from e
