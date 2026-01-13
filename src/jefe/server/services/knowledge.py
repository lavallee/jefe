"""Service for ingesting URLs into the knowledge base."""

from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import TYPE_CHECKING

import httpx

from jefe.data.models.knowledge import KnowledgeEntry
from jefe.data.repositories.knowledge import KnowledgeRepository
from jefe.server.llm.openrouter import OpenRouterClient, OpenRouterError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class KnowledgeIngestionError(Exception):
    """Raised when knowledge ingestion fails."""

    pass


@dataclass
class ExtractedContent:
    """Content extracted from a URL."""

    title: str
    content: str
    content_type: str


@dataclass
class IngestionResult:
    """Result of ingesting a URL."""

    entry: KnowledgeEntry
    summary: str
    tags: list[str]


class ContentExtractor:
    """Extract text content from HTML and Markdown."""

    @staticmethod
    def extract_html(html: str) -> ExtractedContent:
        """Extract text content and title from HTML.

        Args:
            html: Raw HTML content.

        Returns:
            ExtractedContent with title and cleaned text.
        """
        parser = _HTMLTextExtractor()
        parser.feed(html)

        title = parser.title or "Untitled"
        content = parser.get_text()

        return ExtractedContent(
            title=title,
            content=content,
            content_type="html",
        )

    @staticmethod
    def extract_markdown(markdown: str) -> ExtractedContent:
        """Extract text content and title from Markdown.

        Args:
            markdown: Raw Markdown content.

        Returns:
            ExtractedContent with title and cleaned text.
        """
        lines = markdown.strip().split("\n")
        title = "Untitled"

        # Try to find title from first heading
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("# "):
                title = stripped[2:].strip()
                break

        # Clean up markdown syntax for plain text
        content = markdown
        # Remove code block markers but keep code content
        content = re.sub(r"```[\w]*\n", "", content)
        content = re.sub(r"```", "", content)
        # Remove inline code markers
        content = re.sub(r"`([^`]+)`", r"\1", content)
        # Remove link syntax but keep text
        content = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", content)
        # Remove image syntax
        content = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", content)
        # Remove emphasis markers
        content = re.sub(r"\*\*([^*]+)\*\*", r"\1", content)
        content = re.sub(r"\*([^*]+)\*", r"\1", content)
        content = re.sub(r"__([^_]+)__", r"\1", content)
        content = re.sub(r"_([^_]+)_", r"\1", content)
        # Remove heading markers
        content = re.sub(r"^#{1,6}\s+", "", content, flags=re.MULTILINE)
        # Remove blockquote markers
        content = re.sub(r"^>\s*", "", content, flags=re.MULTILINE)
        # Remove horizontal rules
        content = re.sub(r"^[-*_]{3,}$", "", content, flags=re.MULTILINE)
        # Remove list markers
        content = re.sub(r"^[\s]*[-*+]\s+", "", content, flags=re.MULTILINE)
        content = re.sub(r"^[\s]*\d+\.\s+", "", content, flags=re.MULTILINE)
        # Collapse multiple newlines
        content = re.sub(r"\n{3,}", "\n\n", content)

        return ExtractedContent(
            title=title,
            content=content.strip(),
            content_type="markdown",
        )

    @classmethod
    def extract(cls, raw_content: str, content_type: str) -> ExtractedContent:
        """Extract content based on content type.

        Args:
            raw_content: Raw content from the URL.
            content_type: Content type (html or markdown).

        Returns:
            ExtractedContent with title and cleaned text.
        """
        if content_type.lower() in ("markdown", "md", "text/markdown"):
            return cls.extract_markdown(raw_content)
        else:
            return cls.extract_html(raw_content)


