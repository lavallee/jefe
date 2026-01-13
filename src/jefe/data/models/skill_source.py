"""SkillSource model."""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from sqlalchemy import Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from jefe.data.models.base import BaseModel

if TYPE_CHECKING:
    from jefe.data.models.skill import Skill


class SourceType(enum.Enum):
    """Type of skill source."""

    GIT = "git"
    MARKETPLACE = "marketplace"


class SyncStatus(enum.Enum):
    """Sync status of a skill source."""

    PENDING = "pending"
    SYNCING = "syncing"
    SYNCED = "synced"
    ERROR = "error"


class SkillSource(BaseModel):
    """Skill source repository or marketplace."""

    __tablename__ = "skill_sources"

    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    source_type: Mapped[SourceType] = mapped_column(
        Enum(SourceType, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
    )
    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sync_status: Mapped[SyncStatus] = mapped_column(
        Enum(SyncStatus, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=SyncStatus.PENDING,
    )
    last_synced_at: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )  # ISO 8601 timestamp as string

    skills: Mapped[list[Skill]] = relationship(
        back_populates="source",
        cascade="all, delete-orphan",
        order_by="Skill.id",
    )
