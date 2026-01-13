"""Harness configuration model."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Enum as SqlEnum
from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from jefe.data.models.base import BaseModel

if TYPE_CHECKING:
    from jefe.data.models.harness import Harness
    from jefe.data.models.project import Project


class ConfigScope(str, Enum):
    """Scope of a harness configuration."""

    GLOBAL = "global"
    PROJECT = "project"


class HarnessConfig(BaseModel):
    """Discovered harness configuration entry."""

    __tablename__ = "harness_configs"
    __table_args__ = (
        UniqueConstraint(
            "harness_id",
            "scope",
            "kind",
            "path",
            "project_id",
            name="uq_harness_config_identity",
        ),
    )

    harness_id: Mapped[int] = mapped_column(
        ForeignKey("harnesses.id", ondelete="CASCADE"), nullable=False
    )
    scope: Mapped[ConfigScope] = mapped_column(
        SqlEnum(
            ConfigScope,
            name="config_scope",
            values_callable=lambda obj: [item.value for item in obj],
        ),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    path: Mapped[str] = mapped_column(String(1024), nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=True
    )

    harness: Mapped[Harness] = relationship(back_populates="configs")
    project: Mapped[Project | None] = relationship()
