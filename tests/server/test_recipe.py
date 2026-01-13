"""Tests for recipe parser and resolver."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from jefe.data.models.bundle import Bundle
from jefe.data.models.harness import Harness
from jefe.data.models.skill import Skill
from jefe.data.models.skill_source import SkillSource, SourceType
from jefe.server.schemas.recipe import Recipe, SkillSpec
from jefe.server.services.recipe import (
    RecipeParseError,
    RecipeResolutionError,
    RecipeService,
    RecipeValidationError,
)


@pytest.fixture
def mock_session() -> AsyncSession:
    """Create a mock async session."""
    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    return session  # type: ignore


@pytest.fixture
def recipe_service(mock_session: AsyncSession, tmp_path: Path) -> RecipeService:
    """Create a RecipeService instance."""
    return RecipeService(mock_session, data_dir=tmp_path / "skills")


@pytest.fixture
def mock_skill_source() -> SkillSource:
    """Create a mock skill source."""
    source = MagicMock(spec=SkillSource)
    source.id = 1
    source.name = "test-source"
    source.source_type = SourceType.GIT
    source.url = "https://github.com/test/skills"
    return source


@pytest.fixture
def mock_skill(mock_skill_source: SkillSource) -> Skill:
    """Create a mock skill."""
    skill = MagicMock(spec=Skill)
    skill.id = 1
    skill.source_id = mock_skill_source.id
    skill.name = "test-skill"
    skill.display_name = "Test Skill"
    skill.version = "1.0.0"
    skill.source = mock_skill_source
    return skill


@pytest.fixture
def mock_bundle() -> Bundle:
    """Create a mock bundle."""
    bundle = MagicMock(spec=Bundle)
    bundle.id = 1
    bundle.name = "test-bundle"
    bundle.display_name = "Test Bundle"
    bundle.description = "A test bundle"
    bundle.get_skill_refs_list = MagicMock(
        return_value=[
            {"source": "test-source", "name": "test-skill"},
            {"source": "test-source", "name": "another-skill"},
        ]
    )
    return bundle


@pytest.fixture
def mock_harness() -> Harness:
    """Create a mock harness."""
    harness = MagicMock(spec=Harness)
    harness.id = 1
    harness.name = "claude-code"
    harness.display_name = "Claude Code"
    return harness


# ==================== Parse Recipe Tests ====================


def test_parse_recipe_from_file(recipe_service: RecipeService, tmp_path: Path) -> None:
    """Recipe files can be parsed from disk."""
    recipe_file = tmp_path / "test-recipe.yaml"
    recipe_file.write_text(
        """
name: test-recipe
description: A test recipe
skills:
  - source: test-source
    name: test-skill
    version: 1.0.0
"""
    )

    recipe = recipe_service.parse_recipe(recipe_file)
    assert recipe.name == "test-recipe"
    assert recipe.description == "A test recipe"
    assert len(recipe.skills) == 1
    assert recipe.skills[0].source == "test-source"
    assert recipe.skills[0].name == "test-skill"
    assert recipe.skills[0].version == "1.0.0"


def test_parse_recipe_file_not_found(recipe_service: RecipeService) -> None:
    """Parsing a non-existent file raises RecipeParseError."""
    with pytest.raises(RecipeParseError, match="Recipe file not found"):
        recipe_service.parse_recipe(Path("/non/existent/recipe.yaml"))


def test_parse_recipe_content_minimal(recipe_service: RecipeService) -> None:
    """Minimal valid recipe can be parsed."""
    content = """
name: minimal-recipe
skills:
  - source: test-source
    name: test-skill
"""
    recipe = recipe_service.parse_recipe_content(content)
    assert recipe.name == "minimal-recipe"
    assert recipe.description is None
    assert len(recipe.harnesses) == 0  # No harness restrictions
    assert len(recipe.skills) == 1
    assert len(recipe.bundles) == 0


def test_parse_recipe_content_with_bundles(recipe_service: RecipeService) -> None:
    """Recipe with bundles can be parsed."""
    content = """
name: bundle-recipe
bundles:
  - frontend-tools
  - testing-suite
"""
    recipe = recipe_service.parse_recipe_content(content)
    assert recipe.name == "bundle-recipe"
    assert len(recipe.bundles) == 2
    assert "frontend-tools" in recipe.bundles
    assert "testing-suite" in recipe.bundles


def test_parse_recipe_content_with_harnesses(recipe_service: RecipeService) -> None:
    """Recipe with harness restrictions can be parsed."""
    content = """
