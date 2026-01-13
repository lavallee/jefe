"""Knowledge entry model for best practices knowledge base."""

from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from jefe.data.models.base import BaseModel


class KnowledgeEntry(BaseModel):
    """Knowledge base entry with extracted content and LLM summary."""

    __tablename__ = "knowledge_entries"

    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array as string
    embedding: Mapped[bytes | None] = mapped_column(
        Text, nullable=True
    )  # BLOB for future vector search

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
