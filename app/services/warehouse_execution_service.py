"""Unified async SQL execution service for Snowflake and Redshift."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from logging import getLogger
from time import perf_counter
from typing import Any

from app.schemas.warehouse import (
    WarehouseExecutionRequest,
    WarehouseExecutionResult,
    WarehouseType,
)

logger = getLogger(__name__)


class WarehouseExecutionService:
    """Execute SQL with async timeout, retries, and structured execution logging."""

    async def execute_query(
        self,
        request: WarehouseExecutionRequest,
    ) -> WarehouseExecutionResult:
        """Execute a query on the requested warehouse with retry and timeout controls."""
        started_at = datetime.now(timezone.utc)
        started_perf = perf_counter()
        attempts = 0
        last_error: Exception | None = None
        timed_out = False

        while attempts <= request.max_retries:
            attempts += 1
            try:
                logger.info(
                    "Warehouse execution started: warehouse=%s attempt=%s timeout_seconds=%s",
                    request.warehouse.value,
                    attempts,
                    request.timeout_seconds,
                )
                rows, query_id = await asyncio.wait_for(
                    asyncio.to_thread(self._execute_sync, request),
                    timeout=request.timeout_seconds,
                )
                finished_at = datetime.now(timezone.utc)
                duration_ms = int((perf_counter() - started_perf) * 1000)

                logger.info(
                    "Warehouse execution succeeded: warehouse=%s attempt=%s row_count=%s duration_ms=%s query_id=%s",
                    request.warehouse.value,
                    attempts,
                    len(rows),
                    duration_ms,
                    query_id,
                )
                return WarehouseExecutionResult(
                    warehouse=request.warehouse,
                    query=request.query,
                    success=True,
                    attempts=attempts,
                    started_at=started_at,
                    finished_at=finished_at,
                    duration_ms=duration_ms,
                    timed_out=False,
                    row_count=len(rows),
                    rows=rows,
                    query_id=query_id,
                )
            except asyncio.TimeoutError as exc:
                timed_out = True
                last_error = exc
                logger.warning(
                    "Warehouse execution timed out: warehouse=%s attempt=%s timeout_seconds=%s",
                    request.warehouse.value,
                    attempts,
                    request.timeout_seconds,
                )
            except Exception as exc:  # pragma: no cover - exercised via unit tests
                last_error = exc
                logger.warning(
                    "Warehouse execution failed: warehouse=%s attempt=%s error=%s",
                    request.warehouse.value,
                    attempts,
                    str(exc),
                )

            if attempts <= request.max_retries:
                backoff_seconds = self._compute_backoff(
                    attempts=attempts,
                    base_delay=request.retry_delay_seconds,
                )
                logger.info(
                    "Warehouse execution retry scheduled: warehouse=%s next_attempt=%s backoff_seconds=%.2f",
                    request.warehouse.value,
                    attempts + 1,
                    backoff_seconds,
                )
                await asyncio.sleep(backoff_seconds)

        finished_at = datetime.now(timezone.utc)
        duration_ms = int((perf_counter() - started_perf) * 1000)
        error_message = str(last_error) if last_error else "Query execution failed"
        logger.error(
            "Warehouse execution exhausted retries: warehouse=%s attempts=%s timed_out=%s error=%s",
            request.warehouse.value,
            attempts,
            timed_out,
            error_message,
        )
        return WarehouseExecutionResult(
            warehouse=request.warehouse,
            query=request.query,
            success=False,
            attempts=attempts,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=duration_ms,
            timed_out=timed_out,
            row_count=0,
            rows=[],
            error_message=error_message,
        )

    @staticmethod
    def _compute_backoff(attempts: int, base_delay: float) -> float:
        """Compute exponential backoff delay for retries."""
        return min(base_delay * (2 ** (attempts - 1)), 30.0)

    def _execute_sync(self, request: WarehouseExecutionRequest) -> tuple[list[dict[str, Any]], str | None]:
        """Dispatch sync query execution to warehouse-specific implementation."""
        if request.warehouse == WarehouseType.SNOWFLAKE:
            return self._execute_snowflake_sync(request.connection, request.query)
        if request.warehouse == WarehouseType.REDSHIFT:
            return self._execute_redshift_sync(request.connection, request.query)
        raise ValueError(f"Unsupported warehouse type: {request.warehouse}")

    def _execute_snowflake_sync(
        self,
        connection: dict[str, Any],
        query: str,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """Execute SQL against Snowflake using DictCursor rows."""
        try:
            import snowflake.connector
        except ImportError as exc:
            raise RuntimeError(
                "snowflake-connector-python is not installed. Add it to dependencies."
            ) from exc

        with snowflake.connector.connect(**connection) as conn:
            with conn.cursor(snowflake.connector.DictCursor) as cursor:
                cursor.execute(query)
                rows: list[dict[str, Any]] = [dict(row) for row in (cursor.fetchall() or [])]
                query_id = getattr(cursor, "sfqid", None)
                return rows, query_id

    def _execute_redshift_sync(
        self,
        connection: dict[str, Any],
        query: str,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """Execute SQL against Redshift through psycopg2 RealDictCursor."""
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor
        except ImportError as exc:
            raise RuntimeError("psycopg2-binary is not installed. Add it to dependencies.") from exc

        with psycopg2.connect(**connection) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query)
                rows: list[dict[str, Any]] = [dict(row) for row in (cursor.fetchall() or [])]
                return rows, None
