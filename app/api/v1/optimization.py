"""API endpoints for SQL optimization."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.models import User
from app.schemas.optimization import SQLOptimizationRequest, SQLOptimizationResponse
from app.schemas.user import UserRole
from app.services.auth_service import require_roles
from app.services.sql_optimization_engine import SQLOptimizationEngine

router = APIRouter(prefix="/optimize", tags=["SQL Optimization"])

_engine = SQLOptimizationEngine()


@router.post(
    "/sql",
    response_model=SQLOptimizationResponse,
    summary="Optimize a SQL query for Snowflake or Redshift",
    description=(
        "Analyzes and rewrites a SQL query according to the performance best practices "
        "of the chosen dialect (Snowflake or Redshift). Returns the optimized SQL, "
        "a list of rules triggered, and counts of rewrites and remaining warnings."
    ),
    status_code=status.HTTP_200_OK,
)
def optimize_sql(
    request: SQLOptimizationRequest,
    _current_user: User = Depends(
        require_roles(UserRole.ANALYST, UserRole.DATA_ENGINEER, UserRole.ADMIN)
    ),
) -> SQLOptimizationResponse:
    """Optimize SQL for the requested dialect."""
    try:
        return _engine.optimize(request)
    except Exception as exc:  # pragma: no cover
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
