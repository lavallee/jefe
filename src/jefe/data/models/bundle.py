"""Bundle model."""

from __future__ import annotations

from typing import Any

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from jefe.data.models.base import BaseModel


class Bundle(BaseModel):
    """Skill bundle/profile for bulk installation."""

    __tablename__ = "bundles"

    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    skill_refs: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # JSON array of skill references

    def get_skill_refs_list(self) -> list[dict[str, Any]]:
        """Parse skill_refs JSON string to list of dicts.

        Each skill ref dict should have:
        - source: str (source name or ID)
        - name: str (skill name)
        """
        import json

        if self.skill_refs:
            try:
                result = json.loads(self.skill_refs)
                return result if isinstance(result, list) else []
            except json.JSONDecodeError:
                return []
        return []

    def set_skill_refs_list(self, skill_refs: list[dict[str, Any]]) -> None:
        """Convert skill_refs list to JSON string."""
        import json

        self.skill_refs = json.dumps(skill_refs)
