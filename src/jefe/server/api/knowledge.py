"""Knowledge API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from jefe.data.database import get_session
from jefe.data.models.knowledge import KnowledgeEntry
from jefe.data.repositories.knowledge import KnowledgeRepository
from jefe.server.auth import APIKey
from jefe.server.schemas.knowledge import (
    KnowledgeEntryCreate,
    KnowledgeEntryDetailResponse,
    KnowledgeEntryResponse,
    KnowledgeIngestRequest,
)

router = APIRouter()


def _entry_to_response(entry: KnowledgeEntry) -> KnowledgeEntryResponse:
    """Convert a KnowledgeEntry model to a response schema."""
    return KnowledgeEntryResponse(
        id=entry.id,
        source_url=entry.source_url,
        title=entry.title,
        summary=entry.summary,
        tags=entry.get_tags_list(),
        created_at=entry.created_at,
    )


def _entry_to_detail_response(entry: KnowledgeEntry) -> KnowledgeEntryDetailResponse:
    """Convert a KnowledgeEntry model to a detailed response schema."""
    return KnowledgeEntryDetailResponse(
        id=entry.id,
        source_url=entry.source_url,
        title=entry.title,
        summary=entry.summary,
        content=entry.content,
        tags=entry.get_tags_list(),
        created_at=entry.created_at,
    )


@router.post(
    "/api/knowledge/ingest",
    response_model=KnowledgeEntryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def ingest_knowledge(
    _payload: KnowledgeIngestRequest,
    _api_key: APIKey,
    _session: AsyncSession = Depends(get_session),
) -> KnowledgeEntryResponse:
    """Ingest a URL into the knowledge base.

    Note: This is a placeholder implementation. In a production system, this would:
    1. Fetch the content from the URL
    2. Extract text from HTML/PDF/etc
    3. Use an LLM to generate a summary
    4. Extract or generate tags
    5. Store the processed entry

    For now, it returns a 501 Not Implemented.
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Ingestion pipeline not yet implemented. Use POST /api/knowledge directly to create entries.",
    )


@router.post(
    "/api/knowledge",
    response_model=KnowledgeEntryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_knowledge_entry(
    payload: KnowledgeEntryCreate,
    _api_key: APIKey,
    session: AsyncSession = Depends(get_session),
) -> KnowledgeEntryResponse:
    """Create a new knowledge entry directly."""
    repository = KnowledgeRepository(session)

    # Check if URL already exists
    existing = await repository.get_by_url(payload.source_url)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An entry with this source URL already exists",
        )

    # Create the entry
    entry = KnowledgeEntry(
        source_url=payload.source_url,
        title=payload.title,
        content=payload.content,
        summary=payload.summary,
    )
    entry.set_tags_list(payload.tags)

    session.add(entry)
    await session.commit()
    await session.refresh(entry)

    return _entry_to_response(entry)


@router.get("/api/knowledge", response_model=list[KnowledgeEntryResponse])
async def search_knowledge(
    q: str | None = None,
    tags: str | None = None,
    limit: int = 20,
    offset: int = 0,
    _api_key: APIKey = APIKey,
    session: AsyncSession = Depends(get_session),
) -> list[KnowledgeEntryResponse]:
    """Search knowledge entries.

    Args:
        q: Text query to search in title/summary/content
        tags: Comma-separated list of tags to filter by
        limit: Maximum number of results (1-100)
        offset: Offset for pagination
    """
    # Validate limit
    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Limit must be between 1 and 100",
        )

    # Parse tags
    tag_list = [tag.strip() for tag in tags.split(",")] if tags else None

    repository = KnowledgeRepository(session)
    entries = await repository.search(
        query=q,
        tags=tag_list,
        limit=limit,
        offset=offset,
    )

    return [_entry_to_response(entry) for entry in entries]


@router.get("/api/knowledge/{entry_id}", response_model=KnowledgeEntryDetailResponse)
async def get_knowledge_entry(
    entry_id: int,
    _api_key: APIKey,
    session: AsyncSession = Depends(get_session),
) -> KnowledgeEntryDetailResponse:
    """Get a knowledge entry by ID with full content."""
    repository = KnowledgeRepository(session)
    entry = await repository.get_by_id(entry_id)

    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge entry not found",
        )

    return _entry_to_detail_response(entry)


@router.delete("/api/knowledge/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge_entry(
    entry_id: int,
    _api_key: APIKey,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Delete a knowledge entry."""
    repository = KnowledgeRepository(session)
    entry = await repository.get_by_id(entry_id)

    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge entry not found",
        )

    await session.delete(entry)
    await session.commit()
