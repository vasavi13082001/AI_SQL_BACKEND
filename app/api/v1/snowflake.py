"""Snowflake API endpoints."""
from fastapi import APIRouter, HTTPException
from logging import getLogger

from app.schemas.snowflake import SnowflakeConnectionRequest, SnowflakeMetadataResponse
from app.services.snowflake_service import SnowflakeMetadataService

logger = getLogger(__name__)

router = APIRouter(prefix="/snowflake", tags=["snowflake"])


@router.post("/extract", response_model=SnowflakeMetadataResponse)
async def extract_snowflake_metadata(request: SnowflakeConnectionRequest):
    """Extract schemas, tables, columns, and relationships from Snowflake."""
    try:
        return SnowflakeMetadataService.extract_metadata(request)
    except RuntimeError as exc:
        logger.error(f"Snowflake dependency/configuration error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.exception("Snowflake metadata extraction failed")
        raise HTTPException(
            status_code=400,
            detail=f"Failed to extract Snowflake metadata: {exc}",
        ) from exc
