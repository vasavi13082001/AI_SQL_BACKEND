"""Snowflake API endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from logging import getLogger

from app.models import User
from app.schemas.snowflake import (
    SnowflakeConnectionRequest,
    SnowflakeMetadataResponse,
    SnowflakeSQLGenerationRequest,
    SnowflakeSQLGenerationResponse,
)
from app.services.snowflake_service import SnowflakeMetadataService
from app.services.snowflake_sql_service import (
    SQLValidationError,
    SnowflakeSQLGenerationService,
)
from app.schemas.user import UserRole
from app.services.auth_service import require_roles

logger = getLogger(__name__)

router = APIRouter(prefix="/snowflake", tags=["snowflake"])


@router.post("/extract", response_model=SnowflakeMetadataResponse)
async def extract_snowflake_metadata(
    request: SnowflakeConnectionRequest,
    current_user: User = Depends(require_roles(UserRole.DATA_ENGINEER, UserRole.ADMIN)),
):
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


@router.post("/generate-sql", response_model=SnowflakeSQLGenerationResponse)
async def generate_snowflake_sql(
    request: SnowflakeSQLGenerationRequest,
    current_user: User = Depends(require_roles(UserRole.DATA_ENGINEER, UserRole.ADMIN)),
):
    """Generate optimized and validated Snowflake SQL from natural language."""
    try:
        service = SnowflakeSQLGenerationService()
        return service.generate_sql(request)
    except SQLValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        logger.error(f"SQL generation configuration/dependency error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.exception("Snowflake SQL generation failed")
        raise HTTPException(
            status_code=400,
            detail=f"Failed to generate Snowflake SQL: {exc}",
        ) from exc
