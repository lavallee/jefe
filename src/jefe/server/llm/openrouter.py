"""OpenRouter API client for LLM completions."""

from __future__ import annotations

import os
from typing import Any

import httpx


class OpenRouterError(Exception):
    """Base exception for OpenRouter errors."""

    pass


class OpenRouterRateLimitError(OpenRouterError):
    """Rate limit exceeded."""

    pass


class OpenRouterAuthenticationError(OpenRouterError):
    """Authentication failed."""

    pass


class OpenRouterClient:
    """Client for interacting with OpenRouter API."""

    BASE_URL = "https://openrouter.ai/api/v1"
    DEFAULT_MODEL = "anthropic/claude-3-haiku"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float = 30.0,
        base_url: str | None = None,
    ) -> None:
        """
        Initialize OpenRouter client.

        Args:
            api_key: OpenRouter API key. Falls back to OPENROUTER_API_KEY env var.
            model: Model to use for completions. Defaults to claude-3-haiku.
            timeout: Request timeout in seconds. Defaults to 30.0.
            base_url: Base URL for OpenRouter API. Defaults to production URL.

        Raises:
            OpenRouterAuthenticationError: If no API key is provided or found.
        """
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise OpenRouterAuthenticationError(
                "OpenRouter API key is required. Set OPENROUTER_API_KEY environment variable "
                "or pass api_key parameter."
            )

        self.model = model or self.DEFAULT_MODEL
        self.base_url = base_url or self.BASE_URL
        self.timeout = timeout
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )

    async def complete(
        self,
        prompt: str,
        *,
        model: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> str:
        """
        Generate a text completion.

        Args:
            prompt: The prompt text to complete.
            model: Override the default model for this request.
            max_tokens: Maximum number of tokens to generate.
            temperature: Sampling temperature (0.0 to 2.0).
            **kwargs: Additional parameters to pass to the API.

        Returns:
            The generated completion text.

        Raises:
            OpenRouterRateLimitError: If rate limit is exceeded.
            OpenRouterAuthenticationError: If authentication fails.
            OpenRouterError: For other API errors.
        """
        payload = {
            "model": model or self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
            **kwargs,
        }

        try:
            response = await self._client.post("/chat/completions", json=payload)
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            content: str = data["choices"][0]["message"]["content"]
            return content
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                raise OpenRouterRateLimitError(
                    f"Rate limit exceeded: {e.response.text}"
                ) from e
            elif e.response.status_code == 401:
                raise OpenRouterAuthenticationError(
                    f"Authentication failed: {e.response.text}"
                ) from e
            else:
                raise OpenRouterError(
                    f"API error ({e.response.status_code}): {e.response.text}"
                ) from e
        except httpx.RequestError as e:
            raise OpenRouterError(f"Request failed: {e!s}") from e

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> OpenRouterClient:
        """Async context manager entry."""
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Async context manager exit."""
        await self.close()
