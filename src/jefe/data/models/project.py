"""Project and manifestation models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from jefe.data.models.base import BaseModel


class ManifestationType(str, Enum):
    """Type of project manifestation."""

    LOCAL = "local"
    REMOTE = "remote"


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