name: harness-specific
harnesses:
  - claude-code
  - cursor
skills:
  - source: test-source
    name: test-skill
"""
    recipe = recipe_service.parse_recipe_content(content)
    assert len(recipe.harnesses) == 2
    assert "claude-code" in recipe.harnesses
    assert "cursor" in recipe.harnesses


def test_parse_recipe_with_version_constraints(recipe_service: RecipeService) -> None:
    """Recipe with various version constraints can be parsed."""
    content = """
name: version-test
skills:
  - source: test-source
    name: exact-version
    version: 1.2.3
  - source: test-source
    name: caret-version
    version: ^1.2.3
  - source: test-source
    name: tilde-version
    version: ~1.2.3
  - source: test-source
    name: gte-version
    version: ">= 1.0.0"
  - source: test-source
    name: latest-version
    version: "*"
  - source: test-source
    name: no-version
"""
    recipe = recipe_service.parse_recipe_content(content)
    assert len(recipe.skills) == 6
    assert recipe.skills[0].version == "1.2.3"
    assert recipe.skills[1].version == "^1.2.3"
    assert recipe.skills[2].version == "~1.2.3"
    assert recipe.skills[3].version == ">= 1.0.0"
    assert recipe.skills[4].version == "*"
    assert recipe.skills[5].version is None


def test_parse_recipe_with_pinned_versions(recipe_service: RecipeService) -> None:
    """Recipe with pinned versions can be parsed."""
    content = """
name: pinned-test
skills:
  - source: test-source
    name: pinned-skill
    version: 1.0.0
    pinned: true
  - source: test-source
    name: unpinned-skill
    version: 1.0.0
    pinned: false
"""
    recipe = recipe_service.parse_recipe_content(content)
    assert recipe.skills[0].pinned is True
    assert recipe.skills[1].pinned is False


def test_parse_recipe_invalid_yaml(recipe_service: RecipeService) -> None:
    """Invalid YAML raises RecipeParseError."""
    content = """
name: invalid
skills:
  - source: test
    name
"""
    with pytest.raises(RecipeParseError, match="Invalid YAML"):
        recipe_service.parse_recipe_content(content)


def test_parse_recipe_not_dict(recipe_service: RecipeService) -> None:
    """Non-dictionary YAML raises RecipeParseError."""
    content = "- just a list"
    with pytest.raises(RecipeParseError, match="must be a YAML object"):
        recipe_service.parse_recipe_content(content)


def test_parse_recipe_missing_name(recipe_service: RecipeService) -> None:
    """Recipe without name raises RecipeValidationError."""
    content = """
description: Missing name
skills:
  - source: test-source
    name: test-skill
"""
    with pytest.raises(RecipeValidationError, match="validation failed"):
        recipe_service.parse_recipe_content(content)


def test_parse_recipe_invalid_name_format(recipe_service: RecipeService) -> None:
    """Recipe with invalid name format raises RecipeValidationError."""
    content = """
name: Invalid_Name_With_Underscores
skills:
  - source: test-source
    name: test-skill
"""
    with pytest.raises(RecipeValidationError, match="kebab-case"):
        recipe_service.parse_recipe_content(content)


def test_parse_recipe_no_content(recipe_service: RecipeService) -> None:
    """Recipe with no skills or bundles raises RecipeValidationError."""
    content = """
name: empty-recipe
description: This recipe has no content
"""
    with pytest.raises(RecipeValidationError, match="at least one skill or bundle"):
        recipe_service.parse_recipe_content(content)


def test_parse_recipe_invalid_version_format(recipe_service: RecipeService) -> None:
    """Recipe with invalid version format raises RecipeValidationError."""
    content = """
name: invalid-version
skills:
  - source: test-source
    name: test-skill
    version: not-a-version
