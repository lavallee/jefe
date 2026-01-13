"""Schemas for knowledge API."""

from datetime import datetime

from pydantic import BaseModel, Field


class KnowledgeIngestRequest(BaseModel):
    """Request to ingest a URL into the knowledge base."""

    source_url: str = Field(..., description="URL to ingest")
    content_type: str | None = Field(
        None, description="Optional content type hint (e.g., 'documentation', 'article')"
    )


class KnowledgeEntryCreate(BaseModel):
    """Knowledge entry create payload."""

    source_url: str = Field(..., description="Original source URL")
    title: str = Field(..., description="Entry title")
    content: str = Field(..., description="Extracted full text content")
    summary: str = Field(..., description="LLM-generated summary")
    tags: list[str] = Field(default_factory=list, description="Tags and categories")


class KnowledgeEntryResponse(BaseModel):
    """Knowledge entry response payload."""

    id: int = Field(..., description="Entry ID")
    source_url: str = Field(..., description="Original source URL")
    title: str = Field(..., description="Entry title")
    summary: str = Field(..., description="LLM-generated summary")
    tags: list[str] = Field(default_factory=list, description="Tags and categories")
    created_at: datetime = Field(..., description="Timestamp when entry was ingested")


class KnowledgeEntryDetailResponse(KnowledgeEntryResponse):
    """Detailed knowledge entry response with full content."""

    content: str = Field(..., description="Full extracted text content")


class KnowledgeSearchRequest(BaseModel):
    """Request to search knowledge entries."""

    q: str | None = Field(None, description="Text query to search in title/summary/content")
    tags: list[str] | None = Field(None, description="Filter by tags")
    limit: int = Field(20, ge=1, le=100, description="Maximum number of results")
    offset: int = Field(0, ge=0, description="Offset for pagination")
