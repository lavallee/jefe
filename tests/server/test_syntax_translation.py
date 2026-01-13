"""Tests for syntax translation between harness config formats."""

from typing import ClassVar

import pytest

from jefe.server.services.translation import TranslationError, translate_syntax


class TestTranslateSyntaxInstructions:
    """Tests for translating instruction files (Markdown)."""

    def test_same_harness_returns_unchanged(self) -> None:
        """When source and target are the same, content is unchanged."""
        content = "# Project Overview\n\nThis is my project."
        result = translate_syntax(content, "claude-code", "claude-code")
        assert result == content

    def test_claude_to_codex_basic(self) -> None:
        """Claude CLAUDE.md to Codex AGENTS.md basic translation."""
        content = """# Project Overview

This is a Python project.

## Getting Started

Run `pip install -e .`
"""
        result = translate_syntax(content, "claude-code", "codex_cli")

        assert "<!-- Translated from Claude Code format to Codex CLI format -->" in result
        # Section headings should be mapped
        assert "# Overview" in result or "# Project Overview" in result
        assert "## Getting Started" in result
        # Content preserved
        assert "This is a Python project." in result
        assert "pip install -e ." in result

    def test_codex_to_claude_basic(self) -> None:
        """Codex AGENTS.md to Claude CLAUDE.md basic translation."""
        content = """# Overview

A TypeScript project.

## Coding Conventions

Use 4 spaces for indentation.
"""
        result = translate_syntax(content, "codex_cli", "claude-code")

        assert "<!-- Translated from Codex CLI format to Claude Code format -->" in result
        assert "# Project Overview" in result
        assert "## Conventions" in result
        assert "A TypeScript project." in result
        assert "Use 4 spaces for indentation." in result

    def test_claude_to_gemini_basic(self) -> None:
        """Claude CLAUDE.md to Gemini GEMINI.md basic translation."""
        content = """# Agent Instructions

Follow these rules.

## Important Files

- src/main.py
- config.yaml
"""
        result = translate_syntax(content, "claude-code", "gemini_cli")

        assert "<!-- Translated from Claude Code format to Gemini CLI format -->" in result
        assert "# Instructions" in result
        assert "## Important Files" in result
        assert "Follow these rules." in result

    def test_opencode_to_claude_basic(self) -> None:
        """OpenCode agent file to Claude CLAUDE.md basic translation."""
        content = """# Instructions

You are a helpful coding assistant.

## Development Setup

1. Clone the repo
2. Run npm install
"""
        result = translate_syntax(content, "opencode", "claude-code")

        assert "<!-- Translated from OpenCode format to Claude Code format -->" in result
        assert "# Agent Instructions" in result
        assert "## Development" in result

    def test_gemini_to_codex_basic(self) -> None:
        """Gemini GEMINI.md to Codex AGENTS.md basic translation."""
        content = """# Project Overview

A Rust project.

## Build

cargo build --release
"""
        result = translate_syntax(content, "gemini_cli", "codex_cli")

        assert "<!-- Translated from Gemini CLI format to Codex CLI format -->" in result
        assert "# Overview" in result
        assert "## Build" in result

    def test_preserves_code_blocks(self) -> None:
        """Code blocks are preserved during translation."""
        content = """# Development

## Commands

```bash
make build
make test
make lint
```

Run these before committing.
"""
        result = translate_syntax(content, "claude-code", "codex_cli")

        assert "```bash" in result
        assert "make build" in result
        assert "make test" in result
        assert "make lint" in result
        assert "```" in result

    def test_preserves_nested_sections(self) -> None:
        """Nested section hierarchy is preserved."""
        content = """# Overview

## Architecture

### Backend

FastAPI-based REST API.

### Frontend

React with TypeScript.

## Deployment

Docker containers.
"""
        result = translate_syntax(content, "claude-code", "codex_cli")

        # All sections should be present
        assert "### Backend" in result
        assert "### Frontend" in result
        assert "FastAPI-based REST API." in result
        assert "React with TypeScript." in result
        assert "Docker containers." in result

    def test_preserves_lists(self) -> None:
        """Lists are preserved during translation."""
        content = """# Dependencies

Required packages:

- fastapi
- uvicorn
- sqlalchemy

Numbered steps:

1. Clone the repo
2. Install dependencies
3. Run the server
"""
        result = translate_syntax(content, "claude-code", "opencode")

        assert "- fastapi" in result
        assert "- uvicorn" in result
        assert "1. Clone the repo" in result
        assert "2. Install dependencies" in result

    def test_handles_empty_content(self) -> None:
        """Empty content is handled gracefully."""
        result = translate_syntax("", "claude-code", "codex_cli")
        assert "<!-- Translated from Claude Code format to Codex CLI format -->" in result

    def test_handles_no_sections(self) -> None:
        """Content with no markdown headings is handled."""
        content = "Just some plain text without any sections."
        result = translate_syntax(content, "claude-code", "codex_cli")
        assert "Just some plain text without any sections." in result

    def test_unknown_section_preserved(self) -> None:
        """Sections without mappings are preserved as-is."""
        content = """# Project Overview

Test project.

## Custom Section That Has No Mapping

This custom content should be preserved.
"""
        result = translate_syntax(content, "claude-code", "codex_cli")
        assert "## Custom Section That Has No Mapping" in result
        assert "This custom content should be preserved." in result

    def test_harness_name_normalization(self) -> None:
        """Harness names can be provided in various formats."""
        content = "# Test"

        # Should all work with various name formats
        result1 = translate_syntax(content, "claude-code", "codex_cli")
        result2 = translate_syntax(content, "claude_code", "codex_cli")
        result3 = translate_syntax(content, "claude", "codex")

        # All should produce the same output (same harnesses)
        assert result1 == result2 == result3