class _HTMLTextExtractor(HTMLParser):
    """HTML parser that extracts text content."""

    # Tags to skip content from (frozenset is immutable, no ClassVar needed)
    SKIP_TAGS = frozenset({"script", "style", "head", "meta", "link", "noscript", "svg", "path"})
    # Tags that typically contain main content
    CONTENT_TAGS = frozenset({"article", "main", "p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "td", "th"})

    def __init__(self) -> None:
        super().__init__()
        self._text: list[str] = []
        self._skip_depth = 0
        self._current_tag = ""
        self.title: str | None = None
        self._in_title = False

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]  # noqa: ARG002
    ) -> None:
        self._current_tag = tag.lower()
        if self._current_tag in self.SKIP_TAGS:
            self._skip_depth += 1
        if self._current_tag == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()
        if tag_lower in self.SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1
        if tag_lower == "title":
            self._in_title = False
        # Add spacing after block elements
        if tag_lower in ("p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6"):
            self._text.append("\n")

    def handle_data(self, data: str) -> None:
        if self._in_title and not self.title:
            self.title = data.strip()
        if self._skip_depth == 0:
            text = data.strip()
            if text:
                self._text.append(text)

    def get_text(self) -> str:
        """Get the extracted text content."""
        text = " ".join(self._text)
        # Collapse multiple spaces
        text = re.sub(r"[ \t]+", " ", text)
        # Collapse multiple newlines
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


class RateLimiter:
    """Simple rate limiter for URL fetching."""

    def __init__(self, requests_per_second: float = 1.0) -> None:
        """Initialize rate limiter.

        Args:
            requests_per_second: Maximum requests per second.
        """
        self._min_interval = 1.0 / requests_per_second
        self._last_request: float = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Acquire rate limit permit, waiting if necessary."""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request
            if elapsed < self._min_interval:
                await asyncio.sleep(self._min_interval - elapsed)
            self._last_request = time.monotonic()


# Default summarization prompt
SUMMARIZATION_PROMPT = """You are a technical documentation summarizer. Your task is to:
1. Read the following content extracted from a URL
2. Provide a concise summary (2-4 sentences) capturing the key points
3. Extract 3-7 relevant tags/categories for this content

Content:
{content}

Respond in this exact format:
SUMMARY:
<your summary here>

TAGS:
<comma-separated list of tags>

