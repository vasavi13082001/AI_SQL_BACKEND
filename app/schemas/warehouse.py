"""Pydantic schemas for cross-warehouse SQL execution."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class WarehouseType(str, Enum):
    """Supported warehouse engines for SQL execution."""

    SNOWFLAKE = "snowflake"
    REDSHIFT = "redshift"


class WarehouseExecutionRequest(BaseModel):
    """Execution request for a warehouse query."""

    warehouse: WarehouseType = Field(..., description="Target warehouse engine")
    connection: dict[str, Any] = Field(
        ...,
        description="Warehouse connection settings",
    )
    query: str = Field(..., min_length=1, description="SQL query to execute")
    timeout_seconds: float = Field(
        default=30.0,
        gt=0,
        le=300,
        description="Max seconds to wait for each execution attempt",
    )
    max_retries: int = Field(
        default=2,
        ge=0,
        le=10,
        description="Retry count after the initial failed attempt",
    )
    retry_delay_seconds: float = Field(
        default=1.0,
        ge=0,
        le=30,
        description="Base delay used for exponential retry backoff",
    )


class WarehouseExecutionResult(BaseModel):
    """Execution result payload with retries and timing metadata."""

    warehouse: WarehouseType
    query: str
    success: bool
    attempts: int
    started_at: datetime
    finished_at: datetime
    duration_ms: int
    timed_out: bool
    row_count: int
    rows: list[dict[str, Any]]
    query_id: str | None = None
    error_message: str | None = None
