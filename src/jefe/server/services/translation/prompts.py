"""Prompts for semantic translation between harness formats.

This module defines the prompts used for LLM-powered semantic translation
that adapts prompting style while preserving meaning.
"""

from __future__ import annotations

from typing import Literal

from jefe.server.services.translation.syntax import HarnessName

# Display names for harnesses
HARNESS_DISPLAY_NAMES: dict[HarnessName, str] = {
    "claude-code": "Claude Code",
    "codex_cli": "OpenAI Codex CLI",
    "opencode": "OpenCode",
    "gemini_cli": "Gemini CLI",
}

# Harness-specific context for prompting style
HARNESS_CONTEXT: dict[HarnessName, str] = {
    "claude-code": """Claude Code is Anthropic's official CLI for Claude. It uses:
- CLAUDE.md files for project instructions
- settings.json for configuration
- A conversational, direct communication style
- Emphasis on safety, helpfulness, and honest limitations
- Markdown formatting with clear section headers
- Specific mention of tool usage patterns and file operations
- Focus on careful code review and verification""",
    "codex_cli": """OpenAI Codex CLI is OpenAI's code generation assistant. It uses:
- AGENTS.md files for project instructions
- config.toml for configuration
- A technical, code-focused communication style
- Emphasis on efficiency and minimal explanations
- Structured output with clear formatting
- Focus on generating working code quickly
- Agent-based workflow with clear task breakdowns""",
    "opencode": """OpenCode is an open-source AI coding assistant. It uses:
- Agent files in .opencode/agent/ for instructions
- opencode.json for configuration
- A flexible, customizable communication style
- Emphasis on extensibility and user control
- Support for multiple AI providers
- Plugin-based architecture awareness
- Context-aware code generation patterns""",
    "gemini_cli": """Gemini CLI is Google's AI-powered coding assistant. It uses:
- GEMINI.md files for project instructions
- settings.json for configuration
- A helpful, informative communication style
- Emphasis on code quality and best practices
- Google-style documentation patterns
- Integration with Google Cloud services awareness
- Focus on explanation alongside code generation""",
}


def build_semantic_translation_prompt(
    content: str,
    source_harness: HarnessName,
    target_harness: HarnessName,
    config_kind: Literal["settings", "instructions"] = "instructions",
) -> str:
    """Build the prompt for semantic translation.

    Args:
        content: The content to translate
        source_harness: The source harness name
        target_harness: The target harness name
        config_kind: Whether this is settings or instructions

    Returns:
        The complete prompt for the LLM
    """
    source_name = HARNESS_DISPLAY_NAMES.get(source_harness, source_harness)
    target_name = HARNESS_DISPLAY_NAMES.get(target_harness, target_harness)
    source_context = HARNESS_CONTEXT.get(source_harness, "")
    target_context = HARNESS_CONTEXT.get(target_harness, "")

    if config_kind == "settings":
        return _build_settings_prompt(
            content, source_name, target_name, source_context, target_context
        )

    return _build_instructions_prompt(
        content, source_name, target_name, source_context, target_context
    )


def _build_instructions_prompt(
    content: str,
    source_name: str,
    target_name: str,
    source_context: str,
    target_context: str,
) -> str:
    """Build prompt for instruction file translation."""
    return f"""You are an expert at adapting AI coding assistant instructions between different tools while preserving meaning and intent.

## Task
Translate the following instruction file from {source_name} format to {target_name} format.

## Source Harness Context
{source_context}

## Target Harness Context
{target_context}

## Translation Guidelines
1. **Preserve Core Meaning**: Keep all technical requirements, constraints, and project-specific information intact.
2. **Adapt Prompting Style**: Adjust the tone, structure, and phrasing to match the target harness's conventions.
3. **Remap Section Names**: Use appropriate section headings for the target format.
4. **Maintain Technical Accuracy**: Don't alter code examples, file paths, or technical specifications.
5. **Keep Markdown Formatting**: Preserve lists, code blocks, links, and other formatting.
6. **Add Translation Note**: Include a brief comment at the top indicating the source format.

## Source Content ({source_name})
```markdown
{content}
```

## Instructions
Translate the above content to {target_name} format. Output ONLY the translated content, no additional explanation. Ensure the translation:
- Uses the appropriate section heading conventions for {target_name}
- Matches the communication style expected by {target_name}
- Preserves all essential information
- Is ready to use as-is in a {target_name} project

Translated content:"""


def _build_settings_prompt(
    content: str,
    source_name: str,
    target_name: str,
    source_context: str,
    target_context: str,
) -> str:
    """Build prompt for settings file translation."""
    return f"""You are an expert at adapting AI coding assistant configuration files between different tools.

## Task
Translate the following settings file from {source_name} format to {target_name} format.

## Source Harness Context
{source_context}

## Target Harness Context
{target_context}

## Translation Guidelines
1. **Map Configuration Keys**: Convert setting names to the target format's conventions.
2. **Preserve Values**: Keep configuration values exactly as specified.
3. **Handle Format Changes**: Convert between JSON/TOML as needed.
4. **Remove Unsupported Settings**: Omit settings not supported by the target harness.
5. **Add Equivalent Settings**: Add any required default settings for the target format.

## Key Mapping Notes
- API keys and credentials should be mapped to equivalent fields
- Model names may need adjustment for provider compatibility
- Path settings should use target format conventions
- Boolean settings may have different representations

## Source Content ({source_name})
```
{content}
```

## Instructions
Translate the above settings to {target_name} format. Output ONLY the translated content, no additional explanation.
- If {target_name} uses JSON, output valid JSON
- If {target_name} uses TOML, output valid TOML
- Include only settings that are supported by {target_name}

Translated settings:"""


# Model recommendation for translation
RECOMMENDED_MODEL = "anthropic/claude-sonnet-4"  # Good balance of quality and speed

# Maximum tokens for translation output
MAX_TRANSLATION_TOKENS = 4096

# Temperature for translation (lower for more deterministic output)
TRANSLATION_TEMPERATURE = 0.3
