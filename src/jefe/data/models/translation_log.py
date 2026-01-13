"""Translation log model for tracking translation history."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Enum as SqlEnum
from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from jefe.data.models.base import BaseModel

if TYPE_CHECKING:
    from jefe.data.models.project import Project


class TranslationType(str, Enum):
    """Types of translations that can be performed."""

    SYNTAX = "syntax"
    SEMANTIC = "semantic"


class TranslationLog(BaseModel):
    """Records of translation operations with input, output, and metadata.

    Tracks the history of translations performed, including the type of
    translation, the model used, and both input and output content.
    """

    __tablename__ = "translation_logs"

    input_text: Mapped[str] = mapped_column(Text, nullable=False)
    output_text: Mapped[str] = mapped_column(Text, nullable=False)
    translation_type: Mapped[TranslationType] = mapped_column(
        SqlEnum(
            TranslationType,
            values_callable=lambda obj: [item.value for item in obj],
        ),
        nullable=False,
    )
    model_name: Mapped[str] = mapped_column(nullable=False)
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
    )

    project: Mapped[Project | None] = relationship(
        back_populates="translation_logs",
    )
