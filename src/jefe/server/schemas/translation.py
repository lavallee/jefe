"""Schemas for translation API."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from jefe.data.models.translation_log import TranslationType


class TranslateRequest(BaseModel):
    """Translation request payload."""

    content: str = Field(..., description="Content to translate")
    source_harness: Annotated[str, Field(..., description="Source harness name")]
    target_harness: Annotated[str, Field(..., description="Target harness name")]
    config_kind: Literal["settings", "instructions"] = Field(
        "instructions", description="Type of configuration being translated"
    )
    project_id: int | None = Field(None, description="Optional project ID")
    translation_type: Literal["syntax", "semantic"] = Field(
        "syntax",
        description="Type of translation: 'syntax' for rule-based, 'semantic' for LLM-powered",
    )
    model: str | None = Field(
        None, description="Optional model override for semantic translation"
    )


class TranslateResponse(BaseModel):
    """Translation response payload."""

    output: str = Field(..., description="Translated content")
    diff: str = Field(..., description="Unified diff of changes")
    log_id: int = Field(..., description="Translation log ID")


class TranslationLogResponse(BaseModel):
    """Translation log response payload."""

    id: int = Field(..., description="Log ID")
    input_text: str = Field(..., description="Original content")
    output_text: str = Field(..., description="Translated content")
    translation_type: TranslationType = Field(..., description="Translation type")
    model_name: str = Field(..., description="Translation model name")
    project_id: int | None = Field(None, description="Associated project ID")
    created_at: datetime = Field(..., description="Creation timestamp")


class ApplyTranslationRequest(BaseModel):
    """Apply translation request payload."""

    file_path: str = Field(..., description="Path to write the translated content")
    content: str = Field(..., description="Content to write")