"""
    with pytest.raises(RecipeValidationError, match="Invalid version constraint"):
        recipe_service.parse_recipe_content(content)


# ==================== Resolve Recipe Tests ====================


@pytest.mark.asyncio
async def test_resolve_recipe_with_skills(
    recipe_service: RecipeService,
    mock_skill_source: SkillSource,
    mock_skill: Skill,
) -> None:
    """Recipe with direct skills can be resolved."""
    # Mock repository responses
    recipe_service.source_repo.get_by_name = AsyncMock(return_value=mock_skill_source)
    recipe_service.skill_repo.list_by_name = AsyncMock(return_value=[mock_skill])

    recipe = Recipe(
        name="test-recipe",
        skills=[SkillSpec(source="test-source", name="test-skill", version="1.0.0")],
    )

    resolved = await recipe_service.resolve_recipe(recipe)

    # Should apply to all harnesses (no restrictions)
    assert "*" in resolved
    assert len(resolved["*"]) == 1
    assert resolved["*"][0]["skill_id"] == mock_skill.id
    assert resolved["*"][0]["skill_name"] == "test-skill"
    assert resolved["*"][0]["source_name"] == "test-source"
    assert resolved["*"][0]["version"] == "1.0.0"


@pytest.mark.asyncio
async def test_resolve_recipe_with_harness_restriction(
    recipe_service: RecipeService,
    mock_skill_source: SkillSource,
    mock_skill: Skill,
) -> None:
    """Recipe with harness restrictions resolves correctly."""
    recipe_service.source_repo.get_by_name = AsyncMock(return_value=mock_skill_source)
    recipe_service.skill_repo.list_by_name = AsyncMock(return_value=[mock_skill])

    recipe = Recipe(
        name="test-recipe",
        harnesses=["claude-code", "cursor"],
        skills=[SkillSpec(source="test-source", name="test-skill")],
    )

    resolved = await recipe_service.resolve_recipe(recipe)

    assert "claude-code" in resolved
    assert "cursor" in resolved
    assert "*" not in resolved
    assert len(resolved["claude-code"]) == 1
    assert len(resolved["cursor"]) == 1


@pytest.mark.asyncio
async def test_resolve_recipe_source_not_found(
    recipe_service: RecipeService,
) -> None:
    """Resolving with non-existent source raises RecipeResolutionError."""
    recipe_service.source_repo.get_by_name = AsyncMock(return_value=None)

    recipe = Recipe(
        name="test-recipe",
        skills=[SkillSpec(source="non-existent", name="test-skill")],
    )

    with pytest.raises(RecipeResolutionError, match="Source 'non-existent' not found"):
        await recipe_service.resolve_recipe(recipe)


@pytest.mark.asyncio
async def test_resolve_recipe_skill_not_found(
    recipe_service: RecipeService,
    mock_skill_source: SkillSource,
) -> None:
    """Resolving with non-existent skill raises RecipeResolutionError."""
    recipe_service.source_repo.get_by_name = AsyncMock(return_value=mock_skill_source)
    recipe_service.skill_repo.list_by_name = AsyncMock(return_value=[])

    recipe = Recipe(
        name="test-recipe",
        skills=[SkillSpec(source="test-source", name="non-existent-skill")],
    )

    with pytest.raises(RecipeResolutionError, match="Skill 'non-existent-skill' not found"):
        await recipe_service.resolve_recipe(recipe)


@pytest.mark.asyncio
async def test_resolve_recipe_with_bundles(
    recipe_service: RecipeService,
    mock_skill_source: SkillSource,
    mock_skill: Skill,
    mock_bundle: Bundle,
) -> None:
    """Recipe with bundles expands to constituent skills."""
    recipe_service.bundle_repo.get_by_name = AsyncMock(return_value=mock_bundle)
    recipe_service.source_repo.get_by_name = AsyncMock(return_value=mock_skill_source)
    recipe_service.skill_repo.list_by_name = AsyncMock(return_value=[mock_skill])

    recipe = Recipe(
        name="test-recipe",
        bundles=["test-bundle"],
    )

    resolved = await recipe_service.resolve_recipe(recipe)

    assert "*" in resolved
    # Bundle has 2 skill refs, but we're mocking skill resolution to return same skill
    # In reality, different skills would be returned
    assert len(resolved["*"]) >= 1


@pytest.mark.asyncio
async def test_resolve_recipe_bundle_not_found(
    recipe_service: RecipeService,
) -> None:
    """Resolving with non-existent bundle raises RecipeResolutionError."""
    recipe_service.bundle_repo.get_by_name = AsyncMock(return_value=None)

    recipe = Recipe(
        name="test-recipe",
        bundles=["non-existent-bundle"],
    )

    with pytest.raises(RecipeResolutionError, match="Bundle 'non-existent-bundle' not found"):
        await recipe_service.resolve_recipe(recipe)


@pytest.mark.asyncio
async def test_resolve_recipe_skills_and_bundles(
    recipe_service: RecipeService,
    mock_skill_source: SkillSource,
    mock_skill: Skill,
    mock_bundle: Bundle,
) -> None:
    """Recipe with both skills and bundles resolves correctly."""
    recipe_service.source_repo.get_by_name = AsyncMock(return_value=mock_skill_source)
    recipe_service.skill_repo.list_by_name = AsyncMock(return_value=[mock_skill])
    recipe_service.bundle_repo.get_by_name = AsyncMock(return_value=mock_bundle)

    recipe = Recipe(
        name="test-recipe",
        skills=[SkillSpec(source="test-source", name="test-skill")],
        bundles=["test-bundle"],
    )

    resolved = await recipe_service.resolve_recipe(recipe)

    assert "*" in resolved
    # Should have at least the direct skill
    assert len(resolved["*"]) >= 1


@pytest.mark.asyncio
async def test_resolve_recipe_deduplicates_skills(
    recipe_service: RecipeService,
    mock_skill_source: SkillSource,
    mock_skill: Skill,
    mock_bundle: Bundle,
) -> None:
    """Duplicate skills from direct specs and bundles are deduplicated."""
    # Set bundle to contain the same skill as direct spec
    mock_bundle.get_skill_refs_list = MagicMock(
        return_value=[{"source": "test-source", "name": "test-skill"}]
    )

    recipe_service.source_repo.get_by_name = AsyncMock(return_value=mock_skill_source)
    recipe_service.skill_repo.list_by_name = AsyncMock(return_value=[mock_skill])
    recipe_service.bundle_repo.get_by_name = AsyncMock(return_value=mock_bundle)

    recipe = Recipe(
        name="test-recipe",
        skills=[SkillSpec(source="test-source", name="test-skill", version="1.0.0")],
        bundles=["test-bundle"],
    )

    resolved = await recipe_service.resolve_recipe(recipe)

    # Should have only one instance of the skill (direct spec takes precedence)
    assert "*" in resolved
    assert len(resolved["*"]) == 1


@pytest.mark.asyncio
async def test_resolve_recipe_version_constraint_latest(
    recipe_service: RecipeService,
    mock_skill_source: SkillSource,
    mock_skill: Skill,
) -> None:
    """Recipe with * or no version uses latest skill version."""
    recipe_service.source_repo.get_by_name = AsyncMock(return_value=mock_skill_source)
    recipe_service.skill_repo.list_by_name = AsyncMock(return_value=[mock_skill])

    recipe = Recipe(
        name="test-recipe",
        skills=[SkillSpec(source="test-source", name="test-skill", version="*")],
    )

    resolved = await recipe_service.resolve_recipe(recipe)

    assert resolved["*"][0]["version"] == mock_skill.version


# ==================== Version Constraint Tests ====================


def test_version_matches_exact(recipe_service: RecipeService) -> None:
    """Exact version constraints match correctly."""
    assert recipe_service._matches_version_constraint("1.2.3", "1.2.3") is True
    assert recipe_service._matches_version_constraint("1.2.4", "1.2.3") is False


def test_version_matches_wildcard(recipe_service: RecipeService) -> None:
    """Wildcard version constraint matches any version."""
    assert recipe_service._matches_version_constraint("1.2.3", "*") is True
    assert recipe_service._matches_version_constraint("99.99.99", "*") is True
    assert recipe_service._matches_version_constraint("0.0.1", None) is True


# ==================== Integration Tests ====================


def test_parse_real_recipe_example(recipe_service: RecipeService, tmp_path: Path) -> None:
    """Real-world recipe example can be parsed."""
    recipe_file = tmp_path / "web-ui.yaml"
    recipe_file.write_text(
        """
name: web-ui
description: Complete web development environment

harnesses:
  - claude-code
  - cursor
  - vscode

skills:
  - source: javascript
    name: react-snippets
    version: ^2.0.0
    pinned: false

  - source: javascript
    name: typescript-helpers
    version: 1.5.2
    pinned: true

  - source: testing
    name: jest-runner
    version: ~3.1.0

  - source: javascript
    name: eslint-formatter
    version: ">=2.0.0"

  - source: frontend
    name: tailwind-utilities
    version: ^1.8.0

  - source: frontend
    name: axios-helpers
    version: "*"

bundles:
  - frontend-essentials
  - testing-suite
  - react-toolkit
"""
    )

    recipe = recipe_service.parse_recipe(recipe_file)
    assert recipe.name == "web-ui"
    assert len(recipe.harnesses) == 3
    assert len(recipe.skills) == 6
    assert len(recipe.bundles) == 3
    assert recipe.skills[1].pinned is True
    assert recipe.skills[0].pinned is False