class TestTranslateSyntaxSettings:
    """Tests for translating settings files (JSON/TOML)."""

    def test_json_to_json_key_mapping(self) -> None:
        """JSON settings with key mapping between formats."""
        content = """{
  "apiKey": "sk-xxx",
  "model": "claude-3-opus",
  "maxTokens": 4096
}"""
        result = translate_syntax(content, "claude-code", "opencode", config_kind="settings")

        # Should be valid JSON
        import json
        parsed = json.loads(result)

        # Keys should be mapped
        assert "api_key" in parsed
        assert parsed["api_key"] == "sk-xxx"
        assert "model" in parsed
        assert "max_tokens" in parsed

    def test_json_to_toml_conversion(self) -> None:
        """JSON settings converted to TOML format."""
        content = """{
  "apiKey": "sk-xxx",
  "model": "gpt-4",
  "maxTokens": 4096
}"""
        result = translate_syntax(content, "claude-code", "codex_cli", config_kind="settings")

        # Should be valid TOML
        import tomllib
        parsed = tomllib.loads(result)

        # Keys should be mapped to snake_case
        assert "api_key" in parsed
        assert parsed["api_key"] == "sk-xxx"
        assert "model" in parsed
        assert "max_tokens" in parsed

    def test_toml_to_json_conversion(self) -> None:
        """TOML settings converted to JSON format."""
        content = """api_key = "sk-xxx"
model = "codex-001"
max_tokens = 2048
"""
        result = translate_syntax(content, "codex_cli", "claude-code", config_kind="settings")

        # Should be valid JSON
        import json
        parsed = json.loads(result)

        # Keys should be mapped to camelCase
        assert "apiKey" in parsed
        assert parsed["apiKey"] == "sk-xxx"
        assert "model" in parsed
        assert "maxTokens" in parsed

    def test_preserves_unmapped_keys(self) -> None:
        """Keys without explicit mappings are preserved."""
        content = """{
  "apiKey": "sk-xxx",
  "customSetting": "value",
  "anotherCustom": true
}"""
        result = translate_syntax(content, "claude-code", "opencode", config_kind="settings")

        import json
        parsed = json.loads(result)

        # Mapped keys
        assert "api_key" in parsed
        # Unmapped keys preserved as-is
        assert "customSetting" in parsed
        assert parsed["customSetting"] == "value"
        assert "anotherCustom" in parsed
        assert parsed["anotherCustom"] is True

    def test_skips_unsupported_settings(self) -> None:
        """Settings that don't map to target format are skipped."""
        content = """{
  "apiKey": "sk-xxx",
  "autoApprovePatterns": ["*.md", "*.txt"]
}"""
        # autoApprovePatterns is not supported in Codex CLI
        result = translate_syntax(content, "claude-code", "codex_cli", config_kind="settings")

        import tomllib
        parsed = tomllib.loads(result)

        assert "api_key" in parsed
        # autoApprovePatterns should not be in output (mapped to None)
        assert "autoApprovePatterns" not in parsed
        assert "auto_approve_patterns" not in parsed

    def test_jsonc_comments_stripped(self) -> None:
        """JSONC comments are stripped from OpenCode config."""
        content = """{
  // This is a comment
  "api_key": "sk-xxx",
  "model": "gpt-4" // inline comment
}"""
        result = translate_syntax(content, "opencode", "claude-code", config_kind="settings")

        import json
        parsed = json.loads(result)

        assert "apiKey" in parsed
        assert parsed["apiKey"] == "sk-xxx"

    def test_nested_json_objects(self) -> None:
        """Nested JSON objects are preserved."""
        content = """{
  "apiKey": "sk-xxx",
  "nested": {
    "foo": "bar",
    "baz": 123
  }
}"""
        result = translate_syntax(content, "claude-code", "opencode", config_kind="settings")

        import json
        parsed = json.loads(result)

        assert "nested" in parsed
        assert parsed["nested"]["foo"] == "bar"
        assert parsed["nested"]["baz"] == 123

    def test_arrays_preserved(self) -> None:
        """Arrays are preserved in settings."""
        content = """{
  "apiKey": "sk-xxx",
  "ignoredPaths": ["node_modules", ".git", "dist"]
}"""
        result = translate_syntax(content, "claude-code", "opencode", config_kind="settings")

        import json
        parsed = json.loads(result)

        assert "ignore_patterns" in parsed
        assert parsed["ignore_patterns"] == ["node_modules", ".git", "dist"]


