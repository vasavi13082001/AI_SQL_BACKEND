"""Service for generating and validating Snowflake SQL from natural language."""
from __future__ import annotations

import re
from typing import Any

from app.config import get_settings
from app.schemas.snowflake import (
    ConversationTurn,
    SnowflakeMetadataResponse,
    SnowflakeSQLGenerationRequest,
    SnowflakeSQLGenerationResponse,
)
from app.schemas.warehouse import WarehouseType
from app.services.nl_query_parser import NaturalLanguageQueryParser, ParsedQuery
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
        schema_text, relationships_text = self._build_schema_context(
            metadata=request.metadata,
            prompt=request.prompt,
            conversation_history=request.conversation_history,
            max_schema_tables=request.max_schema_tables,
        )
        system_prompt = self._build_system_prompt(
            metadata=request.metadata,
            target_warehouse=request.target_warehouse,
            schema_text=schema_text,
            relationships_text=relationships_text,
        )
        intent_summary = self._build_intent_summary(
            prompt=request.prompt,
            conversation_history=request.conversation_history,
        )
        user_prompt = self._build_user_prompt(request, intent_summary)

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
            "Prompt injects relevance-ranked schema and relationship context.",
            "Conversational intent memory is applied for follow-up questions.",
        ]
        if request.target_warehouse == WarehouseType.SNOWFLAKE:
            optimization_notes.append(
                "Snowflake-specific rules applied: DATE_TRUNC, ILIKE, QUALIFY, IFF guidance."
            )
        else:
            optimization_notes.append(
                "Redshift-specific rules applied: DATE_TRUNC, ILIKE, CTE-first window filtering, CASE guidance."
            )

        if request.conversation_history:
            optimization_notes.append(
                f"Prompt includes {len(request.conversation_history)} prior conversation turn(s)."
            )

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
    def _build_system_prompt(
        metadata: SnowflakeMetadataResponse,
        target_warehouse: WarehouseType,
        schema_text: str,
        relationships_text: str,
    ) -> str:
        warehouse_name = "Snowflake" if target_warehouse == WarehouseType.SNOWFLAKE else "Redshift"
        warehouse_rules = SnowflakeSQLGenerationService._warehouse_prompt_rules(target_warehouse)
        warehouse_rules_text = "\n".join(
            f"{index}) {rule}" for index, rule in enumerate(warehouse_rules, start=14)
        )

        return (
            f"You are an expert {warehouse_name} SQL engineer.\n"
            f"Return only a single valid {warehouse_name} SQL statement with no explanations or markdown.\n"
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
            "7) Wrap multi-step logic in CTEs (WITH clauses) rather than deeply nested subqueries.\n"
            "8) Apply IS NOT NULL guards on nullable join keys to avoid unintentional row loss.\n"
            "9) Never include SQL comments (-- or /* */).\n"
            "10) If this is a follow-up request, carry forward unchanged intent from conversation context.\n"
            "11) Prefer deterministic aliases and fully qualify tables as SCHEMA.TABLE.\n"
            "12) Keep SQL concise and executable without placeholders.\n"
            "13) Ensure expressions and functions match the target warehouse dialect.\n"
            f"{warehouse_rules_text}\n"
            "\n"
            f"Database: {metadata.database}\n"
            f"Target warehouse dialect: {target_warehouse.value}\n"
            "Schema (format: SCHEMA.TABLE: COL (TYPE, nullability), ...):\n"
            f"{schema_text}\n"
            "Relationships (suggested JOIN patterns):\n"
            f"{relationships_text}"
        )

    @staticmethod
    def _build_user_prompt(request: SnowflakeSQLGenerationRequest, intent_summary: str) -> str:
        limit_instruction = (
            f"Include a LIMIT {request.max_rows} clause at the end of the outermost query."
            if request.enforce_limit
            else "No row limit is required."
        )

        conversation_text = SnowflakeSQLGenerationService._format_conversation_history(
            request.conversation_history
        )

        return (
            f"Warehouse dialect: {request.target_warehouse.value}\n"
            f"Resolved intent: {intent_summary}\n"
            f"Conversation context:\n{conversation_text}\n"
            f"Request: {request.prompt}\n"
            f"Row limit: {limit_instruction}\n"
            "Return only the SQL statement."
        )

    @staticmethod
    def _warehouse_prompt_rules(target_warehouse: WarehouseType) -> list[str]:
        if target_warehouse == WarehouseType.SNOWFLAKE:
            return [
                "Use DATE_TRUNC or TO_DATE for date/timestamp bucketing and filtering.",
                "Use ILIKE for case-insensitive text matching.",
                "Use QUALIFY for filtering window-function outputs when appropriate.",
                "For conditional aggregation, prefer IFF or CASE inside aggregate functions.",
            ]
        return [
            "Use DATE_TRUNC for date/time bucketing; avoid string-based date formatting in predicates.",
            "Use ILIKE for case-insensitive text matching.",
            "Filter window-function outputs with a CTE or subquery for compatibility.",
            "Use CASE expressions for conditional logic and conditional aggregation.",
        ]

    @staticmethod
    def _format_conversation_history(conversation_history: list[ConversationTurn]) -> str:
        if not conversation_history:
            return "- none"

        recent_turns = conversation_history[-6:]
        lines = [
            f"- {turn.role.upper()}: {turn.message.strip()}"
            for turn in recent_turns
            if turn.message.strip()
        ]
        return "\n".join(lines) if lines else "- none"

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        return {token for token in re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", text.lower()) if len(token) > 1}

    def _build_schema_context(
        self,
        metadata: SnowflakeMetadataResponse,
        prompt: str,
        conversation_history: list[ConversationTurn],
        max_schema_tables: int,
    ) -> tuple[str, str]:
        context_text = " ".join([prompt, *[turn.message for turn in conversation_history]])
        context_terms = self._tokenize(context_text)

        scored_tables: list[tuple[int, str, str, str]] = []
        for schema in metadata.schemas:
            for table in schema.tables:
                table_tokens = self._tokenize(f"{schema.name} {table.name}")
                column_tokens: set[str] = set()
                col_parts: list[str] = []
                for column in table.columns:
                    column_tokens.update(self._tokenize(column.name))
                    null_flag = "nullable" if column.is_nullable else "NOT NULL"
                    col_parts.append(f"{column.name} ({column.data_type}, {null_flag})")

                overlap = len(context_terms.intersection(table_tokens.union(column_tokens)))
                table_name_token = table.name.lower()
                strong_name_match = 4 if table_name_token in context_text.lower() else 0
                score = overlap + strong_name_match

                schema_line = f"- {schema.name}.{table.name}: {', '.join(col_parts)}"
                scored_tables.append((score, schema.name, table.name, schema_line))

        scored_tables.sort(key=lambda item: (-item[0], item[1], item[2]))
        selected = scored_tables[:max_schema_tables]
        if not selected:
            return "- none", "- none"

        schema_text = "\n".join(item[3] for item in selected)
        selected_fq_tables = {f"{schema}.{table}".upper() for _, schema, table, _ in selected}

        relationship_lines: list[str] = []
        for relation in metadata.relationships:
            source_fq = f"{relation.source_schema}.{relation.source_table}".upper()
            target_fq = f"{relation.target_schema}.{relation.target_table}".upper()
            if source_fq in selected_fq_tables and target_fq in selected_fq_tables:
                relationship_lines.append(
                    "- JOIN "
                    f"{relation.source_schema}.{relation.source_table} t1 "
                    f"ON t1.{relation.source_column} = "
                    f"{relation.target_schema}.{relation.target_table}.{relation.target_column}"
                )

        relationships_text = "\n".join(relationship_lines) if relationship_lines else "- none"
        return schema_text, relationships_text

    def _build_intent_summary(
        self,
        prompt: str,
        conversation_history: list[ConversationTurn],
    ) -> str:
        parser = NaturalLanguageQueryParser()
        prior_parsed: list[ParsedQuery] = []

        for turn in conversation_history:
            if turn.role != "user":
                continue
            parsed_turn = parser.parse(turn.message, prior_queries=prior_parsed)
            prior_parsed.append(parsed_turn)

        current = parser.parse(prompt, prior_queries=prior_parsed)

        filters = ", ".join(
            f"{flt.field} {flt.operator} {flt.value}" for flt in current.filters
        ) or "none"
        date_window = (
            f"{current.date_range.start_date} to {current.date_range.end_date}"
            if current.date_range
            else "none"
        )

        return (
            f"metrics={current.metrics or ['none']}; "
            f"dimensions={current.dimensions or ['none']}; "
            f"aggregations={current.aggregations or ['none']}; "
            f"filters={filters}; "
            f"date_range={date_window}; "
            f"memory_applied={current.memory_applied}"
        )
