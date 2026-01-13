"""Translation service for converting between harness config formats.

This module provides services for:
- Syntax translation: Converting between config file formats (CLAUDE.md <-> AGENTS.md, etc.)
- Semantic translation: LLM-powered style-adapted translation
- Preserving content integrity during translation
- Audit logging of all translations
"""

from jefe.server.services.translation.semantic import (
    SemanticTranslationResult,
    translate_semantic,
)
from jefe.server.services.translation.service import (
    TranslationResult,
    TranslationService,
)
from jefe.server.services.translation.syntax import (
    TranslationError,
    translate_syntax,
)

__all__ = [
    "SemanticTranslationResult",
    "TranslationError",
    "TranslationResult",
    "TranslationService",
    "translate_semantic",
    "translate_syntax",
]