class TestTranslationError:
    """Tests for error handling in translations."""

    def test_invalid_json_raises_error(self) -> None:
        """Invalid JSON raises TranslationError."""
        content = "{ invalid json }"

        with pytest.raises(TranslationError) as exc_info:
            translate_syntax(content, "claude-code", "opencode", config_kind="settings")

        assert "Failed to parse JSON" in str(exc_info.value)

    def test_invalid_toml_raises_error(self) -> None:
        """Invalid TOML raises TranslationError."""
        content = "invalid = = toml"

        with pytest.raises(TranslationError) as exc_info:
            translate_syntax(content, "codex_cli", "claude-code", config_kind="settings")

        assert "Failed to parse TOML" in str(exc_info.value)


class TestAllHarnessPairs:
    """Test all harness pair combinations work."""

    HARNESSES: ClassVar[list[str]] = ["claude-code", "codex_cli", "opencode", "gemini_cli"]

    @pytest.mark.parametrize("source", HARNESSES)
    @pytest.mark.parametrize("target", HARNESSES)
    def test_instruction_translation_pair(self, source: str, target: str) -> None:
        """Every harness pair can translate instructions."""
        content = """# Project Overview

A test project for translation.

## Development

Run the tests.
"""
        # Should not raise
        result = translate_syntax(content, source, target, config_kind="instructions")  # type: ignore[arg-type]

        # Content should be present
        assert "test project" in result.lower() or "translation" in result.lower()
        assert "run the tests" in result.lower()

    @pytest.mark.parametrize(
        "source,target",
        [
            ("claude-code", "opencode"),
            ("claude-code", "gemini_cli"),
            ("opencode", "claude-code"),
            ("opencode", "gemini_cli"),
            ("gemini_cli", "claude-code"),
            ("gemini_cli", "opencode"),
        ],
    )
    def test_json_to_json_settings_pairs(self, source: str, target: str) -> None:
        """JSON-based harness pairs can translate settings."""
        content = """{
  "model": "test-model",
  "temperature": 0.7
}"""
        # Should not raise
        result = translate_syntax(content, source, target, config_kind="settings")  # type: ignore[arg-type]

        import json
        parsed = json.loads(result)
        assert "model" in parsed
        assert parsed["model"] == "test-model"

    @pytest.mark.parametrize(
        "source,target",
        [
            ("claude-code", "codex_cli"),
            ("opencode", "codex_cli"),
            ("gemini_cli", "codex_cli"),
        ],
    )
    def test_json_to_toml_settings_pairs(self, source: str, target: str) -> None:
        """JSON to TOML harness pairs can translate settings."""
        content = """{
  "model": "test-model",
  "temperature": 0.7
}"""
        result = translate_syntax(content, source, target, config_kind="settings")  # type: ignore[arg-type]

        import tomllib
        parsed = tomllib.loads(result)
        assert "model" in parsed
        assert parsed["model"] == "test-model"

    @pytest.mark.parametrize(
        "source,target",
        [
            ("codex_cli", "claude-code"),
            ("codex_cli", "opencode"),
            ("codex_cli", "gemini_cli"),
        ],
    )
    def test_toml_to_json_settings_pairs(self, source: str, target: str) -> None:
        """TOML to JSON harness pairs can translate settings."""
        content = """model = "test-model"
temperature = 0.7
"""
        result = translate_syntax(content, source, target, config_kind="settings")  # type: ignore[arg-type]

        import json
        parsed = json.loads(result)
        assert "model" in parsed
        assert parsed["model"] == "test-model"


