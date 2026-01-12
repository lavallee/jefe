"""Authentication API endpoints."""

from fastapi import APIRouter

from jefe.server.auth import APIKey
from jefe.server.schemas.common import MessageResponse

router = APIRouter()


@router.get("/api/auth/verify", response_model=MessageResponse)
async def verify_api_key(_api_key: APIKey) -> MessageResponse:
    """
    Verify if the provided API key is valid.

    This endpoint requires a valid API key in the X-API-Key header.
    If the key is valid, it returns a success message.
    If the key is invalid or missing, it returns a 401 error.

    Returns:
        Success message confirming the API key is valid.
    """
    return MessageResponse(message="API key is valid")
