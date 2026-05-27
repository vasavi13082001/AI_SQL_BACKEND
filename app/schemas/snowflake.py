"""Pydantic schemas for Snowflake metadata extraction."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.warehouse import WarehouseType


class SnowflakeConnectionRequest(BaseModel):
    """Connection details and extraction filters for Snowflake."""

    account: str = Field(..., description="Snowflake account identifier")
    user: str = Field(..., description="Snowflake username")
    password: str = Field(..., description="Snowflake password")
    warehouse: str = Field(..., description="Snowflake warehouse")
    database: str = Field(..., description="Snowflake database to inspect")
    role: str | None = Field(None, description="Optional Snowflake role")
    schemas: list[str] | None = Field(
        default=None,
        description="Optional list of schema names to inspect",
    )
    include_views: bool = Field(
        default=True,
        description="Include views in extracted table metadata",
    )


class ColumnMetadata(BaseModel):
    """Column-level metadata for a table."""

    name: str
    data_type: str
    is_nullable: bool
    default: str | None = None
    ordinal_position: int


class TableMetadata(BaseModel):
    """Table-level metadata containing all columns."""

    name: str
    table_type: str
    columns: list[ColumnMetadata]


class SchemaMetadata(BaseModel):
    """Schema-level metadata containing all tables."""

    name: str
    tables: list[TableMetadata]


class RelationshipMetadata(BaseModel):
    """Relationship metadata inferred from foreign keys."""

    constraint_name: str
    source_schema: str
    source_table: str
    source_column: str
    target_schema: str
    target_table: str
    target_column: str


class SnowflakeMetadataResponse(BaseModel):
    """Complete metadata snapshot for selected Snowflake database objects."""

    database: str
    extracted_at: datetime
    schemas: list[SchemaMetadata]
    relationships: list[RelationshipMetadata]


class ConversationTurn(BaseModel):
    """A prior conversational message used to resolve follow-up prompts."""

    role: Literal["user", "assistant", "system"] = Field(
        ...,
        description="Role of the speaker for this turn",
    )
    message: str = Field(
        ...,
        min_length=1,
        description="Natural language content or SQL text from the turn",
    )


class SnowflakeSQLGenerationRequest(BaseModel):
    """Input payload to generate Snowflake SQL from natural language."""

    prompt: str = Field(..., min_length=3, description="Natural language analytics request")
    metadata: SnowflakeMetadataResponse = Field(
        ...,
        description="Schema metadata used to constrain SQL generation",
    )
    target_warehouse: WarehouseType = Field(
        default=WarehouseType.SNOWFLAKE,
        description="Warehouse dialect to target in generated SQL",
    )
    conversation_history: list[ConversationTurn] = Field(
        default_factory=list,
        description="Recent conversation turns for contextual follow-up generation",
    )
    max_schema_tables: int = Field(
        default=25,
        ge=1,
        le=200,
        description="Maximum number of most-relevant tables to inject into the prompt context",
    )
    enforce_limit: bool = Field(
        default=True,
        description="Whether to enforce a row limit on generated SQL",
    )
    max_rows: int = Field(
        default=1000,
        ge=1,
        le=100000,
        description="Maximum allowed rows when limit is enforced",
    )
    temperature: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="OpenAI temperature for SQL generation",
    )


class SnowflakeSQLGenerationResponse(BaseModel):
    """Validated Snowflake SQL generated from natural language."""

    sql: str
    model: str
    validation_passed: bool
    optimization_notes: list[str]