Example tags: python, testing, api-design, security, performance, documentation, tutorial, best-practices, etc."""


class KnowledgeService:
    """Service for ingesting URLs into the knowledge base."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        api_key: str | None = None,
        model: str | None = None,
        rate_limit: float = 1.0,
    ) -> None:
        """Initialize knowledge service.

        Args:
            session: Database session.
            api_key: OpenRouter API key (falls back to env var).
            model: LLM model to use for summarization.
            rate_limit: Maximum requests per second for URL fetching.
        """
        self.session = session
        self.repository = KnowledgeRepository(session)
        self._api_key = api_key
        self._model = model or "anthropic/claude-3-haiku"
        self._rate_limiter = RateLimiter(rate_limit)
        self._http_client: httpx.AsyncClient | None = None

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
                headers={
                    "User-Agent": "Jefe-KnowledgeBot/1.0",
                    "Accept": "text/html,text/markdown,text/plain,*/*",
                },
            )
        return self._http_client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None

    async def __aenter__(self) -> KnowledgeService:
        """Async context manager entry."""
        return self

    async def __aexit__(self, *args: object) -> None:
        """Async context manager exit."""
        await self.close()

    async def fetch_url(self, url: str) -> tuple[str, str]:
        """Fetch content from a URL.

        Args:
            url: URL to fetch.

        Returns:
            Tuple of (content, content_type).

        Raises:
            KnowledgeIngestionError: If fetching fails.
        """
        await self._rate_limiter.acquire()

        client = await self._get_http_client()
        try:
            response = await client.get(url)
            response.raise_for_status()

            content_type = response.headers.get("content-type", "text/html")
            if "markdown" in content_type.lower() or url.endswith((".md", ".markdown")):
                detected_type = "markdown"
            else:
                detected_type = "html"

            return response.text, detected_type

        except httpx.HTTPStatusError as e:
            raise KnowledgeIngestionError(
                f"Failed to fetch URL {url}: HTTP {e.response.status_code}"
            ) from e
        except httpx.RequestError as e:
            raise KnowledgeIngestionError(f"Failed to fetch URL {url}: {e!s}") from e

    def _parse_llm_response(self, response: str) -> tuple[str, list[str]]:
        """Parse LLM response to extract summary and tags.

        Args:
            response: Raw LLM response text.

        Returns:
            Tuple of (summary, tags).
        """
        summary = ""
        tags: list[str] = []

        lines = response.strip().split("\n")
        current_section = ""

        for line in lines:
            stripped = line.strip()
            if stripped.upper().startswith("SUMMARY:"):
                current_section = "summary"
                remaining = stripped[8:].strip()
                if remaining:
                    summary = remaining
            elif stripped.upper().startswith("TAGS:"):
                current_section = "tags"
                remaining = stripped[5:].strip()
                if remaining:
                    tags = [t.strip().lower() for t in remaining.split(",") if t.strip()]
            elif current_section == "summary" and stripped:
                summary = f"{summary} {stripped}" if summary else stripped
            elif current_section == "tags" and stripped:
                new_tags = [t.strip().lower() for t in stripped.split(",") if t.strip()]
                tags.extend(new_tags)

        # Apply defaults
        if not summary:
            summary = "Content extracted from URL."
        tags = list(dict.fromkeys(tags))  # Remove duplicates
        tags = [t for t in tags if t and len(t) <= 50]
        if not tags:
            tags = ["uncategorized"]

        return summary, tags

    async def summarize_content(self, content: str) -> tuple[str, list[str]]:
        """Generate summary and tags using LLM.

        Args:
            content: Text content to summarize.

        Returns:
            Tuple of (summary, tags).

        Raises:
            KnowledgeIngestionError: If summarization fails.
        """
        # Truncate content if too long (keep first ~8000 chars for context)
        max_content_length = 8000
        if len(content) > max_content_length:
            truncated = content[:max_content_length]
            last_period = truncated.rfind(". ")
            if last_period > max_content_length // 2:
                truncated = truncated[: last_period + 1]
            content = truncated + "\n\n[Content truncated...]"

        prompt = SUMMARIZATION_PROMPT.format(content=content)

        try:
            async with OpenRouterClient(api_key=self._api_key, model=self._model) as client:
                response = await client.complete(
                    prompt=prompt,
                    max_tokens=512,
                    temperature=0.3,
                )
        except OpenRouterError as e:
            raise KnowledgeIngestionError(f"LLM summarization failed: {e!s}") from e

        return self._parse_llm_response(response)

    async def ingest_url(
        self,
        url: str,
        content_type_hint: str | None = None,
    ) -> KnowledgeEntry:
        """Ingest a URL into the knowledge base.

        This method:
        1. Checks if URL already exists
        2. Fetches the URL content
        3. Extracts text from HTML/Markdown
        4. Uses LLM to generate summary and tags
        5. Stores the entry in the database

        Args:
            url: URL to ingest.
            content_type_hint: Optional hint for content type (html/markdown).

        Returns:
            Created KnowledgeEntry.

        Raises:
            KnowledgeIngestionError: If ingestion fails.
        """
        # Check for existing entry
        existing = await self.repository.get_by_url(url)
        if existing is not None:
            raise KnowledgeIngestionError(f"URL already exists in knowledge base: {url}")

        # Fetch content
        logger.info(f"Fetching URL: {url}")
        raw_content, detected_type = await self.fetch_url(url)

        # Use hint if provided, otherwise use detected type
        content_type = content_type_hint or detected_type

        # Extract text
        logger.info(f"Extracting content from {content_type}")
        extracted = ContentExtractor.extract(raw_content, content_type)

        # Generate summary and tags
        logger.info("Generating summary with LLM")
        summary, tags = await self.summarize_content(extracted.content)

        # Create entry
        entry = KnowledgeEntry(
            source_url=url,
            title=extracted.title,
            content=extracted.content,
            summary=summary,
        )
        entry.set_tags_list(tags)

        self.session.add(entry)
        await self.session.commit()
        await self.session.refresh(entry)

        logger.info(f"Created knowledge entry {entry.id}: {entry.title}")
        return entry
