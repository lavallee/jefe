"""Tests for OpenRouter client."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from httpx import Response

from jefe.server.llm.openrouter import (
    OpenRouterAuthenticationError,
    OpenRouterClient,
    OpenRouterError,
    OpenRouterRateLimitError,
)


@pytest.fixture
def mock_api_key() -> str:
    """Provide a test API key."""
    return "test-api-key-123"


@pytest.fixture
def client(mock_api_key: str) -> OpenRouterClient:
    """Create an OpenRouter client for testing."""
    return OpenRouterClient(api_key=mock_api_key)


@pytest.fixture
def mock_response() -> dict[str, object]:
    """Create a mock API response."""
    return {
        "id": "gen-123",
        "model": "anthropic/claude-3-haiku",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "This is a test completion response.",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
    }


class TestOpenRouterClient:
    """Test OpenRouterClient initialization and configuration."""

    def test_init_with_api_key(self, mock_api_key: str) -> None:
        """Test initialization with explicit API key."""
        client = OpenRouterClient(api_key=mock_api_key)
        assert client.api_key == mock_api_key
        assert client.model == OpenRouterClient.DEFAULT_MODEL
        assert client.base_url == OpenRouterClient.BASE_URL

    def test_init_with_env_var(self, mock_api_key: str) -> None:
        """Test initialization with API key from environment."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": mock_api_key}):
            client = OpenRouterClient()
            assert client.api_key == mock_api_key

    def test_init_without_api_key(self) -> None:
        """Test initialization fails without API key."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(
                OpenRouterAuthenticationError, match="API key is required"
            ):
                OpenRouterClient()

    def test_init_with_custom_model(self, mock_api_key: str) -> None:
        """Test initialization with custom model."""
        custom_model = "anthropic/claude-3-opus"
        client = OpenRouterClient(api_key=mock_api_key, model=custom_model)
        assert client.model == custom_model

    def test_init_with_custom_timeout(self, mock_api_key: str) -> None:
        """Test initialization with custom timeout."""
        client = OpenRouterClient(api_key=mock_api_key, timeout=60.0)
        assert client.timeout == 60.0

    def test_init_with_custom_base_url(self, mock_api_key: str) -> None:
        """Test initialization with custom base URL."""
        custom_url = "https://custom.openrouter.ai/api/v1"
        client = OpenRouterClient(api_key=mock_api_key, base_url=custom_url)
        assert client.base_url == custom_url


class TestComplete:
    """Test completion generation."""

    @pytest.mark.asyncio
    async def test_complete_success(
        self, client: OpenRouterClient, mock_response: dict[str, object]
    ) -> None:
        """Test successful completion request."""
        mock_post = AsyncMock(
            return_value=Response(
                status_code=200,
                json=mock_response,
                request=httpx.Request("POST", "https://openrouter.ai/api/v1"),
            )
        )

        with patch.object(client._client, "post", mock_post):
            result = await client.complete("Hello, world!")
            assert result == "This is a test completion response."
            mock_post.assert_called_once()

            call_kwargs = mock_post.call_args[1]
            assert call_kwargs["json"]["model"] == client.model
            assert call_kwargs["json"]["messages"][0]["content"] == "Hello, world!"

    @pytest.mark.asyncio
    async def test_complete_with_custom_model(
        self, client: OpenRouterClient, mock_response: dict[str, object]
    ) -> None:
        """Test completion with custom model override."""
        mock_post = AsyncMock(
            return_value=Response(
                status_code=200,
                json=mock_response,
                request=httpx.Request("POST", "https://openrouter.ai/api/v1"),
            )
        )

        custom_model = "anthropic/claude-3-sonnet"
        with patch.object(client._client, "post", mock_post):
            await client.complete("Test prompt", model=custom_model)

            call_kwargs = mock_post.call_args[1]
            assert call_kwargs["json"]["model"] == custom_model

    @pytest.mark.asyncio
    async def test_complete_with_parameters(
        self, client: OpenRouterClient, mock_response: dict[str, object]
    ) -> None:
        """Test completion with custom parameters."""
        mock_post = AsyncMock(
            return_value=Response(
                status_code=200,
                json=mock_response,
                request=httpx.Request("POST", "https://openrouter.ai/api/v1"),
            )
        )

        with patch.object(client._client, "post", mock_post):
            await client.complete(
                "Test prompt", max_tokens=2048, temperature=0.5, top_p=0.9
            )

            call_kwargs = mock_post.call_args[1]
            payload = call_kwargs["json"]
            assert payload["max_tokens"] == 2048
            assert payload["temperature"] == 0.5
            assert payload["top_p"] == 0.9


class TestErrorHandling:
    """Test error handling for various API failures."""

    @pytest.mark.asyncio
    async def test_rate_limit_error(self, client: OpenRouterClient) -> None:
        """Test rate limit error handling."""
        mock_response = Response(
            status_code=429,
            json={"error": "Rate limit exceeded"},
            request=httpx.Request("POST", "https://openrouter.ai/api/v1"),
        )

        mock_post = AsyncMock(side_effect=httpx.HTTPStatusError("", request=httpx.Request("POST", ""), response=mock_response))

        with patch.object(client._client, "post", mock_post):
            with pytest.raises(OpenRouterRateLimitError, match="Rate limit exceeded"):
                await client.complete("Test prompt")

    @pytest.mark.asyncio
    async def test_authentication_error(self, client: OpenRouterClient) -> None:
        """Test authentication error handling."""
        mock_response = Response(
            status_code=401,
            json={"error": "Invalid API key"},
            request=httpx.Request("POST", "https://openrouter.ai/api/v1"),
        )

        mock_post = AsyncMock(side_effect=httpx.HTTPStatusError("", request=httpx.Request("POST", ""), response=mock_response))

        with patch.object(client._client, "post", mock_post):
            with pytest.raises(
                OpenRouterAuthenticationError, match="Authentication failed"
            ):
                await client.complete("Test prompt")

    @pytest.mark.asyncio
    async def test_general_http_error(self, client: OpenRouterClient) -> None:
        """Test general HTTP error handling."""
        mock_response = Response(
            status_code=500,
            json={"error": "Internal server error"},
            request=httpx.Request("POST", "https://openrouter.ai/api/v1"),
        )

        mock_post = AsyncMock(side_effect=httpx.HTTPStatusError("", request=httpx.Request("POST", ""), response=mock_response))

        with patch.object(client._client, "post", mock_post):
            with pytest.raises(OpenRouterError, match="API error"):
                await client.complete("Test prompt")

    @pytest.mark.asyncio
    async def test_request_error(self, client: OpenRouterClient) -> None:
        """Test network request error handling."""
        mock_post = AsyncMock(
            side_effect=httpx.RequestError("Connection failed", request=httpx.Request("POST", ""))
        )

        with patch.object(client._client, "post", mock_post):
            with pytest.raises(OpenRouterError, match="Request failed"):
                await client.complete("Test prompt")


class TestContextManager:
    """Test async context manager functionality."""

    @pytest.mark.asyncio
    async def test_context_manager(self, mock_api_key: str) -> None:
        """Test using client as async context manager."""
        async with OpenRouterClient(api_key=mock_api_key) as client:
            assert client.api_key == mock_api_key

    @pytest.mark.asyncio
    async def test_close(self, client: OpenRouterClient) -> None:
        """Test closing the client."""
        mock_aclose = AsyncMock()
        with patch.object(client._client, "aclose", mock_aclose):
            await client.close()
            mock_aclose.assert_called_once()


class TestEnvironmentVariables:
    """Test environment variable handling."""

    def test_api_key_from_env(self) -> None:
        """Test API key is read from environment variable."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "env-key-123"}):
            client = OpenRouterClient()
            assert client.api_key == "env-key-123"

    def test_explicit_api_key_overrides_env(self) -> None:
        """Test explicit API key overrides environment variable."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "env-key-123"}):
            client = OpenRouterClient(api_key="explicit-key-456")
            assert client.api_key == "explicit-key-456"
