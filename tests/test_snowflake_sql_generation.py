"""Tests for Snowflake SQL generation and validation rules."""

import pytest

from app.schemas.snowflake import (
    ColumnMetadata,
    ConversationTurn,
    RelationshipMetadata,
    SchemaMetadata,
    SnowflakeMetadataResponse,
    SnowflakeSQLGenerationRequest,
    TableMetadata,
)
from app.schemas.warehouse import WarehouseType
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
                    ),
                    TableMetadata(
                        name="CUSTOMERS",
                        table_type="BASE TABLE",
                        columns=[
                            ColumnMetadata(
                                name="ID",
                                data_type="NUMBER",
                                is_nullable=False,
                                default=None,
                                ordinal_position=1,
                            ),
                            ColumnMetadata(
                                name="CUSTOMER_NAME",
                                data_type="VARCHAR",
                                is_nullable=True,
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


def test_validate_sql_accepts_join_matching_relationship():
    service = SnowflakeSQLGenerationService(client=object(), model="test-model")
    metadata = _build_metadata()

    result = service.validate_sql(
        sql=(
            "SELECT o.ORDER_ID, c.CUSTOMER_NAME "
            "FROM PUBLIC.ORDERS o "
            "JOIN PUBLIC.CUSTOMERS c ON o.CUSTOMER_ID = c.ID"
        ),
        metadata=metadata,
        enforce_limit=False,
        max_rows=1000,
    )

    assert "JOIN PUBLIC.CUSTOMERS" in result


def test_validate_sql_rejects_join_not_matching_relationship():
    service = SnowflakeSQLGenerationService(client=object(), model="test-model")
    metadata = _build_metadata()

    with pytest.raises(SQLValidationError, match="does not match any known table relationship"):
        service.validate_sql(
            sql=(
                "SELECT o.ORDER_ID, c.CUSTOMER_NAME "
                "FROM PUBLIC.ORDERS o "
                "JOIN PUBLIC.CUSTOMERS c ON o.ORDER_ID = c.ID"
            ),
            metadata=metadata,
            enforce_limit=False,
            max_rows=1000,
        )


def test_validate_sql_rejects_cross_join_keyword():
    service = SnowflakeSQLGenerationService(client=object(), model="test-model")
    metadata = _build_metadata()

    with pytest.raises(SQLValidationError, match="CROSS JOIN"):
        service.validate_sql(
            sql="SELECT o.ORDER_ID FROM PUBLIC.ORDERS o CROSS JOIN PUBLIC.CUSTOMERS c",
            metadata=metadata,
            enforce_limit=False,
            max_rows=1000,
        )


def test_validate_sql_rejects_disallowed_operation_keyword():
    service = SnowflakeSQLGenerationService(client=object(), model="test-model")
    metadata = _build_metadata()

    with pytest.raises(SQLValidationError, match="disallowed operation keywords"):
        service.validate_sql(
            sql="SELECT ORDER_ID FROM PUBLIC.ORDERS EXECUTE IMMEDIATE 'DROP TABLE X'",
            metadata=metadata,
            enforce_limit=False,
            max_rows=1000,
        )


def test_validate_sql_rejects_multiple_statements():
    service = SnowflakeSQLGenerationService(client=object(), model="test-model")
    metadata = _build_metadata()

    with pytest.raises(SQLValidationError, match="single SQL statement"):
        service.validate_sql(
            sql="SELECT ORDER_ID FROM PUBLIC.ORDERS; SELECT ID FROM PUBLIC.CUSTOMERS",
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
    assert "relationship" in notes_text.lower()
    assert "nullability" in notes_text.lower()
    assert "LIMIT 1000" in notes_text


def test_user_prompt_includes_conversation_context(monkeypatch):
    metadata = _build_metadata()
    service = SnowflakeSQLGenerationService(client=object(), model="test-model")
    captured: dict = {}

    def fake_invoke(system_prompt: str, user_prompt: str, temperature: float) -> str:
        captured["user"] = user_prompt
        return "SELECT ORDER_ID FROM PUBLIC.ORDERS"

    monkeypatch.setattr(service, "_invoke_llm", fake_invoke)
    service.generate_sql(
        SnowflakeSQLGenerationRequest(
            prompt="Do the same for west",
            metadata=metadata,
            conversation_history=[
                ConversationTurn(role="user", message="Show total revenue by region last 30 days"),
                ConversationTurn(role="assistant", message="SELECT ..."),
            ],
            enforce_limit=True,
            max_rows=250,
            temperature=0.0,
        )
    )

    assert "Conversation context" in captured["user"]
    assert "Show total revenue by region last 30 days" in captured["user"]
    assert "memory_applied=True" in captured["user"]


def test_system_prompt_uses_redshift_rules(monkeypatch):
    metadata = _build_metadata()
    service = SnowflakeSQLGenerationService(client=object(), model="test-model")
    captured: dict = {}

    def fake_invoke(system_prompt: str, user_prompt: str, temperature: float) -> str:
        captured["system"] = system_prompt
        return "SELECT ORDER_ID FROM PUBLIC.ORDERS"

    monkeypatch.setattr(service, "_invoke_llm", fake_invoke)
    service.generate_sql(
        SnowflakeSQLGenerationRequest(
            prompt="list orders",
            metadata=metadata,
            target_warehouse=WarehouseType.REDSHIFT,
            enforce_limit=False,
            max_rows=1000,
            temperature=0.0,
        )
    )

    assert "Target warehouse dialect: redshift" in captured["system"]
    assert "CTE or subquery" in captured["system"]
    assert "QUALIFY" not in captured["system"]


def test_schema_context_limits_to_relevant_tables(monkeypatch):
    metadata = _build_metadata()
    service = SnowflakeSQLGenerationService(client=object(), model="test-model")
    captured: dict = {}

    def fake_invoke(system_prompt: str, user_prompt: str, temperature: float) -> str:
        captured["system"] = system_prompt
        return "SELECT CUSTOMER_NAME FROM PUBLIC.CUSTOMERS"

    monkeypatch.setattr(service, "_invoke_llm", fake_invoke)
    service.generate_sql(
        SnowflakeSQLGenerationRequest(
            prompt="List customer names",
            metadata=metadata,
            max_schema_tables=1,
            enforce_limit=False,
            max_rows=1000,
            temperature=0.0,
        )
    )

    assert "PUBLIC.CUSTOMERS" in captured["system"]
    assert "PUBLIC.ORDERS" not in captured["system"]
