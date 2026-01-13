"""Tests for skill parser utility."""

from pathlib import Path

import pytest

from jefe.server.utils.skill_parser import (
    SkillParseError,
    find_skill_files,
    parse_skill_file,
)


class TestSkillParser:
    """Tests for parsing SKILL.md files."""

    def test_parse_valid_skill_with_all_fields(self) -> None:
        """Test parsing a valid skill file with all fields."""
        skill_file = Path("tests/fixtures/sample_skills_repo/SKILL.md")
        result = parse_skill_file(skill_file)

        assert result["name"] == "example-skill"
        assert result["display_name"] == "Example Skill"
        assert result["description"] == "A sample skill for testing"
        assert result["version"] == "1.0.0"
        assert result["author"] == "Test Author"
        assert result["tags"] == ["testing", "example"]
        assert "metadata" in result
        assert result["metadata"]["category"] == "utility"
        assert result["metadata"]["license"] == "MIT"

    def test_parse_skill_with_minimal_fields(self) -> None:
        """Test parsing a skill file with only required fields."""
        skill_file = Path("tests/fixtures/sample_skills_repo/subdirectory/SKILL.md")
        result = parse_skill_file(skill_file)

        assert result["name"] == "nested-skill"
        assert result["display_name"] is None
        assert result["description"] == "A skill in a subdirectory"
        assert result["version"] == "2.1.0"
        assert result["author"] == "Another Author"
        assert result["tags"] == ["nested", "example"]
        assert "metadata" not in result

    def test_parse_skill_missing_required_field(self) -> None:
        """Test parsing a skill file missing the required 'name' field."""
        skill_file = Path("tests/fixtures/invalid_skill.md")

        with pytest.raises(ValueError, match="Required field 'name' missing"):
            parse_skill_file(skill_file)

    def test_parse_skill_no_frontmatter(self) -> None:
        """Test parsing a file without YAML frontmatter."""
        skill_file = Path("tests/fixtures/no_frontmatter.md")

        with pytest.raises(SkillParseError, match="No YAML frontmatter found"):
            parse_skill_file(skill_file)

    def test_parse_skill_malformed_yaml(self) -> None:
        """Test parsing a file with malformed YAML."""
        skill_file = Path("tests/fixtures/malformed_yaml.md")

        with pytest.raises(SkillParseError, match="Invalid YAML"):
            parse_skill_file(skill_file)

    def test_parse_skill_file_not_found(self) -> None:
        """Test parsing a non-existent file."""
        skill_file = Path("tests/fixtures/nonexistent.md")

        with pytest.raises(SkillParseError, match="Failed to read"):
            parse_skill_file(skill_file)


class TestFindSkillFiles:
    """Tests for finding SKILL.md files in a repository."""

    def test_find_skill_files_in_directory(self) -> None:
        """Test finding all SKILL.md files in a directory tree."""
        repo_path = Path("tests/fixtures/sample_skills_repo")
        skill_files = find_skill_files(repo_path)

        assert len(skill_files) == 2
        skill_names = [f.parent.name if f.parent != repo_path else "root" for f in skill_files]
        assert "root" in skill_names
        assert "subdirectory" in skill_names

    def test_find_skill_files_empty_directory(self, tmp_path: Path) -> None:
        """Test finding SKILL.md files in an empty directory."""
        skill_files = find_skill_files(tmp_path)
        assert len(skill_files) == 0

    def test_find_skill_files_nonexistent_directory(self) -> None:
        """Test finding SKILL.md files in a non-existent directory."""
        repo_path = Path("tests/fixtures/nonexistent_repo")
        skill_files = find_skill_files(repo_path)
        assert len(skill_files) == 0
