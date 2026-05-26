"""Pydantic schemas for SQL optimization requests and responses."""
from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class SQLDialect(str, Enum):
    """Supported SQL dialects for optimization."""

    SNOWFLAKE = "snowflake"
    REDSHIFT = "redshift"


class OptimizationSeverity(str, Enum):
    """Severity level of an optimization finding."""

    ERROR = "error"       # Query has a correctness or major performance issue
    WARNING = "warning"   # Likely sub-optimal; rewrite strongly recommended
    INFO = "info"         # Minor suggestion; rewrite is optional


class AppliedRule(BaseModel):
    """A single optimization rule that was evaluated and triggered."""

    rule_id: str = Field(..., description="Unique rule identifier")
    description: str = Field(..., description="Human-readable description of the optimization")
    severity: OptimizationSeverity
    rewritten: bool = Field(..., description="Whether the SQL was automatically rewritten")
    original_fragment: str | None = Field(
        None, description="The SQL fragment that triggered the rule"
    )
    rewritten_fragment: str | None = Field(
        None, description="The replacement fragment, if auto-rewritten"
    )


class SQLOptimizationRequest(BaseModel):
    """Input payload for SQL optimization."""

    sql: str = Field(..., min_length=6, description="The SQL query to optimize")
    dialect: SQLDialect = Field(
        default=SQLDialect.SNOWFLAKE,
        description="Target SQL dialect: snowflake or redshift",
    )
    auto_rewrite: bool = Field(
        default=True,
        description="Whether to apply safe automatic rewrites; set false for analysis-only",
    )


class SQLOptimizationResponse(BaseModel):
    """Result of SQL optimization analysis and rewriting."""

    original_sql: str
    optimized_sql: str
    dialect: SQLDialect
    rules_applied: list[AppliedRule]
    rewrite_count: int = Field(..., description="Number of automatic rewrites performed")
    warning_count: int = Field(..., description="Number of warnings raised")
    fully_optimized: bool = Field(
        ...,
        description="True when no warnings remain after rewriting",
    )
