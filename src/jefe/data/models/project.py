"""Project model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from jefe.data.models.base import BaseModel

if TYPE_CHECKING:
    from jefe.data.models.manifestation import Manifestation
    from jefe.data.models.translation_log import TranslationLog


class Project(BaseModel):
    """Project registry entry."""

    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    manifestations: Mapped[list[Manifestation]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="Manifestation.id",
    )
    translation_logs: Mapped[list[TranslationLog]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="TranslationLog.id",
    )
