"""InstalledSkill model."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Enum as SqlEnum
from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from jefe.data.models.base import BaseModel

if TYPE_CHECKING:
    from jefe.data.models.harness import Harness
    from jefe.data.models.project import Project
    from jefe.data.models.skill import Skill


class InstallScope(str, Enum):
    """Scope of a skill installation."""

    GLOBAL = "global"
    PROJECT = "project"


class InstalledSkill(BaseModel):
    """Tracks which skills are installed where (global vs project, which harness)."""

    __tablename__ = "installed_skills"
    __table_args__ = (
        UniqueConstraint(
            "skill_id",
            "harness_id",
            "scope",
            "project_id",
            name="uq_installed_skill_identity",
        ),
    )

    skill_id: Mapped[int] = mapped_column(
        ForeignKey("skills.id", ondelete="CASCADE"), nullable=False
    )
    harness_id: Mapped[int] = mapped_column(
        ForeignKey("harnesses.id", ondelete="CASCADE"), nullable=False
    )
    scope: Mapped[InstallScope] = mapped_column(
        SqlEnum(
            InstallScope,
            name="install_scope",
            values_callable=lambda obj: [item.value for item in obj],
        ),
        nullable=False,
    )
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=True
    )
    installed_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    pinned_version: Mapped[str | None] = mapped_column(String(50), nullable=True)

    skill: Mapped[Skill] = relationship()
    harness: Mapped[Harness] = relationship()
    project: Mapped[Project | None] = relationship()
