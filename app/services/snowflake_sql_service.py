"""Service for generating and validating Snowflake SQL from natural language."""
from __future__ import annotations

from typing import Any

from app.config import get_settings
from app.schemas.snowflake import (
    SnowflakeMetadataResponse,
    SnowflakeSQLGenerationRequest,
    SnowflakeSQLGenerationResponse,
)
from app.services.sql_validation_engine import SQLValidationEngine, SQLValidationError


class SnowflakeSQLGenerationService:
    """Generate optimized Snowflake SQL with schema-aware prompting and validation."""

    def __init__(self, client: Any | None = None, model: str | None = None) -> None:
        settings = get_settings()
        self.model = model or settings.openai_model
        self._validator = SQLValidationEngine()

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
            "JOIN predicates must match known metadata relationships.",
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
        """Validate SQL via the reusable SQL validation engine."""
        return self._validator.validate_sql(
            sql=sql,
            metadata=metadata,
            enforce_limit=enforce_limit,
            max_rows=max_rows,
        )

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
