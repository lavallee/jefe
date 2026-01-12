"""Authentication utilities and dependencies for the FastAPI server."""

import hashlib
import secrets
from pathlib import Path
from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader

# API Key header configuration
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def get_api_key_file() -> Path:
    """
    Get the path to the API key storage file.

    Returns:
        Path to the API key file in the project root.
    """
    # Store API key in project root as .station_chief_api_key
    return Path.home() / ".station_chief" / "api_key"


def _hash_key(key: str) -> str:
    """
    Hash an API key using SHA-256.

    Args:
        key: The plain API key to hash.

    Returns:
        The hexadecimal digest of the hashed key.
    """
    return hashlib.sha256(key.encode()).hexdigest()


def generate_api_key() -> str:
    """
    Generate a new random API key.

    Returns:
        A URL-safe random token (32 bytes).
    """
    return secrets.token_urlsafe(32)


def save_api_key(key: str) -> None:
    """
    Save API key (hashed) to storage file.

    Args:
        key: The plain API key to save (will be hashed before storage).
    """
    key_file = get_api_key_file()
    key_file.parent.mkdir(parents=True, exist_ok=True)

    hashed = _hash_key(key)
    key_file.write_text(hashed)
    key_file.chmod(0o600)  # Read/write for owner only


def load_api_key_hash() -> str | None:
    """
    Load the hashed API key from storage.

    Returns:
        The hashed API key, or None if not found.
    """
    key_file = get_api_key_file()
    if not key_file.exists():
        return None
    return key_file.read_text().strip()


def verify_api_key(key: str) -> bool:
    """
    Verify if the provided API key is valid.

    Args:
        key: The API key to verify.

    Returns:
        True if the key is valid, False otherwise.
    """
    stored_hash = load_api_key_hash()
    if stored_hash is None:
        return False

    provided_hash = _hash_key(key)
    return secrets.compare_digest(stored_hash, provided_hash)


def ensure_api_key_exists() -> str | None:
    """
    Ensure an API key exists. Generate one if it doesn't.

    Returns:
        The plain API key if newly generated, None if one already exists.
    """
    if load_api_key_hash() is not None:
        return None

    # Generate new key
    new_key = generate_api_key()
    save_api_key(new_key)
    return new_key


async def require_api_key(
    api_key: Annotated[str | None, Security(api_key_header)]
) -> str:
    """
    FastAPI dependency that requires a valid API key.

    Args:
        api_key: The API key from the X-API-Key header.

    Returns:
        The validated API key.

    Raises:
        HTTPException: 401 if the API key is missing or invalid.
    """
    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key is required. Provide it in the X-API-Key header.",
        )

    if not verify_api_key(api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key.",
        )

    return api_key


# Type alias for dependency injection
APIKey = Annotated[str, Depends(require_api_key)]
