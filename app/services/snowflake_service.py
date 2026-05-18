"""Service for extracting Snowflake schemas, tables, columns, and relationships."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from logging import getLogger
from typing import Any

from app.schemas.snowflake import (
    ColumnMetadata,
    RelationshipMetadata,
    SchemaMetadata,
    SnowflakeConnectionRequest,
    SnowflakeMetadataResponse,
    TableMetadata,
)

logger = getLogger(__name__)


class SnowflakeMetadataService:
    """Business logic for dynamic Snowflake metadata extraction."""

    @staticmethod
    def extract_metadata(
        request: SnowflakeConnectionRequest,
    ) -> SnowflakeMetadataResponse:
        """Connect to Snowflake and extract schemas, tables, columns, and FK relationships."""
        try:
            import snowflake.connector
        except ImportError as exc:
            raise RuntimeError(
                "snowflake-connector-python is not installed. Add it to dependencies."
            ) from exc

        connection_kwargs: dict[str, Any] = {
            "account": request.account,
            "user": request.user,
            "password": request.password,
            "warehouse": request.warehouse,
            "database": request.database,
        }
        if request.role:
            connection_kwargs["role"] = request.role

        logger.info("Starting Snowflake metadata extraction")
        with snowflake.connector.connect(**connection_kwargs) as conn:
            with conn.cursor(snowflake.connector.DictCursor) as cursor:
                schema_names = SnowflakeMetadataService._fetch_schema_names(cursor, request)
                tables_by_schema = SnowflakeMetadataService._fetch_tables(
                    cursor,
                    request.database,
                    schema_names,
                    request.include_views,
                )
                columns_by_table = SnowflakeMetadataService._fetch_columns(
                    cursor,
                    request.database,
                    schema_names,
                )
                relationships = SnowflakeMetadataService._fetch_relationships(
                    cursor,
                    request.database,
                    schema_names,
                )

        schema_payload = SnowflakeMetadataService._build_schema_payload(
            schema_names,
            tables_by_schema,
            columns_by_table,
        )

        return SnowflakeMetadataResponse(
            database=request.database,
            extracted_at=datetime.now(timezone.utc),
            schemas=schema_payload,
            relationships=relationships,
        )

    @staticmethod
    def _fetch_schema_names(cursor: Any, request: SnowflakeConnectionRequest) -> list[str]:
        cursor.execute(
            """
            SELECT SCHEMA_NAME
            FROM INFORMATION_SCHEMA.SCHEMATA
            WHERE CATALOG_NAME = %s
              AND SCHEMA_NAME <> 'INFORMATION_SCHEMA'
            ORDER BY SCHEMA_NAME
            """,
            (request.database,),
        )
        available = [row["SCHEMA_NAME"] for row in cursor.fetchall()]
        if not request.schemas:
            return available

        requested = {schema.upper() for schema in request.schemas}
        filtered = [schema for schema in available if schema.upper() in requested]
        return filtered

    @staticmethod
    def _fetch_tables(
        cursor: Any,
        database: str,
        schema_names: list[str],
        include_views: bool,
    ) -> dict[str, list[dict[str, str]]]:
        if not schema_names:
            return {}

        placeholders = ", ".join(["%s"] * len(schema_names))
        table_types = ["BASE TABLE"]
        if include_views:
            table_types.append("VIEW")
        table_type_placeholders = ", ".join(["%s"] * len(table_types))

        query = f"""
            SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_CATALOG = %s
              AND TABLE_SCHEMA IN ({placeholders})
              AND TABLE_TYPE IN ({table_type_placeholders})
            ORDER BY TABLE_SCHEMA, TABLE_NAME
        """
        params = [database, *schema_names, *table_types]
        cursor.execute(query, tuple(params))

        result: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in cursor.fetchall():
            result[row["TABLE_SCHEMA"]].append(
                {
                    "name": row["TABLE_NAME"],
                    "table_type": row["TABLE_TYPE"],
                }
            )
        return dict(result)

    @staticmethod
    def _fetch_columns(
        cursor: Any,
        database: str,
        schema_names: list[str],
    ) -> dict[tuple[str, str], list[ColumnMetadata]]:
        if not schema_names:
            return {}

        placeholders = ", ".join(["%s"] * len(schema_names))
        query = f"""
            SELECT TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME, DATA_TYPE,
                   IS_NULLABLE, COLUMN_DEFAULT, ORDINAL_POSITION
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_CATALOG = %s
              AND TABLE_SCHEMA IN ({placeholders})
            ORDER BY TABLE_SCHEMA, TABLE_NAME, ORDINAL_POSITION
        """
        cursor.execute(query, tuple([database, *schema_names]))

        columns_map: dict[tuple[str, str], list[ColumnMetadata]] = defaultdict(list)
        for row in cursor.fetchall():
            key = (row["TABLE_SCHEMA"], row["TABLE_NAME"])
            columns_map[key].append(
                ColumnMetadata(
                    name=row["COLUMN_NAME"],
                    data_type=row["DATA_TYPE"],
                    is_nullable=str(row["IS_NULLABLE"]).upper() == "YES",
                    default=row["COLUMN_DEFAULT"],
                    ordinal_position=int(row["ORDINAL_POSITION"]),
                )
            )

        return dict(columns_map)

    @staticmethod
    def _fetch_relationships(
        cursor: Any,
        database: str,
        schema_names: list[str],
    ) -> list[RelationshipMetadata]:
        if not schema_names:
            return []

        placeholders = ", ".join(["%s"] * len(schema_names))
        query = f"""
            SELECT
                fk.CONSTRAINT_NAME AS FK_CONSTRAINT_NAME,
                fk.TABLE_SCHEMA AS FK_SCHEMA,
                fk.TABLE_NAME AS FK_TABLE,
                fk.COLUMN_NAME AS FK_COLUMN,
                pk.TABLE_SCHEMA AS PK_SCHEMA,
                pk.TABLE_NAME AS PK_TABLE,
                pk.COLUMN_NAME AS PK_COLUMN
            FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc
            JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE fk
              ON rc.CONSTRAINT_CATALOG = fk.CONSTRAINT_CATALOG
             AND rc.CONSTRAINT_SCHEMA = fk.CONSTRAINT_SCHEMA
             AND rc.CONSTRAINT_NAME = fk.CONSTRAINT_NAME
            JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE pk
              ON rc.UNIQUE_CONSTRAINT_CATALOG = pk.CONSTRAINT_CATALOG
             AND rc.UNIQUE_CONSTRAINT_SCHEMA = pk.CONSTRAINT_SCHEMA
             AND rc.UNIQUE_CONSTRAINT_NAME = pk.CONSTRAINT_NAME
             AND fk.POSITION_IN_UNIQUE_CONSTRAINT = pk.ORDINAL_POSITION
            WHERE fk.CONSTRAINT_CATALOG = %s
              AND fk.TABLE_SCHEMA IN ({placeholders})
            ORDER BY fk.TABLE_SCHEMA, fk.TABLE_NAME, fk.CONSTRAINT_NAME, fk.ORDINAL_POSITION
        """
        cursor.execute(query, tuple([database, *schema_names]))

        relationships: list[RelationshipMetadata] = []
        for row in cursor.fetchall():
            relationships.append(
                RelationshipMetadata(
                    constraint_name=row["FK_CONSTRAINT_NAME"],
                    source_schema=row["FK_SCHEMA"],
                    source_table=row["FK_TABLE"],
                    source_column=row["FK_COLUMN"],
                    target_schema=row["PK_SCHEMA"],
                    target_table=row["PK_TABLE"],
                    target_column=row["PK_COLUMN"],
                )
            )

        return relationships

    @staticmethod
    def _build_schema_payload(
        schema_names: list[str],
        tables_by_schema: dict[str, list[dict[str, str]]],
        columns_by_table: dict[tuple[str, str], list[ColumnMetadata]],
    ) -> list[SchemaMetadata]:
        schemas: list[SchemaMetadata] = []
        for schema_name in schema_names:
            table_payload: list[TableMetadata] = []
            for table in tables_by_schema.get(schema_name, []):
                key = (schema_name, table["name"])
                table_payload.append(
                    TableMetadata(
                        name=table["name"],
                        table_type=table["table_type"],
                        columns=columns_by_table.get(key, []),
                    )
                )

            schemas.append(SchemaMetadata(name=schema_name, tables=table_payload))

        return schemas
