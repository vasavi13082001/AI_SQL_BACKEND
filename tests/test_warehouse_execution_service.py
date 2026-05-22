"""Tests for warehouse execution service timeout, retries, and dispatching."""

import time

import pytest

from app.schemas.warehouse import WarehouseExecutionRequest, WarehouseType
from app.services.warehouse_execution_service import WarehouseExecutionService


@pytest.mark.asyncio
async def test_execute_query_success_after_retry(monkeypatch):
    service = WarehouseExecutionService()
    request = WarehouseExecutionRequest(
        warehouse=WarehouseType.SNOWFLAKE,
        connection={"account": "a"},
        query="SELECT 1",
        timeout_seconds=1,
        max_retries=2,
        retry_delay_seconds=0,
    )

    call_count = {"value": 0}

    def fake_execute_sync(_request):
        call_count["value"] += 1
        if call_count["value"] == 1:
            raise RuntimeError("transient error")
        return ([{"value": 1}], "query-1")

    monkeypatch.setattr(service, "_execute_sync", fake_execute_sync)

    result = await service.execute_query(request)

    assert result.success is True
    assert result.attempts == 2
    assert result.row_count == 1
    assert result.rows[0]["value"] == 1
    assert result.query_id == "query-1"


@pytest.mark.asyncio
async def test_execute_query_timeout_returns_failed_result(monkeypatch):
    service = WarehouseExecutionService()
    request = WarehouseExecutionRequest(
        warehouse=WarehouseType.REDSHIFT,
        connection={"host": "localhost"},
        query="SELECT pg_sleep(5)",
        timeout_seconds=0.01,
        max_retries=0,
        retry_delay_seconds=0,
    )

    def fake_execute_sync(_request):
        time.sleep(0.05)
        return ([{"value": 1}], None)

    monkeypatch.setattr(service, "_execute_sync", fake_execute_sync)

    result = await service.execute_query(request)

    assert result.success is False
    assert result.timed_out is True
    assert result.attempts == 1
    assert result.row_count == 0
    assert result.rows == []


@pytest.mark.asyncio
async def test_execute_query_exhausts_retries_on_error(monkeypatch):
    service = WarehouseExecutionService()
    request = WarehouseExecutionRequest(
        warehouse=WarehouseType.REDSHIFT,
        connection={"host": "localhost"},
        query="SELECT 1",
        timeout_seconds=1,
        max_retries=2,
        retry_delay_seconds=0,
    )

    def fake_execute_sync(_request):
        raise RuntimeError("connection down")

    monkeypatch.setattr(service, "_execute_sync", fake_execute_sync)

    result = await service.execute_query(request)

    assert result.success is False
    assert result.attempts == 3
    assert result.timed_out is False
    assert "connection down" in (result.error_message or "")


def test_execute_sync_dispatches_snowflake(monkeypatch):
    service = WarehouseExecutionService()

    def fake_snowflake(connection, query):
        assert connection == {"account": "test"}
        assert query == "SELECT 1"
        return ([{"value": 1}], "sfqid")

    monkeypatch.setattr(service, "_execute_snowflake_sync", fake_snowflake)

    result = service._execute_sync(
        WarehouseExecutionRequest(
            warehouse=WarehouseType.SNOWFLAKE,
            connection={"account": "test"},
            query="SELECT 1",
        )
    )

    assert result[0][0]["value"] == 1
    assert result[1] == "sfqid"


def test_execute_sync_dispatches_redshift(monkeypatch):
    service = WarehouseExecutionService()

    def fake_redshift(connection, query):
        assert connection == {"host": "localhost"}
        assert query == "SELECT 1"
        return ([{"value": 1}], None)

    monkeypatch.setattr(service, "_execute_redshift_sync", fake_redshift)

    result = service._execute_sync(
        WarehouseExecutionRequest(
            warehouse=WarehouseType.REDSHIFT,
            connection={"host": "localhost"},
            query="SELECT 1",
        )
    )

    assert result[0][0]["value"] == 1
    assert result[1] is None
