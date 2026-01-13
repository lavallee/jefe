"""Tests for the knowledge ingestion service."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from jefe.data.database import configure_engine
from jefe.data.models.knowledge import KnowledgeEntry
from jefe.data.repositories.knowledge import KnowledgeRepository
from jefe.server.services.knowledge import (
    ContentExtractor,
    KnowledgeIngestionError,
    KnowledgeService,
    RateLimiter,
)

# --- ContentExtractor Tests ---


class TestContentExtractor:
    """Tests for ContentExtractor."""

    def test_extract_html_basic(self) -> None:
        """Extract text from basic HTML."""
        html = """
        <!DOCTYPE html>
        <html>
        <head><title>Test Page</title></head>
        <body>
            <h1>Welcome</h1>
            <p>This is a test paragraph.</p>
            <p>Another paragraph here.</p>
        </body>
        </html>
        """
        result = ContentExtractor.extract_html(html)

        assert result.title == "Test Page"
        assert "Welcome" in result.content
        assert "This is a test paragraph" in result.content
        assert "Another paragraph here" in result.content
        assert result.content_type == "html"

    def test_extract_html_strips_scripts_and_styles(self) -> None:
        """Script and style content should be stripped."""
        html = """
        <html>
        <head>
            <title>Page Title</title>
            <style>body { color: red; }</style>
        </head>
        <body>
            <script>console.log('ignored');</script>
            <p>Visible content</p>
            <noscript>No script fallback</noscript>
        </body>
        </html>
        """
        result = ContentExtractor.extract_html(html)

        assert result.title == "Page Title"
        assert "Visible content" in result.content
        assert "console.log" not in result.content
        assert "color: red" not in result.content

    def test_extract_html_no_title(self) -> None:
        """HTML without title should use default."""
        html = "<html><body><p>Just content</p></body></html>"
        result = ContentExtractor.extract_html(html)

        assert result.title == "Untitled"
        assert "Just content" in result.content

    def test_extract_markdown_with_title(self) -> None:
        """Extract title from markdown heading."""
        markdown = """# My Document

This is the first paragraph.

## Section 1

Content in section 1.

- List item 1
- List item 2
"""
        result = ContentExtractor.extract_markdown(markdown)

        assert result.title == "My Document"
        assert "This is the first paragraph" in result.content
        assert "Content in section 1" in result.content
        assert result.content_type == "markdown"

    def test_extract_markdown_removes_formatting(self) -> None:
        """Markdown formatting markers should be removed."""
        markdown = """# Title

**Bold text** and *italic text*.

`inline code` here.

```python
code block
```

