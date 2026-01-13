"""Schemas for recipe files."""

from pydantic import BaseModel, Field, field_validator


class SkillSpec(BaseModel):
    """Skill specification in a recipe."""

    source: str = Field(..., description="Source name")
    name: str = Field(..., description="Skill name")
    version: str | None = Field(None, description="Version constraint (semver)")
    pinned: bool = Field(False, description="Pin to exact version")

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: str | None) -> str | None:
        """Validate version constraint format."""
        if v is None or v == "*":
            return v

        # Basic validation for common semver patterns
        # Supports: 1.2.3, ^1.2.3, ~1.2.3, >=1.2.0, >= 1.2.0, etc.
        import re

        # Allow optional whitespace after operators
        pattern = r"^(\^|~|>=|<=|>|<|=)?\s*(\d+)\.(\d+)\.(\d+)(-[\w.]+)?(\+[\w.]+)?$"
        if not re.match(pattern, v):
            raise ValueError(
                f"Invalid version constraint: {v}. "
                "Expected semver format (e.g., 1.2.3, ^1.2.3, ~1.2.3, >=1.2.0)"
            )
        return v


class Recipe(BaseModel):
    """Recipe file schema."""

    name: str = Field(..., description="Unique recipe identifier")
    description: str | None = Field(None, description="Human-readable description")
    harnesses: list[str] = Field(
        default_factory=list,
        description="Target harness names (empty means all harnesses)",
    )
    skills: list[SkillSpec] = Field(
        default_factory=list, description="Individual skills to install"
    )
    bundles: list[str] = Field(
        default_factory=list, description="Bundle names to apply"
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate recipe name format."""
        import re

        # Require kebab-case or lowercase with underscores
        pattern = r"^[a-z0-9]+(-[a-z0-9]+)*$"
        if not re.match(pattern, v):
            raise ValueError(
                f"Invalid recipe name: {v}. "
                "Expected kebab-case format (e.g., web-ui-tools, python-dev)"
            )
        return v


    def has_content(self) -> bool:
        """Check if recipe has any skills or bundles."""
        return bool(self.skills or self.bundles)


class RecipeLoadRequest(BaseModel):
    """Request to load a recipe from YAML content."""

    content: str = Field(..., description="YAML content of the recipe file")
    validate_references: bool = Field(
        True, description="Validate that referenced harnesses/bundles exist"
    )


class RecipeApplyRequest(BaseModel):
    """Request to apply a recipe to a harness."""

    recipe_name: str = Field(..., description="Name of the recipe to apply")
    harness_id: int | None = Field(
        None, description="Specific harness ID (if None, applies to all recipe harnesses)"
    )
    project_id: int | None = Field(
        None, description="Project ID for project-scoped installations"
    )
    scope: str = Field("global", description="Installation scope (global or project)")


class RecipeApplyResponse(BaseModel):
    """Response from applying a recipe."""

    recipe_name: str = Field(..., description="Recipe that was applied")
    harnesses_applied: list[str] = Field(
        ..., description="List of harness names where recipe was applied"
    )
    skills_installed: int = Field(..., description="Number of skills installed")
    bundles_applied: int = Field(..., description="Number of bundles applied")
    errors: list[str] = Field(
        default_factory=list, description="List of errors encountered"
    )
    warnings: list[str] = Field(
        default_factory=list, description="List of warnings (e.g., skipped items)"
    )


class RecipeResponse(BaseModel):
    """Recipe response payload."""

    name: str = Field(..., description="Recipe name")
    description: str | None = Field(None, description="Description")
    harnesses: list[str] = Field(default_factory=list, description="Target harnesses")
    skills: list[SkillSpec] = Field(default_factory=list, description="Skill specifications")
    bundles: list[str] = Field(default_factory=list, description="Bundle names")
    skill_count: int = Field(..., description="Number of skills in recipe")
    bundle_count: int = Field(..., description="Number of bundles in recipe")


class RecipeValidationError(BaseModel):
    """Validation error for a recipe."""

    field: str = Field(..., description="Field that failed validation")
    message: str = Field(..., description="Error message")
    value: str | None = Field(None, description="Invalid value")
