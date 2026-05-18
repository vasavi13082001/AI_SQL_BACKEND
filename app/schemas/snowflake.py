"""Pydantic schemas for Snowflake metadata extraction."""
from datetime import datetime
from pydantic import BaseModel, Field


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