[Link text](https://example.com)

![Image alt](image.png)
"""
        result = ContentExtractor.extract_markdown(markdown)

        assert "Bold text" in result.content
        assert "**" not in result.content
        assert "*italic text*" not in result.content
        assert "italic text" in result.content
        assert "`inline code`" not in result.content
        assert "inline code" in result.content
        assert "code block" in result.content
        assert "```" not in result.content
        assert "Link text" in result.content
        assert "https://example.com" not in result.content
        assert "Image alt" in result.content

    def test_extract_markdown_no_title(self) -> None:
        """Markdown without heading should use default title."""
        markdown = "Just plain text without any heading."
        result = ContentExtractor.extract_markdown(markdown)

        assert result.title == "Untitled"
        assert "Just plain text" in result.content

    def test_extract_dispatches_by_type(self) -> None:
        """Extract method should dispatch based on content type."""
        html = "<html><head><title>HTML</title></head><body><p>Content</p></body></html>"
        md = "# Markdown\n\nContent here."

        html_result = ContentExtractor.extract(html, "html")
        md_result = ContentExtractor.extract(md, "markdown")

        assert html_result.content_type == "html"
        assert html_result.title == "HTML"
        assert md_result.content_type == "markdown"
        assert md_result.title == "Markdown"


# --- RateLimiter Tests ---


class TestRateLimiter:
    """Tests for RateLimiter."""

    @pytest.mark.asyncio
    async def test_rate_limiter_allows_first_request(self) -> None:
        """First request should not wait."""
        limiter = RateLimiter(requests_per_second=10.0)
        # Should complete quickly without waiting
        await limiter.acquire()

    @pytest.mark.asyncio
    async def test_rate_limiter_enforces_interval(self) -> None:
        """Subsequent requests should be rate limited."""
        limiter = RateLimiter(requests_per_second=100.0)  # Fast for testing

        import time

        start = time.monotonic()
        await limiter.acquire()
        await limiter.acquire()
        elapsed = time.monotonic() - start

        # Should have waited at least one interval (0.01 seconds)
        assert elapsed >= 0.009  # Allow small timing variance


# --- KnowledgeService Tests ---


@pytest.fixture
def mock_session() -> AsyncMock:
    """Create a mock async session."""
    session = AsyncMock(spec=AsyncSession)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def sample_html() -> str:
    """Sample HTML content for testing."""
    return """
    <!DOCTYPE html>
    <html>
    <head><title>Python Best Practices</title></head>
    <body>
        <article>
            <h1>Python Best Practices Guide</h1>
            <p>This guide covers essential practices for writing clean Python code.</p>
            <h2>Type Hints</h2>
            <p>Always use type hints in function signatures.</p>
            <h2>Testing</h2>
            <p>Write tests using pytest framework.</p>
        </article>
    </body>
    </html>
    """


@pytest.fixture
def sample_markdown() -> str:
    """Sample Markdown content for testing."""
    return """# FastAPI Guide

This is a comprehensive guide to FastAPI.

## Getting Started

Install FastAPI with pip:

```bash
pip install fastapi
```

## Creating Routes

Define routes using decorators.

## Testing

Use TestClient for testing.
"""


def _make_mock_response(
    status_code: int,
    content: bytes,
    headers: dict[str, str] | None = None,
) -> MagicMock:
    """Create a mock response object that works with httpx patterns."""
    response = MagicMock()
    response.status_code = status_code
    response.text = content.decode("utf-8") if content else ""
    response.content = content
    response.headers = headers or {}

    def raise_for_status() -> None:
        if status_code >= 400:
            raise httpx.HTTPStatusError(
                message=f"HTTP {status_code}",
                request=MagicMock(),
                response=response,
            )

    response.raise_for_status = raise_for_status
    return response


class TestKnowledgeServiceFetchUrl:
    """Tests for KnowledgeService.fetch_url."""

    @pytest.mark.asyncio
    async def test_fetch_html_content(
        self, mock_session: AsyncMock, sample_html: str
    ) -> None:
        """Fetch and detect HTML content type."""
        mock_response = _make_mock_response(
            200,
            sample_html.encode(),
            headers={"content-type": "text/html; charset=utf-8"},
        )

        service = KnowledgeService(mock_session, rate_limit=1000.0)

        with patch.object(
            service, "_get_http_client", new_callable=AsyncMock
        ) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            content, content_type = await service.fetch_url("https://example.com/article")

        assert "Python Best Practices" in content
        assert content_type == "html"

    @pytest.mark.asyncio
    async def test_fetch_markdown_by_extension(
        self, mock_session: AsyncMock, sample_markdown: str
    ) -> None:
        """Detect markdown from URL extension."""
        mock_response = _make_mock_response(
            200,
            sample_markdown.encode(),
            headers={"content-type": "text/plain"},
        )

        service = KnowledgeService(mock_session, rate_limit=1000.0)

        with patch.object(
            service, "_get_http_client", new_callable=AsyncMock
        ) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            content, content_type = await service.fetch_url("https://example.com/README.md")

        assert "FastAPI Guide" in content
        assert content_type == "markdown"

    @pytest.mark.asyncio
    async def test_fetch_url_http_error(self, mock_session: AsyncMock) -> None:
        """HTTP errors should raise KnowledgeIngestionError."""
        mock_response = _make_mock_response(404, b"Not Found")

        service = KnowledgeService(mock_session, rate_limit=1000.0)

        with patch.object(
            service, "_get_http_client", new_callable=AsyncMock
        ) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            with pytest.raises(KnowledgeIngestionError) as exc_info:
                await service.fetch_url("https://example.com/not-found")

        assert "HTTP 404" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_fetch_url_connection_error(self, mock_session: AsyncMock) -> None:
        """Connection errors should raise KnowledgeIngestionError."""
        service = KnowledgeService(mock_session, rate_limit=1000.0)

        with patch.object(
            service, "_get_http_client", new_callable=AsyncMock
        ) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )
            mock_get_client.return_value = mock_client

            with pytest.raises(KnowledgeIngestionError) as exc_info:
                await service.fetch_url("https://example.com/down")

        assert "Failed to fetch URL" in str(exc_info.value)


class TestKnowledgeServiceSummarize:
    """Tests for KnowledgeService.summarize_content."""

    @pytest.mark.asyncio
    async def test_summarize_parses_response(self, mock_session: AsyncMock) -> None:
        """Summary and tags should be parsed from LLM response."""
        mock_llm_response = """SUMMARY:
This is a comprehensive guide to Python best practices including type hints and testing.

TAGS:
python, best-practices, testing, type-hints"""

        service = KnowledgeService(mock_session, api_key="test-key")

        with patch(
            "jefe.server.services.knowledge.OpenRouterClient"
        ) as mock_client_class:
            mock_client = AsyncMock()
            mock_client.complete = AsyncMock(return_value=mock_llm_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client

            summary, tags = await service.summarize_content("Python best practices content...")

        assert "comprehensive guide" in summary
        assert "python" in tags
        assert "best-practices" in tags
        assert "testing" in tags

    @pytest.mark.asyncio
    async def test_summarize_handles_single_line_format(
        self, mock_session: AsyncMock
    ) -> None:
        """Handle responses where summary/tags are on the same line."""
        mock_llm_response = """SUMMARY: Quick summary here.
TAGS: tag1, tag2, tag3"""

        service = KnowledgeService(mock_session, api_key="test-key")

        with patch(
            "jefe.server.services.knowledge.OpenRouterClient"
        ) as mock_client_class:
            mock_client = AsyncMock()
            mock_client.complete = AsyncMock(return_value=mock_llm_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client

            summary, tags = await service.summarize_content("Content")

        assert summary == "Quick summary here."
        assert tags == ["tag1", "tag2", "tag3"]

    @pytest.mark.asyncio
    async def test_summarize_fallback_on_missing_summary(
        self, mock_session: AsyncMock
    ) -> None:
        """Provide default summary if LLM response is malformed."""
        mock_llm_response = "Some random text without proper format"

        service = KnowledgeService(mock_session, api_key="test-key")

        with patch(
            "jefe.server.services.knowledge.OpenRouterClient"
        ) as mock_client_class:
            mock_client = AsyncMock()
            mock_client.complete = AsyncMock(return_value=mock_llm_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client

            summary, tags = await service.summarize_content("Content")

        assert summary == "Content extracted from URL."
        assert tags == ["uncategorized"]

    @pytest.mark.asyncio
    async def test_summarize_truncates_long_content(
        self, mock_session: AsyncMock
    ) -> None:
        """Long content should be truncated before sending to LLM."""
        long_content = "A" * 10000  # Very long content

        service = KnowledgeService(mock_session, api_key="test-key")

        captured_prompt = None

        async def capture_complete(prompt: str, **kwargs) -> str:
            nonlocal captured_prompt
            captured_prompt = prompt
            return "SUMMARY: Summary.\nTAGS: test"

        with patch(
            "jefe.server.services.knowledge.OpenRouterClient"
        ) as mock_client_class:
            mock_client = AsyncMock()
            mock_client.complete = capture_complete
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client

            await service.summarize_content(long_content)

        assert captured_prompt is not None
        # Content should be truncated (8000 chars max + truncation message)
        assert len(captured_prompt) < 10000
        assert "[Content truncated...]" in captured_prompt

    @pytest.mark.asyncio
    async def test_summarize_llm_error(self, mock_session: AsyncMock) -> None:
        """LLM errors should raise KnowledgeIngestionError."""
        from jefe.server.llm.openrouter import OpenRouterError

        service = KnowledgeService(mock_session, api_key="test-key")

        with patch(
            "jefe.server.services.knowledge.OpenRouterClient"
        ) as mock_client_class:
            # Create the mock that will be returned by __aenter__
            entered_client = AsyncMock()
            entered_client.complete = AsyncMock(
                side_effect=OpenRouterError("API error")
            )

            # Create the context manager mock
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=entered_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_class.return_value = mock_client

            with pytest.raises(KnowledgeIngestionError) as exc_info:
                await service.summarize_content("Content")

        assert "LLM summarization failed" in str(exc_info.value)


class TestKnowledgeServiceIngestUrl:
    """Tests for KnowledgeService.ingest_url."""

    @pytest.mark.asyncio
    async def test_ingest_url_full_pipeline(
        self, mock_session: AsyncMock, sample_html: str
    ) -> None:
        """Full ingestion pipeline creates entry."""
        mock_response = _make_mock_response(
            200,
            sample_html.encode(),
            headers={"content-type": "text/html"},
        )

        mock_llm_response = """SUMMARY:
A guide to Python best practices.

TAGS:
python, best-practices"""

        # Mock repository to return None (no existing entry)
        mock_repo = AsyncMock(spec=KnowledgeRepository)
        mock_repo.get_by_url = AsyncMock(return_value=None)

        service = KnowledgeService(mock_session, api_key="test-key", rate_limit=1000.0)
        service.repository = mock_repo

        with (
            patch.object(
                service, "_get_http_client", new_callable=AsyncMock
            ) as mock_get_client,
            patch(
                "jefe.server.services.knowledge.OpenRouterClient"
            ) as mock_client_class,
        ):
            # Mock HTTP client
            mock_http_client = AsyncMock()
            mock_http_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            # Mock LLM client
            mock_llm_client = AsyncMock()
            mock_llm_client.complete = AsyncMock(return_value=mock_llm_response)
            mock_llm_client.__aenter__ = AsyncMock(return_value=mock_llm_client)
            mock_llm_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_llm_client

            entry = await service.ingest_url("https://example.com/python-guide")

        # Verify entry was created
        assert entry.source_url == "https://example.com/python-guide"
        assert entry.title == "Python Best Practices"
        assert "Python Best Practices Guide" in entry.content
        assert "guide to Python best practices" in entry.summary
        assert entry.get_tags_list() == ["python", "best-practices"]

        # Verify database operations
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_session.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_ingest_url_duplicate_rejected(
        self, mock_session: AsyncMock
    ) -> None:
        """Duplicate URL should raise error."""
        existing_entry = KnowledgeEntry(
            source_url="https://example.com/existing",
            title="Existing",
            content="Content",
            summary="Summary",
        )

        mock_repo = AsyncMock(spec=KnowledgeRepository)
        mock_repo.get_by_url = AsyncMock(return_value=existing_entry)

        service = KnowledgeService(mock_session)
        service.repository = mock_repo

        with pytest.raises(KnowledgeIngestionError) as exc_info:
            await service.ingest_url("https://example.com/existing")

        assert "already exists" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_ingest_url_with_content_type_hint(
        self, mock_session: AsyncMock, sample_markdown: str
    ) -> None:
        """Content type hint overrides detection."""
        mock_response = _make_mock_response(
            200,
            sample_markdown.encode(),
            headers={"content-type": "text/html"},  # Wrong content type
        )

        mock_llm_response = "SUMMARY: FastAPI guide.\nTAGS: fastapi, api"

        mock_repo = AsyncMock(spec=KnowledgeRepository)
        mock_repo.get_by_url = AsyncMock(return_value=None)

        service = KnowledgeService(mock_session, api_key="test-key", rate_limit=1000.0)
        service.repository = mock_repo

        with (
            patch.object(
                service, "_get_http_client", new_callable=AsyncMock
            ) as mock_get_client,
            patch(
                "jefe.server.services.knowledge.OpenRouterClient"
            ) as mock_client_class,
        ):
            mock_http_client = AsyncMock()
            mock_http_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            mock_llm_client = AsyncMock()
            mock_llm_client.complete = AsyncMock(return_value=mock_llm_response)
            mock_llm_client.__aenter__ = AsyncMock(return_value=mock_llm_client)
            mock_llm_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_llm_client

            entry = await service.ingest_url(
                "https://example.com/readme",
                content_type_hint="markdown",
            )

        # Should have been parsed as markdown (title from heading)
        assert entry.title == "FastAPI Guide"


# --- API Integration Tests ---


@pytest.fixture
def client_with_key(tmp_path: Path) -> tuple:
    """Create TestClient with database and API key."""
    from unittest.mock import patch

    from fastapi.testclient import TestClient

    from jefe.server.app import create_app
    from jefe.server.auth import generate_api_key, save_api_key

    db_path = tmp_path / "test_knowledge.db"
    configure_engine(f"sqlite+aiosqlite:///{db_path}")

    key_file = tmp_path / "api_key"
    with patch("jefe.server.auth.get_api_key_file", return_value=key_file):
        api_key = generate_api_key()
        save_api_key(api_key)
        app = create_app()
        with TestClient(app) as client:
            yield client, api_key


class TestKnowledgeAPIIntegration:
    """Integration tests for knowledge API with service."""

    def test_ingest_endpoint_success(self, client_with_key: tuple) -> None:
        """Ingest endpoint creates entry on success."""
        client, api_key = client_with_key

        sample_html = """
        <html>
        <head><title>Test Article</title></head>
        <body><p>Test content for ingestion.</p></body>
        </html>
        """

        mock_response = _make_mock_response(
            200,
            sample_html.encode(),
            headers={"content-type": "text/html"},
        )

        mock_llm_response = "SUMMARY: Test article summary.\nTAGS: testing, api"

        with (
            patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get,
            patch(
                "jefe.server.services.knowledge.OpenRouterClient"
            ) as mock_client_class,
        ):
            mock_get.return_value = mock_response

            mock_llm_client = AsyncMock()
            mock_llm_client.complete = AsyncMock(return_value=mock_llm_response)
            mock_llm_client.__aenter__ = AsyncMock(return_value=mock_llm_client)
            mock_llm_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_llm_client

            response = client.post(
                "/api/knowledge/ingest",
                json={"source_url": "https://example.com/test-article"},
                headers={"X-API-Key": api_key},
            )

        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Test Article"
        assert data["source_url"] == "https://example.com/test-article"
        assert "testing" in data["tags"]

    def test_ingest_endpoint_duplicate_url(self, client_with_key: tuple) -> None:
        """Ingest endpoint returns 400 for duplicate URL."""
        client, api_key = client_with_key

        # First, create an entry directly
        client.post(
            "/api/knowledge",
            json={
                "source_url": "https://example.com/duplicate",
                "title": "Existing",
                "content": "Content",
                "summary": "Summary",
                "tags": [],
            },
            headers={"X-API-Key": api_key},
        )

        # Try to ingest the same URL
        response = client.post(
            "/api/knowledge/ingest",
            json={"source_url": "https://example.com/duplicate"},
            headers={"X-API-Key": api_key},
        )

        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]

    def test_ingest_endpoint_fetch_failure(self, client_with_key: tuple) -> None:
        """Ingest endpoint returns 502 on fetch failure."""
        client, api_key = client_with_key

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.ConnectError("Connection refused")

            response = client.post(
                "/api/knowledge/ingest",
                json={"source_url": "https://unreachable.example.com/article"},
                headers={"X-API-Key": api_key},
            )

        assert response.status_code == 502
        assert "Failed to ingest URL" in response.json()["detail"]
