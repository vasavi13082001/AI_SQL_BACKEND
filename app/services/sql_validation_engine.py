"""Reusable SQL validation engine for Snowflake SQL safety and schema correctness."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.schemas.snowflake import RelationshipMetadata, SchemaMetadata, SnowflakeMetadataResponse


class SQLValidationError(ValueError):
    """Raised when SQL violates validation or safety constraints."""


@dataclass
class _SchemaContext:
    """Normalized schema context used during SQL validation."""

    tables: set[str]
    fully_qualified_tables: set[str]
    columns_by_table: dict[str, set[str]]


class SQLValidationEngine:
    """Validate generated SQL against metadata and safety rules."""

    _DISALLOWED_KEYWORDS = {
        "INSERT",
        "UPDATE",
        "DELETE",
        "MERGE",
        "DROP",
        "ALTER",
        "TRUNCATE",
        "CREATE",
        "GRANT",
        "REVOKE",
        "CALL",
        "COPY",
        "PUT",
        "GET",
        "REMOVE",
        "USE",
        "COMMENT",
        "EXECUTE",
    }

    def validate_sql(
        self,
        sql: str,
        metadata: SnowflakeMetadataResponse,
        enforce_limit: bool,
        max_rows: int,
    ) -> str:
        """Apply SQL safety and schema validation rules."""
        cleaned_sql = self._strip_code_fences(sql).strip()
        if not cleaned_sql:
            raise SQLValidationError("Generated SQL is empty.")

        if "--" in cleaned_sql or "/*" in cleaned_sql or "*/" in cleaned_sql:
            raise SQLValidationError("SQL comments are not allowed.")

        normalized = cleaned_sql.rstrip(";").strip()
        if ";" in normalized:
            raise SQLValidationError("Only a single SQL statement is allowed.")

        leading_keyword_match = re.match(r"^\s*([a-zA-Z]+)", normalized)
        if not leading_keyword_match:
            raise SQLValidationError("Unable to parse SQL statement.")

        leading_keyword = leading_keyword_match.group(1).upper()
        if leading_keyword not in {"SELECT", "WITH"}:
            raise SQLValidationError("Only SELECT queries are permitted.")

        if re.search(r"\bSELECT\s+\*\b", normalized, flags=re.IGNORECASE):
            raise SQLValidationError("SELECT * is not allowed. Specify explicit columns.")

        if self._contains_disallowed_keyword(normalized):
            raise SQLValidationError("Generated SQL contains disallowed operation keywords.")

        self._validate_no_implicit_cross_join(normalized)
        if re.search(r"\bCROSS\s+JOIN\b", normalized, flags=re.IGNORECASE):
            raise SQLValidationError("CROSS JOIN is not allowed. Use relationship-based JOIN conditions.")

        schema_context = self._build_schema_context(metadata.schemas)
        alias_map = self._validate_table_references(normalized, schema_context)
        self._validate_qualified_column_references(normalized, schema_context, alias_map)
        self._validate_join_relationships(normalized, metadata.relationships, alias_map)

        existing_limit = re.search(r"\bLIMIT\b\s+(\d+)", normalized, flags=re.IGNORECASE)
        if enforce_limit:
            if existing_limit:
                present_limit = int(existing_limit.group(1))
                if present_limit > max_rows:
                    normalized = re.sub(
                        r"\bLIMIT\b\s+\d+",
                        f"LIMIT {max_rows}",
                        normalized,
                        flags=re.IGNORECASE,
                    )
            else:
                normalized = f"{normalized}\nLIMIT {max_rows}"

        return normalized

    @classmethod
    def _contains_disallowed_keyword(cls, sql: str) -> bool:
        for keyword in cls._DISALLOWED_KEYWORDS:
            if re.search(rf"\b{keyword}\b", sql, flags=re.IGNORECASE):
                return True
        return False

    @staticmethod
    def _validate_no_implicit_cross_join(sql: str) -> None:
        """Reject implicit cross-joins written as comma-separated FROM lists."""
        from_clause = re.search(
            r"\bFROM\b(.+?)(?:\bWHERE\b|\bGROUP\b|\bORDER\b|\bHAVING\b|\bLIMIT\b|\bQUALIFY\b|$)",
            sql,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not from_clause:
            return
        clause_body = from_clause.group(1)
        clause_body_no_subqueries = re.sub(r"\(.*?\)", "", clause_body, flags=re.DOTALL)
        if re.search(r"[a-zA-Z0-9_\"]+\s*,\s*[a-zA-Z0-9_\"]+", clause_body_no_subqueries):
            raise SQLValidationError(
                "Implicit cross-joins (comma-separated FROM lists) are not allowed. "
                "Use explicit JOIN syntax."
            )

    @staticmethod
    def _strip_code_fences(sql: str) -> str:
        stripped = sql.strip()
        if stripped.startswith("```"):
            stripped = re.sub(r"^```[a-zA-Z]*", "", stripped).strip()
            stripped = re.sub(r"```$", "", stripped).strip()
        return stripped

    @staticmethod
    def _normalize_identifier(identifier: str) -> str:
        cleaned = identifier.strip().rstrip(",")
        cleaned = cleaned.replace('"', "")
        return cleaned.upper()

    @staticmethod
    def _build_schema_context(schemas: list[SchemaMetadata]) -> _SchemaContext:
        tables: set[str] = set()
        fully_qualified_tables: set[str] = set()
        columns_by_table: dict[str, set[str]] = {}

        for schema in schemas:
            schema_name = schema.name.upper()
            for table in schema.tables:
                table_name = table.name.upper()
                fq_table_name = f"{schema_name}.{table_name}"
                table_columns = {column.name.upper() for column in table.columns}

                tables.add(table_name)
                fully_qualified_tables.add(fq_table_name)
                columns_by_table[table_name] = table_columns
                columns_by_table[fq_table_name] = table_columns

        return _SchemaContext(
            tables=tables,
            fully_qualified_tables=fully_qualified_tables,
            columns_by_table=columns_by_table,
        )

    def _validate_table_references(self, sql: str, schema_context: _SchemaContext) -> dict[str, str]:
        table_pattern = re.compile(
            r'\b(?:FROM|JOIN)\s+([a-zA-Z0-9_\.\"]+)(?:\s+(?:AS\s+)?([a-zA-Z0-9_\"]+))?',
            flags=re.IGNORECASE,
        )
        table_matches = table_pattern.findall(sql)

        alias_map: dict[str, str] = {}
        unknown_tables: list[str] = []
        reserved_tokens = {
            "ON",
            "WHERE",
            "GROUP",
            "ORDER",
            "HAVING",
            "LIMIT",
            "QUALIFY",
            "JOIN",
            "INNER",
            "LEFT",
            "RIGHT",
            "FULL",
            "CROSS",
        }

        for table_ref, alias_ref in table_matches:
            normalized_ref = self._normalize_identifier(table_ref)

            if normalized_ref.startswith("("):
                continue

            if "." in normalized_ref:
                if normalized_ref not in schema_context.fully_qualified_tables:
                    unknown_tables.append(table_ref)
                    continue
                table_key = normalized_ref
                short_table_name = normalized_ref.split(".")[-1]
            else:
                if normalized_ref not in schema_context.tables:
                    unknown_tables.append(table_ref)
                    continue
                table_key = normalized_ref
                short_table_name = normalized_ref

            alias_map[short_table_name] = table_key
            alias_map[table_key] = table_key

            if alias_ref:
                normalized_alias = self._normalize_identifier(alias_ref)
                if normalized_alias not in reserved_tokens:
                    alias_map[normalized_alias] = table_key

        if unknown_tables:
            invalid = ", ".join(sorted(set(unknown_tables)))
            raise SQLValidationError(f"SQL references unknown table(s): {invalid}")

        return alias_map

    def _validate_qualified_column_references(
        self,
        sql: str,
        schema_context: _SchemaContext,
        alias_map: dict[str, str],
    ) -> None:
        qualified_column_refs = re.findall(
            r"\b([a-zA-Z0-9_\"]+)\.([a-zA-Z0-9_\"]+)\b",
            sql,
            flags=re.IGNORECASE,
        )

        invalid_refs: list[str] = []
        for qualifier, column in qualified_column_refs:
            qualifier_key = self._normalize_identifier(qualifier)
            table_key = alias_map.get(qualifier_key)
            if not table_key:
                continue

            column_name = self._normalize_identifier(column)
            allowed_columns = schema_context.columns_by_table.get(table_key, set())
            if column_name not in allowed_columns:
                invalid_refs.append(f"{qualifier}.{column}")

        if invalid_refs:
            invalid = ", ".join(sorted(set(invalid_refs)))
            raise SQLValidationError(f"SQL references unknown column(s): {invalid}")

    def _validate_join_relationships(
        self,
        sql: str,
        relationships: list[RelationshipMetadata],
        alias_map: dict[str, str],
    ) -> None:
        relationship_keys = self._build_relationship_key_set(relationships)
        if not relationship_keys:
            return

        join_blocks = re.findall(
            r"\bJOIN\b\s+[a-zA-Z0-9_\.\"]+(?:\s+(?:AS\s+)?[a-zA-Z0-9_\"]+)?\s+\bON\b\s+(.+?)(?=(?:\b(?:INNER|LEFT|RIGHT|FULL|CROSS)?\s*JOIN\b|\bWHERE\b|\bGROUP\b|\bORDER\b|\bHAVING\b|\bLIMIT\b|\bQUALIFY\b|$))",
            sql,
            flags=re.IGNORECASE | re.DOTALL,
        )

        for join_condition in join_blocks:
            if self._join_condition_has_valid_relationship(join_condition, alias_map, relationship_keys):
                continue
            collapsed = re.sub(r"\s+", " ", join_condition).strip()
            raise SQLValidationError(
                "JOIN condition does not match any known table relationship: "
                f"{collapsed}"
            )

    @classmethod
    def _build_relationship_key_set(cls, relationships: list[RelationshipMetadata]) -> set[tuple[str, str, str, str]]:
        relationship_keys: set[tuple[str, str, str, str]] = set()
        for relation in relationships:
            source_table = cls._normalize_identifier(f"{relation.source_schema}.{relation.source_table}")
            target_table = cls._normalize_identifier(f"{relation.target_schema}.{relation.target_table}")
            source_column = cls._normalize_identifier(relation.source_column)
            target_column = cls._normalize_identifier(relation.target_column)

            relationship_keys.add((source_table, source_column, target_table, target_column))
            relationship_keys.add((target_table, target_column, source_table, source_column))

        return relationship_keys

    def _join_condition_has_valid_relationship(
        self,
        join_condition: str,
        alias_map: dict[str, str],
        relationship_keys: set[tuple[str, str, str, str]],
    ) -> bool:
        equality_pairs = re.findall(
            r"([a-zA-Z0-9_\"]+\.[a-zA-Z0-9_\"]+)\s*=\s*([a-zA-Z0-9_\"]+\.[a-zA-Z0-9_\"]+)",
            join_condition,
            flags=re.IGNORECASE,
        )

        for left_ref, right_ref in equality_pairs:
            left_table, left_column = left_ref.split(".", maxsplit=1)
            right_table, right_column = right_ref.split(".", maxsplit=1)
            left_table_key = alias_map.get(self._normalize_identifier(left_table))
            right_table_key = alias_map.get(self._normalize_identifier(right_table))
            if not left_table_key or not right_table_key:
                continue

            left_column_key = self._normalize_identifier(left_column)
            right_column_key = self._normalize_identifier(right_column)

            key = (left_table_key, left_column_key, right_table_key, right_column_key)
            if key in relationship_keys:
                return True

        return False
