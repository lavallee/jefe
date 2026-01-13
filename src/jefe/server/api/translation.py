"""Translation API endpoints."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from jefe.data.database import get_session
from jefe.data.models.translation_log import TranslationLog, TranslationType
from jefe.server.auth import APIKey
from jefe.server.schemas.common import MessageResponse
from jefe.server.schemas.translation import (
    ApplyTranslationRequest,
    TranslateRequest,
    TranslateResponse,
    TranslationLogResponse,
)
from jefe.server.services.translation.service import TranslationService
from jefe.server.services.translation.syntax import TranslationError

router = APIRouter()


def _log_to_response(log: TranslationLog) -> TranslationLogResponse:
    """Convert TranslationLog to response schema."""
    return TranslationLogResponse(
        id=log.id,
        input_text=log.input_text,
        output_text=log.output_text,
        translation_type=log.translation_type,
        model_name=log.model_name,
        project_id=log.project_id,
        created_at=log.created_at,
    )


@router.post("/api/translate", response_model=TranslateResponse)
async def translate_content(
    payload: TranslateRequest,
    _api_key: APIKey,
    session: AsyncSession = Depends(get_session),
) -> TranslateResponse:
    """Translate content between harness formats."""
    service = TranslationService(session)

    try:
        # Validate harness names before calling service
        # The service will perform additional validation and normalization
        result = await service.translate(
            content=payload.content,
            source_harness=payload.source_harness,  # type: ignore[arg-type]
            target_harness=payload.target_harness,  # type: ignore[arg-type]
            config_kind=payload.config_kind,
            project_id=payload.project_id,
        )
        return TranslateResponse(
            output=result.output,
            diff=result.diff,
            log_id=result.log_id,
        )
    except TranslationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Translation failed: {e}") from e


@router.get("/api/translate/log", response_model=list[TranslationLogResponse])
async def get_translation_history(
    _api_key: APIKey,
    session: AsyncSession = Depends(get_session),
    project_id: int | None = Query(None, description="Filter by project ID"),
    translation_type: TranslationType | None = Query(  # noqa: B008
        None, description="Filter by translation type"
    ),
    limit: int | None = Query(None, description="Maximum number of logs to return"),
    offset: int = Query(0, description="Number of logs to skip"),
) -> list[TranslationLogResponse]:
    """Get translation history with optional filters."""
    service = TranslationService(session)

    logs = await service.get_history(
        project_id=project_id,
        translation_type=translation_type,
        limit=limit,
        offset=offset,
    )

    return [_log_to_response(log) for log in logs]


@router.post("/api/translate/apply", response_model=MessageResponse)
async def apply_translation(
    payload: ApplyTranslationRequest,
    _api_key: APIKey,
    session: AsyncSession = Depends(get_session),
) -> MessageResponse:
    """Apply translated content to a file."""
    service = TranslationService(session)

    try:
        file_path = Path(payload.file_path).expanduser()
        await service.apply_translation(
            file_path=file_path,
            content=payload.content,
        )
        return MessageResponse(message=f"Translation applied to {file_path}")
    except TranslationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to apply translation: {e}") from e
