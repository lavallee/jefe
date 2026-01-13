"""Skill model."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from jefe.data.models.base import BaseModel

if TYPE_CHECKING:
    from jefe.data.models.skill_source import SkillSource


class Skill(BaseModel):
    """Individual skill metadata."""

    __tablename__ = "skills"

    source_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("skill_sources.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tags: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array as string
    metadata_json: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # JSON object as string

    source: Mapped[SkillSource] = relationship(
        back_populates="skills",
    )

    def get_tags_list(self) -> list[str]:
        """Parse tags JSON string to list."""
        import json

        if self.tags:
            try:
                result = json.loads(self.tags)
                return result if isinstance(result, list) else []
            except json.JSONDecodeError:
                return []
        return []

    def set_tags_list(self, tags: list[str]) -> None:
        """Convert tags list to JSON string."""
        import json

        self.tags = json.dumps(tags)

    def get_metadata_dict(self) -> dict[str, Any]:
        """Parse metadata JSON string to dict."""
        import json

        if self.metadata_json:
            try:
                result = json.loads(self.metadata_json)
                return result if isinstance(result, dict) else {}
            except json.JSONDecodeError:
                return {}
        return {}

    def set_metadata_dict(self, metadata: dict[str, Any]) -> None:
        """Convert metadata dict to JSON string."""
        import json

        self.metadata_json = json.dumps(metadata)
