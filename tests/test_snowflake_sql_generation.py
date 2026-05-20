"""Tests for Snowflake SQL generation and validation rules."""

import pytest

from app.schemas.snowflake import (
    ColumnMetadata,
    RelationshipMetadata,
    SchemaMetadata,
    SnowflakeMetadataResponse,
    SnowflakeSQLGenerationRequest,
    TableMetadata,
)
from app.services.snowflake_sql_service import (
    SQLValidationError,
    SnowflakeSQLGenerationService,
)


def _build_metadata() -> SnowflakeMetadataResponse:
    return SnowflakeMetadataResponse(
        database="ANALYTICS_DB",
        extracted_at="2026-05-20T00:00:00Z",
        schemas=[
            SchemaMetadata(
                name="PUBLIC",
                tables=[
                    TableMetadata(
                        name="ORDERS",
                        table_type="BASE TABLE",
                        columns=[
                            ColumnMetadata(
                                name="ORDER_ID",
                                data_type="NUMBER",
                                is_nullable=False,
                                default=None,
                                ordinal_position=1,
                            ),
                            ColumnMetadata(
                                name="CUSTOMER_ID",
                                data_type="NUMBER",
                                is_nullable=False,
                                default=None,
                                ordinal_position=2,
                            ),
                        ],
                    )
                ],
            )
        ],
        relationships=[
            RelationshipMetadata(
                constraint_name="FK_ORDERS_CUSTOMER",
                source_schema="PUBLIC",
                source_table="ORDERS",
                source_column="CUSTOMER_ID",
                target_schema="PUBLIC",
                target_table="CUSTOMERS",
                target_column="ID",
            )
        ],
    )


def test_generate_sql_adds_limit_when_missing(monkeypatch):
    metadata = _build_metadata()
    request = SnowflakeSQLGenerationRequest(
        prompt="show order ids",
        metadata=metadata,
        enforce_limit=True,
        max_rows=500,
        temperature=0.0,
    )

    service = SnowflakeSQLGenerationService(client=object(), model="test-model")
    monkeypatch.setattr(
        service,
        "_invoke_llm",
        lambda system_prompt, user_prompt, temperature: "SELECT ORDER_ID FROM PUBLIC.ORDERS",
    )

    result = service.generate_sql(request)

    assert result.validation_passed is True
    assert result.model == "test-model"
    assert "LIMIT 500" in result.sql


def test_validate_sql_rejects_non_select_statement():
    service = SnowflakeSQLGenerationService(client=object(), model="test-model")
    metadata = _build_metadata()

    with pytest.raises(SQLValidationError, match="Only SELECT queries are permitted"):
        service.validate_sql(
            sql="DELETE FROM PUBLIC.ORDERS",
            metadata=metadata,
            enforce_limit=True,
            max_rows=1000,
        )


def test_validate_sql_rejects_unknown_table_reference():
    service = SnowflakeSQLGenerationService(client=object(), model="test-model")
    metadata = _build_metadata()

    with pytest.raises(SQLValidationError, match="unknown table"):
        service.validate_sql(
            sql="SELECT ORDER_ID FROM PUBLIC.UNKNOWN_ORDERS",
            metadata=metadata,
            enforce_limit=False,
            max_rows=1000,
        )


def test_validate_sql_rejects_unknown_qualified_column_reference():
    service = SnowflakeSQLGenerationService(client=object(), model="test-model")
    metadata = _build_metadata()

    with pytest.raises(SQLValidationError, match="unknown column"):
        service.validate_sql(
            sql="SELECT o.BAD_COLUMN FROM PUBLIC.ORDERS o",
            metadata=metadata,
            enforce_limit=False,
            max_rows=1000,
        )


def test_validate_sql_rejects_implicit_cross_join():
    service = SnowflakeSQLGenerationService(client=object(), model="test-model")
    metadata = _build_metadata()

    with pytest.raises(SQLValidationError, match="cross-join"):
        service.validate_sql(
            sql="SELECT ORDER_ID FROM PUBLIC.ORDERS, PUBLIC.ORDERS",
            metadata=metadata,
            enforce_limit=False,
            max_rows=1000,
        )


def test_validate_sql_caps_oversized_limit():
    service = SnowflakeSQLGenerationService(client=object(), model="test-model")
    metadata = _build_metadata()

    result = service.validate_sql(
        sql="SELECT ORDER_ID FROM PUBLIC.ORDERS LIMIT 9999",
        metadata=metadata,
        enforce_limit=True,
        max_rows=500,
    )

    assert "LIMIT 500" in result
    assert "LIMIT 9999" not in result


def test_validate_sql_keeps_limit_within_cap():
    service = SnowflakeSQLGenerationService(client=object(), model="test-model")
    metadata = _build_metadata()

    result = service.validate_sql(
        sql="SELECT ORDER_ID FROM PUBLIC.ORDERS LIMIT 100",
        metadata=metadata,
        enforce_limit=True,
        max_rows=500,
    )

    assert "LIMIT 100" in result


def test_system_prompt_includes_nullability(monkeypatch):
    metadata = _build_metadata()
    service = SnowflakeSQLGenerationService(client=object(), model="test-model")
    captured: dict = {}

    def fake_invoke(system_prompt: str, user_prompt: str, temperature: float) -> str:
        captured["system"] = system_prompt
        captured["user"] = user_prompt
        return "SELECT ORDER_ID FROM PUBLIC.ORDERS"

    monkeypatch.setattr(service, "_invoke_llm", fake_invoke)
    service.generate_sql(
        SnowflakeSQLGenerationRequest(
            prompt="list orders",
            metadata=metadata,
            enforce_limit=False,
            max_rows=1000,
            temperature=0.0,
        )
    )

    assert "NOT NULL" in captured["system"]
    assert "ILIKE" in captured["system"]
    assert "DATE_TRUNC" in captured["system"]
    assert "QUALIFY" in captured["system"]
    assert metadata.database in captured["system"]


def test_user_prompt_includes_limit_instruction(monkeypatch):
    metadata = _build_metadata()
    service = SnowflakeSQLGenerationService(client=object(), model="test-model")
    captured: dict = {}

    def fake_invoke(system_prompt: str, user_prompt: str, temperature: float) -> str:
        captured["user"] = user_prompt
        return "SELECT ORDER_ID FROM PUBLIC.ORDERS"

    monkeypatch.setattr(service, "_invoke_llm", fake_invoke)
    service.generate_sql(
        SnowflakeSQLGenerationRequest(
            prompt="list orders",
            metadata=metadata,
            enforce_limit=True,
            max_rows=250,
            temperature=0.0,
        )
    )

    assert "250" in captured["user"]


def test_generate_sql_optimization_notes_include_snowflake_rules(monkeypatch):
    metadata = _build_metadata()
    service = SnowflakeSQLGenerationService(client=object(), model="test-model")

    monkeypatch.setattr(
        service,
        "_invoke_llm",
        lambda system_prompt, user_prompt, temperature: "SELECT ORDER_ID FROM PUBLIC.ORDERS",
    )

    result = service.generate_sql(
        SnowflakeSQLGenerationRequest(
            prompt="list orders",
            metadata=metadata,
            enforce_limit=True,
            max_rows=1000,
            temperature=0.0,
        )
    )

    notes_text = " ".join(result.optimization_notes)
    assert "cross-join" in notes_text.lower()
    assert "nullability" in notes_text.lower()
    assert "LIMIT 1000" in notes_text
