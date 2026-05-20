"""Service for generating and validating Snowflake SQL from natural language."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.config import get_settings
from app.schemas.snowflake import (
    SchemaMetadata,
    SnowflakeMetadataResponse,
    SnowflakeSQLGenerationRequest,
    SnowflakeSQLGenerationResponse,
)


class SQLValidationError(ValueError):
    """Raised when generated SQL violates validation constraints."""


@dataclass
class _SchemaContext:
    """Normalized schema context for validation and prompting."""

    tables: set[str]
    fully_qualified_tables: set[str]
    columns_by_table: dict[str, set[str]]
    nullable_columns_by_table: dict[str, set[str]]
    date_columns_by_table: dict[str, set[str]]


class SnowflakeSQLGenerationService:
    """Generate optimized Snowflake SQL with schema-aware prompting and validation."""

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
    }

    def __init__(self, client: Any | None = None, model: str | None = None) -> None:
        settings = get_settings()
        self.model = model or settings.openai_model

        if client is not None:
            self._client = client
            return

        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured.")

        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise RuntimeError("openai package is not installed.") from exc

        self._client = OpenAI(api_key=settings.openai_api_key)

    def generate_sql(self, request: SnowflakeSQLGenerationRequest) -> SnowflakeSQLGenerationResponse:
        """Generate SQL from natural language and enforce validation constraints."""
        system_prompt = self._build_system_prompt(request.metadata)
        user_prompt = self._build_user_prompt(request)

        raw_sql = self._invoke_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=request.temperature,
        )
        validated_sql = self.validate_sql(
            sql=raw_sql,
            metadata=request.metadata,
            enforce_limit=request.enforce_limit,
            max_rows=request.max_rows,
        )

        optimization_notes: list[str] = [
            "Only SELECT/WITH statements are allowed.",
            "Query references validated against provided schema metadata.",
            "Implicit cross-joins rejected; explicit JOIN syntax required.",
            "Schema prompt includes column nullability and data-type context.",
            "Snowflake-specific rules applied: DATE_TRUNC, ILIKE, QUALIFY, IFF guidance.",
        ]
        if request.enforce_limit:
            optimization_notes.append(
                f"LIMIT {request.max_rows} enforced; any larger model-generated limit was capped."
            )

        return SnowflakeSQLGenerationResponse(
            sql=validated_sql,
            model=self.model,
            validation_passed=True,
            optimization_notes=optimization_notes,
        )

    def _invoke_llm(self, system_prompt: str, user_prompt: str, temperature: float) -> str:
        """Call OpenAI and extract SQL text from the response."""
        response = self._client.chat.completions.create(
            model=self.model,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )

        content = response.choices[0].message.content
        if not content:
            raise SQLValidationError("OpenAI returned an empty SQL response.")
        return content

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

        schema_context = self._build_schema_context(metadata.schemas)
        alias_map = self._validate_table_references(normalized, schema_context)
        self._validate_qualified_column_references(normalized, schema_context, alias_map)

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
    def _build_schema_context(schemas: list[SchemaMetadata]) -> _SchemaContext:
        tables: set[str] = set()
        fully_qualified_tables: set[str] = set()
        columns_by_table: dict[str, set[str]] = {}
        nullable_columns_by_table: dict[str, set[str]] = {}
        date_columns_by_table: dict[str, set[str]] = {}

        _DATE_TYPE_PATTERNS = re.compile(
            r"\b(DATE|DATETIME|TIMESTAMP|TIMESTAMP_NTZ|TIMESTAMP_LTZ|TIMESTAMP_TZ|TIME)\b",
            flags=re.IGNORECASE,
        )

        for schema in schemas:
            schema_name = schema.name.upper()
            for table in schema.tables:
                table_name = table.name.upper()
                fq_table_name = f"{schema_name}.{table_name}"
                table_columns = {column.name.upper() for column in table.columns}
                nullable_cols = {
                    column.name.upper()
                    for column in table.columns
                    if column.is_nullable
                }
                date_cols = {
                    column.name.upper()
                    for column in table.columns
                    if _DATE_TYPE_PATTERNS.search(column.data_type)
                }

                tables.add(table_name)
                fully_qualified_tables.add(fq_table_name)
                columns_by_table[table_name] = table_columns
                columns_by_table[fq_table_name] = table_columns
                nullable_columns_by_table[table_name] = nullable_cols
                nullable_columns_by_table[fq_table_name] = nullable_cols
                date_columns_by_table[table_name] = date_cols
                date_columns_by_table[fq_table_name] = date_cols

        return _SchemaContext(
            tables=tables,
            fully_qualified_tables=fully_qualified_tables,
            columns_by_table=columns_by_table,
            nullable_columns_by_table=nullable_columns_by_table,
            date_columns_by_table=date_columns_by_table,
        )

    @staticmethod
    def _normalize_identifier(identifier: str) -> str:
        cleaned = identifier.strip().rstrip(",")
        cleaned = cleaned.replace('"', "")
        return cleaned.upper()

    def _validate_table_references(self, sql: str, schema_context: _SchemaContext) -> dict[str, str]:
        table_pattern = re.compile(
            r'\b(?:FROM|JOIN)\s+([a-zA-Z0-9_\.\"]+)(?:\s+(?:AS\s+)?([a-zA-Z0-9_\"]+))?',
            flags=re.IGNORECASE,
        )
        table_matches = table_pattern.findall(sql)

        alias_map: dict[str, str] = {}
        unknown_tables: list[str] = []
        for table_ref, alias_ref in table_matches:
            normalized_ref = self._normalize_identifier(table_ref)

            if normalized_ref.startswith("("):
                # Subquery source.
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
                alias_map[self._normalize_identifier(alias_ref)] = table_key

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

    @staticmethod
    def _build_system_prompt(metadata: SnowflakeMetadataResponse) -> str:
        schema_lines: list[str] = []
        for schema in metadata.schemas:
            for table in schema.tables:
                col_parts: list[str] = []
                for column in table.columns:
                    null_flag = "nullable" if column.is_nullable else "NOT NULL"
                    col_parts.append(f"{column.name} ({column.data_type}, {null_flag})")
                column_descriptions = ", ".join(col_parts)
                schema_lines.append(
                    f"- {schema.name}.{table.name}: {column_descriptions}"
                )

        relationship_lines = [
            (
                f"- JOIN {relation.source_schema}.{relation.source_table} t1 "
                f"ON t1.{relation.source_column} = "
                f"{relation.target_schema}.{relation.target_table}.{relation.target_column}"
            )
            for relation in metadata.relationships
        ]

        relationships_text = "\n".join(relationship_lines) if relationship_lines else "- none"
        schema_text = "\n".join(schema_lines) if schema_lines else "- none"

        return (
            "You are an expert Snowflake SQL engineer.\n"
            "Return only a single valid Snowflake SQL statement — no explanations, no markdown.\n"
            "\n"
            "GENERATION RULES:\n"
            "1) Generate exactly one SELECT or WITH (CTE) query. No DDL, DML, or admin commands.\n"
            "2) Use only the tables and columns listed in the schema below. Never fabricate names.\n"
            "3) Always list explicit columns — never use SELECT *.\n"
            "4) Push filter predicates as early as possible (predicate pushdown). Filter in the\n"
            "   innermost subquery or CTE step, not in an outer wrapper.\n"
            "5) Use explicit ANSI JOIN syntax (INNER JOIN, LEFT JOIN, etc.). Never use\n"
            "   comma-separated FROM lists (implicit cross-joins).\n"
            "6) Use the relationship definitions below for correct join keys.\n"
            "7) For date/timestamp columns use DATE_TRUNC or TO_DATE instead of string casting.\n"
            "8) For case-insensitive text matching use ILIKE instead of LOWER(col) = LOWER(val).\n"
            "9) For window-function result filtering use QUALIFY instead of a subquery wrapper.\n"
            "10) For conditional aggregation use IFF or CASE inside aggregate functions.\n"
            "11) Wrap multi-step logic in CTEs (WITH clauses) rather than deeply nested subqueries.\n"
            "12) Apply IS NOT NULL guards on nullable join keys to avoid unintentional row loss.\n"
            "13) Never include SQL comments (-- or /* */).\n"
            "\n"
            f"Database: {metadata.database}\n"
            "Schema (format: SCHEMA.TABLE: COL (TYPE, nullability), ...):\n"
            f"{schema_text}\n"
            "Relationships (suggested JOIN patterns):\n"
            f"{relationships_text}"
        )

    @staticmethod
    def _build_user_prompt(request: SnowflakeSQLGenerationRequest) -> str:
        limit_instruction = (
            f"Include a LIMIT {request.max_rows} clause at the end of the outermost query."
            if request.enforce_limit
            else "No row limit is required."
        )
        return (
            f"Request: {request.prompt}\n"
            f"Row limit: {limit_instruction}\n"
            "Return only the SQL statement."
        )
