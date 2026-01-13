"""Service for parsing and resolving recipe files."""

import logging
from pathlib import Path
from typing import TypedDict

import yaml
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from jefe.data.models.installed_skill import InstallScope
from jefe.data.models.skill import Skill
from jefe.data.repositories.bundle import BundleRepository
from jefe.data.repositories.harness import HarnessRepository
from jefe.data.repositories.skill import SkillRepository
from jefe.data.repositories.skill_source import SkillSourceRepository
from jefe.server.schemas.recipe import Recipe, SkillSpec
from jefe.server.services.bundle import BundleService
from jefe.server.services.skill import SkillService

logger = logging.getLogger(__name__)


class ResolvedSkill(TypedDict):
    """A resolved skill ready for installation."""

    skill_id: int
    skill_name: str
    source_name: str
    version: str | None
    pinned: bool


class RecipeParseError(Exception):
    """Raised when recipe parsing fails."""

    pass


class RecipeValidationError(Exception):
    """Raised when recipe validation fails."""

    pass


class RecipeResolutionError(Exception):
    """Raised when recipe resolution fails."""

    pass


class RecipeService:
    """Service for parsing and resolving recipe files."""

    def __init__(self, session: AsyncSession, data_dir: Path | None = None) -> None:
        """
        Initialize the recipe service.

        Args:
            session: Database session
            data_dir: Directory for storing skill files
        """
        self.session = session
        self.skill_repo = SkillRepository(session)
        self.bundle_repo = BundleRepository(session)
        self.harness_repo = HarnessRepository(session)
        self.source_repo = SkillSourceRepository(session)
        self.skill_service = SkillService(session, data_dir)
        self.bundle_service = BundleService(session, data_dir)

    def parse_recipe(self, path: Path) -> Recipe:
        """
        Parse a recipe file from disk.

        Args:
            path: Path to the recipe YAML file

        Returns:
            Parsed Recipe object

        Raises:
            RecipeParseError: If file cannot be read or parsed
            RecipeValidationError: If recipe validation fails
        """
        try:
            with open(path) as f:
                content = f.read()
            return self.parse_recipe_content(content)
        except FileNotFoundError as e:
            raise RecipeParseError(f"Recipe file not found: {path}") from e
        except OSError as e:
            raise RecipeParseError(f"Failed to read recipe file: {e}") from e

    def parse_recipe_content(self, content: str) -> Recipe:
        """
        Parse recipe content from a YAML string.

        Args:
            content: YAML content string

        Returns:
            Parsed Recipe object

        Raises:
            RecipeParseError: If YAML parsing fails
            RecipeValidationError: If recipe validation fails
        """
        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError as e:
            raise RecipeParseError(f"Invalid YAML: {e}") from e

        if not isinstance(data, dict):
            raise RecipeParseError("Recipe must be a YAML object (dictionary)")

        try:
            recipe = Recipe.model_validate(data)
        except ValidationError as e:
            errors = []
            for error in e.errors():
                field = ".".join(str(x) for x in error["loc"])
                message = error["msg"]
                errors.append(f"{field}: {message}")
            raise RecipeValidationError(
                "Recipe validation failed:\n" + "\n".join(f"  - {err}" for err in errors)
            ) from e

        # Check that recipe has content
        if not recipe.has_content():
            raise RecipeValidationError(
                "Recipe must contain at least one skill or bundle"
            )

        return recipe

    async def resolve_recipe(self, recipe: Recipe) -> dict[str, list[ResolvedSkill]]:
        """
        Resolve all skills and bundles in a recipe.

        This expands bundles into their constituent skills and resolves all skill
        references to actual skill IDs in the database.

        Args:
            recipe: Parsed Recipe object

        Returns:
            Dictionary mapping harness names to lists of resolved skills.
            If recipe has no harness restrictions, returns {"*": [skills]}.

        Raises:
            RecipeResolutionError: If skills or bundles cannot be resolved
        """
        resolved_skills, errors = await self._resolve_all_skills(recipe)

        if errors:
            raise RecipeResolutionError(
                "Failed to resolve recipe:\n" + "\n".join(f"  - {err}" for err in errors)
            )

        if not resolved_skills:
            raise RecipeResolutionError(
                "No skills resolved from recipe (all skills/bundles were invalid)"
            )

        # Map to harnesses
        return self._map_skills_to_harnesses(recipe, resolved_skills)

    async def _resolve_all_skills(
        self, recipe: Recipe
    ) -> tuple[dict[str, ResolvedSkill], list[str]]:
        """Resolve all skills and bundles in a recipe."""
        resolved_skills: dict[str, ResolvedSkill] = {}
        errors: list[str] = []

        # Resolve direct skill references
        for skill_spec in recipe.skills:
            try:
                resolved = await self._resolve_skill_spec(skill_spec)
                # Use (source, name) as key to avoid duplicates
                key = f"{skill_spec.source}:{skill_spec.name}"
                if key not in resolved_skills:
                    resolved_skills[key] = resolved
            except RecipeResolutionError as e:
                errors.append(str(e))

        # Resolve bundles and expand into skills
        for bundle_name in recipe.bundles:
            try:
                bundle_skills = await self._resolve_bundle(bundle_name)
                for skill in bundle_skills:
                    key = f"{skill['source_name']}:{skill['skill_name']}"
                    # Don't override if already specified directly (direct specs take precedence)
                    if key not in resolved_skills:
                        resolved_skills[key] = skill
            except RecipeResolutionError as e:
                errors.append(str(e))

        return resolved_skills, errors

    def _map_skills_to_harnesses(
        self, recipe: Recipe, resolved_skills: dict[str, ResolvedSkill]
    ) -> dict[str, list[ResolvedSkill]]:
        """Map resolved skills to target harnesses."""
        result: dict[str, list[ResolvedSkill]] = {}
        skill_list = list(resolved_skills.values())

        if not recipe.harnesses:
            # No harness restrictions - applies to all
            result["*"] = skill_list
        else:
            # Apply to specific harnesses
            for harness_name in recipe.harnesses:
                result[harness_name] = skill_list

        return result

    async def _resolve_skill_spec(self, spec: SkillSpec) -> ResolvedSkill:
        """
        Resolve a single skill specification to a skill ID.

        Args:
            spec: SkillSpec to resolve

        Returns:
            ResolvedSkill with skill ID and metadata

        Raises:
            RecipeResolutionError: If skill cannot be found
        """
        # Find the source
        source = await self.source_repo.get_by_name(spec.source)
        if source is None:
            raise RecipeResolutionError(
                f"Source '{spec.source}' not found for skill '{spec.name}'"
            )

        # Find the skill by name
        skills = await self.skill_repo.list_by_name(spec.name)
        matching_skill: Skill | None = None

        for skill in skills:
            if skill.source_id == source.id:
                matching_skill = skill
                break

        if matching_skill is None:
            raise RecipeResolutionError(
                f"Skill '{spec.name}' not found in source '{spec.source}'"
            )

        # Handle version constraints
        version = spec.version
        if version == "*" or version is None:
            # Use latest (current) version
            version = matching_skill.version

        # For now, we don't do version range resolution - we just use the skill's current version
        # TODO: In the future, implement proper semver range matching
        # For exact versions, we would need to check if they match
        if (
            version
            and spec.version
            and matching_skill.version
            and not self._matches_version_constraint(matching_skill.version, spec.version)
        ):
            logger.warning(
                f"Skill '{spec.name}' from '{spec.source}' version {matching_skill.version} "
                f"may not satisfy constraint {spec.version}"
            )

        return ResolvedSkill(
            skill_id=matching_skill.id,
            skill_name=spec.name,
            source_name=spec.source,
            version=matching_skill.version,
            pinned=spec.pinned,
        )

    async def _resolve_bundle(self, bundle_name: str) -> list[ResolvedSkill]:
        """
        Resolve a bundle to its constituent skills.

        Args:
            bundle_name: Name of the bundle

        Returns:
            List of resolved skills from the bundle

        Raises:
            RecipeResolutionError: If bundle cannot be found or resolved
        """
        bundle = await self.bundle_repo.get_by_name(bundle_name)
        if bundle is None:
            raise RecipeResolutionError(f"Bundle '{bundle_name}' not found")

        skill_refs = bundle.get_skill_refs_list()
        if not skill_refs:
            logger.warning(f"Bundle '{bundle_name}' is empty")
            return []

        resolved_skills: list[ResolvedSkill] = []
        errors: list[str] = []

        for ref in skill_refs:
            source_name = ref.get("source")
            skill_name = ref.get("name")

            if not source_name or not skill_name:
                errors.append(f"Invalid skill reference in bundle '{bundle_name}': {ref}")
                continue

            try:
                # Create a SkillSpec for resolution
                spec = SkillSpec(source=source_name, name=skill_name, version=None, pinned=False)
                resolved = await self._resolve_skill_spec(spec)
                resolved_skills.append(resolved)
            except RecipeResolutionError as e:
                errors.append(f"In bundle '{bundle_name}': {e}")

        if errors:
            # Log errors but don't fail entirely - partial bundle resolution is okay
            for error in errors:
                logger.error(error)

        return resolved_skills

    def _matches_version_constraint(self, version: str, constraint: str | None) -> bool:
        """
        Check if a version matches a version constraint.

        This is a simplified version matcher. In production, you'd use a proper
        semver library like `semantic_version` or `packaging`.

        Args:
            version: The actual version string
            constraint: The version constraint (e.g., ^1.2.3, ~1.2.0, >=1.0.0, 1.2.3, *)

        Returns:
            True if version matches the constraint
        """
        if constraint is None or constraint == "*":
            return True

        # For exact version match (no operator)
        if constraint and constraint[0].isdigit():
            return version == constraint

        # For now, we'll just accept any version for complex constraints
        # TODO: Implement proper semver matching using a library
        return True

    async def apply_recipe(
        self,
        recipe: Recipe,
        harness_id: int | None = None,
        scope: InstallScope = InstallScope.GLOBAL,
        project_id: int | None = None,
    ) -> dict[str, dict[str, int | list[str]]]:
        """
        Apply a recipe by installing all its skills and bundles.

        Args:
            recipe: Recipe to apply
            harness_id: Specific harness ID (if None, applies to all recipe harnesses)
            scope: Installation scope (global or project)
            project_id: Project ID (required for project scope)

        Returns:
            Dictionary with results per harness:
            {
                "harness_name": {
                    "skills_installed": count,
                    "bundles_applied": count,
                    "errors": [error messages]
                }
            }

        Raises:
            RecipeResolutionError: If recipe cannot be resolved
        """
        # Resolve the recipe to get skills per harness
        resolved = await self.resolve_recipe(recipe)

        results: dict[str, dict[str, int | list[str]]] = {}

        # If specific harness requested, validate it
        if harness_id is not None:
            harness = await self.harness_repo.get_by_id(harness_id)
            if harness is None:
                raise RecipeResolutionError(f"Harness {harness_id} not found")

            # Check if recipe applies to this harness
            if recipe.harnesses and harness.name not in recipe.harnesses:
                raise RecipeResolutionError(
                    f"Recipe '{recipe.name}' does not apply to harness '{harness.name}'"
                )

            # Install to this harness only
            target_harnesses = [(harness_id, harness.name)]
        else:
            # Install to all harnesses specified in recipe
            target_harnesses = []
            for harness_name in resolved:
                if harness_name == "*":
                    # Recipe applies to all harnesses - would need to get all harnesses
                    # For now, raise an error requiring explicit harness
                    raise RecipeResolutionError(
                        "Recipe applies to all harnesses - please specify a harness_id"
                    )
                harness = await self.harness_repo.get_by_name(harness_name)
                if harness is None:
                    logger.warning(f"Harness '{harness_name}' not found, skipping")
                    continue
                target_harnesses.append((harness.id, harness.name))

        # Apply recipe to each target harness
        for hid, hname in target_harnesses:
            skills = resolved.get(hname, resolved.get("*", []))
            success_count = 0
            errors: list[str] = []

            for skill in skills:
                try:
                    await self.skill_service.install_skill(
                        skill_id=skill["skill_id"],
                        harness_id=hid,
                        scope=scope,
                        project_id=project_id,
                    )
                    success_count += 1
                except Exception as e:
                    error_msg = (
                        f"Failed to install {skill['skill_name']} "
                        f"from {skill['source_name']}: {e}"
                    )
                    logger.error(error_msg)
                    errors.append(error_msg)

            results[hname] = {
                "skills_installed": success_count,
                "bundles_applied": len(recipe.bundles),
                "errors": errors,
            }

        return results