class TestContentIntegrity:
    """Tests ensuring content integrity is preserved."""

    def test_roundtrip_instructions_content_preserved(self) -> None:
        """Content is preserved after roundtrip translation."""
        original = """# Project Overview

This is a Python web application using FastAPI.

## Architecture

- Backend: FastAPI + SQLAlchemy
- Frontend: React + TypeScript
- Database: PostgreSQL

## Getting Started

```bash
pip install -e ".[dev]"
uvicorn app:main --reload
```

## Testing

Run tests with pytest:

```bash
pytest -v
```
"""
        # Claude -> Codex -> Claude
        to_codex = translate_syntax(original, "claude-code", "codex_cli")
        back_to_claude = translate_syntax(to_codex, "codex_cli", "claude-code")

        # Core content should be preserved
        assert "Python web application" in back_to_claude
        assert "FastAPI" in back_to_claude
        assert "SQLAlchemy" in back_to_claude
        assert "pip install" in back_to_claude
        assert "pytest -v" in back_to_claude

    def test_special_characters_preserved(self) -> None:
        """Special characters in content are preserved."""
        content = """# Test

Special chars: `code`, *bold*, _italic_, ~strike~

Symbols: @user, #tag, $var, %percent, ^caret, &amp, |pipe
"""
        result = translate_syntax(content, "claude-code", "codex_cli")

        assert "`code`" in result
        assert "*bold*" in result
        assert "@user" in result
        assert "#tag" in result
        assert "$var" in result

    def test_urls_preserved(self) -> None:
        """URLs in content are preserved."""
        content = """# Links

- GitHub: https://github.com/user/repo
- Docs: https://docs.example.com/api?version=2&format=json
"""
        result = translate_syntax(content, "claude-code", "gemini_cli")

        assert "https://github.com/user/repo" in result
        assert "https://docs.example.com/api?version=2&format=json" in result

    def test_multiline_code_blocks_preserved(self) -> None:
        """Multiline code blocks with language tags preserved."""
        content = '''# Examples

```python
def hello():
    """Say hello."""
    print("Hello, world!")
```

```typescript
const greet = (name: string): void => {
    console.log(`Hello, ${name}!`);
};
```
'''
        result = translate_syntax(content, "claude-code", "opencode")

        assert "```python" in result
        assert '"""Say hello."""' in result
        assert "```typescript" in result
        assert "console.log" in result
