"""Manifestation model."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from jefe.data.models.base import BaseModel

if TYPE_CHECKING:
    from jefe.data.models.project import Project


class ManifestationType(str, Enum):
    """Type of project manifestation."""

    LOCAL = "local"
    REMOTE = "remote"


class Manifestation(BaseModel):
    """Project manifestation (local clone or remote URL)."""

    __tablename__ = "manifestations"

    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[ManifestationType] = mapped_column(
        SqlEnum(
            ManifestationType,
            name="manifestation_type",
            values_callable=lambda obj: [item.value for item in obj],
        ),
        nullable=False,
    )
    path: Mapped[str] = mapped_column(String(1024), nullable=False)
    machine_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_seen: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    project: Mapped[Project] = relationship(back_populates="manifestations")
