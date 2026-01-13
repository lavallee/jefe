"""Utility for parsing SKILL.md files with YAML frontmatter."""

import re
from pathlib import Path
from typing import Any

import yaml


class SkillParseError(Exception):
    """Raised when a SKILL.md file cannot be parsed."""

    pass


def parse_skill_file(file_path: Path) -> dict[str, Any]:
    """
    Parse a SKILL.md file and extract metadata from YAML frontmatter.

    Args:
        file_path: Path to the SKILL.md file

    Returns:
        Dictionary with skill metadata including:
        - name: Skill name (required)
        - display_name: Human-readable name (optional)
        - description: Skill description (optional)
        - version: Version string (optional)
        - author: Author name (optional)
        - tags: List of tags (optional)
        - metadata: Additional metadata fields (optional)

    Raises:
        SkillParseError: If file cannot be read or parsed
        ValueError: If required fields are missing
    """
    try:
        content = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        raise SkillParseError(f"Failed to read {file_path}: {e}") from e

    # Extract YAML frontmatter (between --- delimiters)
    frontmatter_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)

    if not frontmatter_match:
        raise SkillParseError(f"No YAML frontmatter found in {file_path}")

    frontmatter_text = frontmatter_match.group(1)

    try:
        metadata = yaml.safe_load(frontmatter_text)
    except yaml.YAMLError as e:
        raise SkillParseError(f"Invalid YAML in {file_path}: {e}") from e

    if not isinstance(metadata, dict):
        raise SkillParseError(f"YAML frontmatter must be a dictionary in {file_path}")

    # Validate required fields
    if "name" not in metadata:
        raise ValueError(f"Required field 'name' missing in {file_path}")

    # Extract standard fields
    result: dict[str, Any] = {
        "name": str(metadata["name"]),
        "display_name": str(metadata.get("display_name", "")) or None,
        "description": str(metadata.get("description", "")) or None,
        "version": str(metadata.get("version", "")) or None,
        "author": str(metadata.get("author", "")) or None,
        "tags": metadata.get("tags", []) if isinstance(metadata.get("tags"), list) else [],
    }

    # Store all additional fields in metadata
    standard_fields = {"name", "display_name", "description", "version", "author", "tags"}
    additional_metadata = {k: v for k, v in metadata.items() if k not in standard_fields}

    if additional_metadata:
        result["metadata"] = additional_metadata

    return result


def find_skill_files(repo_path: Path) -> list[Path]:
    """
    Find all SKILL.md files in a repository.

    Args:
        repo_path: Root path of the repository

    Returns:
        List of Path objects pointing to SKILL.md files
    """
    if not repo_path.is_dir():
        return []

    return list(repo_path.rglob("SKILL.md"))
