# Recipe File Format

## Overview

Recipe files are YAML configuration files that define collections of skills and bundles to be installed across one or more harnesses. They provide a declarative way to manage skill configurations, similar to how `requirements.txt` manages Python dependencies but with richer structure and metadata.

## File Format

Recipe files use YAML format with the `.yaml` or `.yml` extension. They should be placed in a predictable location (e.g., `.jefe/recipes/` in your project directory).

## Schema

### Top-Level Fields

```yaml
# Recipe metadata
name: string               # Required: Unique identifier for this recipe
description: string        # Optional: Human-readable description

# Target harnesses - which environments this recipe applies to
harnesses:                 # Optional: List of harness names (if omitted, applies to all)
  - harness-name-1
  - harness-name-2

# Skills to install
skills:                    # Optional: List of individual skills
  - source: string         # Required: Source name
    name: string           # Required: Skill name
    version: string        # Optional: Version constraint (semver)
    pinned: boolean        # Optional: Pin to specific version (default: false)

# Bundles to apply
bundles:                   # Optional: List of bundle names
  - bundle-name-1
  - bundle-name-2
```

## Field Descriptions

### `name` (required)
- Type: `string`
- A unique identifier for this recipe
- Used for tracking and referencing the recipe
- Should be kebab-case (e.g., `web-ui-tools`, `python-dev-env`)

### `description` (optional)
- Type: `string`
- Human-readable description of what this recipe provides
- Helps users understand the purpose and contents of the recipe

### `harnesses` (optional)
- Type: `list[string]`
- List of harness names this recipe should be applied to
- If omitted, the recipe applies to all available harnesses
- Harness names should match registered harness identifiers

### `skills` (optional)
- Type: `list[SkillSpec]`
- Individual skills to install
- Each skill specification includes:
  - `source` (required): The skill source name
  - `name` (required): The skill name within that source
  - `version` (optional): Version constraint using semantic versioning
  - `pinned` (optional): Whether to pin to this exact version (default: false)

#### Version Constraints

Version constraints follow semantic versioning conventions:
- `1.2.3` - Exact version
- `^1.2.3` - Compatible with 1.2.3 (>=1.2.3, <2.0.0)
- `~1.2.3` - Approximately 1.2.3 (>=1.2.3, <1.3.0)
- `>=1.2.0` - Greater than or equal to 1.2.0
- `*` or omitted - Any version (latest)

### `bundles` (optional)
- Type: `list[string]`
- List of bundle names to apply
- Bundles are pre-configured collections of skills
- Bundle names should match registered bundle identifiers

## Examples

### Minimal Recipe

```yaml
name: basic-tools
description: Essential tools for any project
skills:
  - source: core
    name: git-helpers
  - source: core
    name: file-utils
```

### Full-Featured Recipe

```yaml
name: web-development
description: Complete web development environment with React, TypeScript, and testing tools

harnesses:
  - claude-code
  - cursor

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

bundles:
  - frontend-essentials
  - testing-suite
```

### Harness-Specific Recipe

```yaml
name: python-data-science
description: Data science tools for Jupyter and Python environments

harnesses:
  - jupyter
  - vscode-python

skills:
  - source: data-science
    name: pandas-helpers

  - source: data-science
    name: matplotlib-snippets

  - source: data-science
    name: sklearn-templates

bundles:
  - numpy-toolkit
```

### Bundle-Only Recipe

```yaml
name: security-audit
description: Security scanning and audit tools

bundles:
  - security-scanners
  - vulnerability-checkers
  - code-analysis
```

## Validation

Recipe files are validated against a JSON Schema. The validation ensures:

1. Required fields are present
2. Field types are correct
3. Version constraints follow semantic versioning rules
4. References (harnesses, sources, skills, bundles) exist in the system

Validation occurs:
- On recipe file load
- Before applying a recipe to a harness
- During recipe sync operations

## Usage

### Loading a Recipe

```bash
# Load recipe from file
jefe recipe load web-ui.yaml

# Apply recipe to current project
jefe recipe apply web-development

# Apply recipe to specific harness
jefe recipe apply web-development --harness claude-code
```

### Creating a Recipe

```bash
# Create new recipe interactively
jefe recipe create

# Export current configuration as recipe
jefe recipe export my-setup.yaml
```

## Best Practices

1. **Use descriptive names**: Choose clear, self-explanatory recipe names
2. **Add descriptions**: Always include a description explaining the recipe's purpose
3. **Pin critical versions**: Use `pinned: true` for skills where version stability is crucial
4. **Prefer bundles**: Group related skills into bundles for easier management
5. **Target specific harnesses**: Only target harnesses where the skills are relevant
6. **Version conservatively**: Use `^` (caret) constraints for flexibility with safety
7. **Document constraints**: Add comments explaining why specific versions are pinned

## Schema Location

The JSON Schema for recipe files is located at:
- `src/jefe/server/schemas/recipe.py` (Pydantic model)
- Generated JSON Schema available via API: `GET /api/schemas/recipe`

## Related Concepts

- **Skills**: Individual units of functionality that can be installed
- **Bundles**: Pre-configured collections of related skills
- **Harnesses**: Target environments where skills are installed (e.g., Claude Code, Cursor, VS Code)
- **Sources**: Repositories of skills (e.g., Git repos, marketplace)
