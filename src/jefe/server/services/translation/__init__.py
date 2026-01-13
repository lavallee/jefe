"""Translation service for converting between harness config formats.

This module provides services for:
- Syntax translation: Converting between config file formats (CLAUDE.md <-> AGENTS.md, etc.)
- Preserving content integrity during translation
"""

from jefe.server.services.translation.syntax import (
    TranslationError,
    translate_syntax,
)

__all__ = [
    "TranslationError",
    "translate_syntax",
]
