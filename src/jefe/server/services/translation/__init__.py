"""Translation service for converting between harness config formats.

This module provides services for:
- Syntax translation: Converting between config file formats (CLAUDE.md <-> AGENTS.md, etc.)
- Preserving content integrity during translation
- Audit logging of all translations
"""

from jefe.server.services.translation.service import (
    TranslationResult,
    TranslationService,
)
from jefe.server.services.translation.syntax import (
    TranslationError,
    translate_syntax,
)

__all__ = [
    "TranslationError",
    "TranslationResult",
    "TranslationService",
    "translate_syntax",
]
