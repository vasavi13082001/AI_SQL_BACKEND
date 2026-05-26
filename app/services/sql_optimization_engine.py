"""SQL optimization engine for Snowflake and Redshift performance best practices.

Each optimization rule is an instance of ``_OptimizationRule``.  Rules inspect
the SQL string with targeted regular expressions and optionally rewrite it.
Rules are organized into three groups:

* ``_COMMON_RULES``   – apply to both dialects
* ``_SNOWFLAKE_RULES`` – Snowflake-specific rewrites / warnings
* ``_REDSHIFT_RULES``  – Redshift-specific rewrites / warnings

The engine processes every rule in order, feeding the (potentially rewritten)
SQL from the previous rule into the next, so rewrites can compose safely.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

from app.schemas.optimization import (
    AppliedRule,
    OptimizationSeverity,
    SQLDialect,
    SQLOptimizationRequest,
    SQLOptimizationResponse,
)


# ---------------------------------------------------------------------------
# Rule primitives
# ---------------------------------------------------------------------------

@dataclass
class _RuleResult:
    triggered: bool
    rewritten: bool
    new_sql: str
    original_fragment: str | None = None
    rewritten_fragment: str | None = None


@dataclass
class _OptimizationRule:
    rule_id: str
    description: str
    severity: OptimizationSeverity
    # apply(sql, auto_rewrite) -> _RuleResult
    apply: Callable[[str, bool], _RuleResult] = field(repr=False)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _first_match(pattern: str, sql: str, flags: int = re.IGNORECASE) -> re.Match | None:
    return re.search(pattern, sql, flags)


def _sub(pattern: str, repl: str | Callable, sql: str, flags: int = re.IGNORECASE) -> str:
    return re.sub(pattern, repl, sql, flags=flags)


# ---------------------------------------------------------------------------
# Common rules
# ---------------------------------------------------------------------------

def _rule_select_star(sql: str, auto_rewrite: bool) -> _RuleResult:
    """Flag SELECT * – cannot be auto-rewritten without schema knowledge."""
    m = _first_match(r"\bSELECT\s+\*", sql)
    if not m:
        return _RuleResult(triggered=False, rewritten=False, new_sql=sql)
    return _RuleResult(
        triggered=True,
        rewritten=False,
        new_sql=sql,
        original_fragment=m.group(0),
    )


def _rule_redundant_distinct(sql: str, auto_rewrite: bool) -> _RuleResult:
    """Remove DISTINCT when GROUP BY already guarantees uniqueness."""
    if not re.search(r"\bDISTINCT\b", sql, re.IGNORECASE):
        return _RuleResult(triggered=False, rewritten=False, new_sql=sql)
    if not re.search(r"\bGROUP\s+BY\b", sql, re.IGNORECASE):
        return _RuleResult(triggered=False, rewritten=False, new_sql=sql)

    original = re.search(r"\bSELECT\s+DISTINCT\b", sql, re.IGNORECASE)
    if not original:
        return _RuleResult(triggered=False, rewritten=False, new_sql=sql)

    if auto_rewrite:
        new_sql = re.sub(
            r"\bSELECT\s+DISTINCT\b", "SELECT", sql, flags=re.IGNORECASE
        )
        return _RuleResult(
            triggered=True,
            rewritten=True,
            new_sql=new_sql,
            original_fragment="SELECT DISTINCT",
            rewritten_fragment="SELECT",
        )
    return _RuleResult(
        triggered=True,
        rewritten=False,
        new_sql=sql,
        original_fragment=original.group(0),
    )


def _rule_not_in_subquery(sql: str, auto_rewrite: bool) -> _RuleResult:
    """Rewrite WHERE col NOT IN (SELECT ...) → WHERE NOT EXISTS (SELECT 1 ...)."""
    pattern = (
        r"(\bWHERE\s+)(\w+(?:\.\w+)?)\s+NOT\s+IN\s*\(\s*(SELECT\s+\w+(?:\.\w+)?\s+FROM\s+\w+(?:\.\w+)?)"
        r"(\s+WHERE\s+[^)]+)?\s*\)"
    )
    m = re.search(pattern, sql, re.IGNORECASE | re.DOTALL)
    if not m:
        return _RuleResult(triggered=False, rewritten=False, new_sql=sql)

    original_fragment = m.group(0)

    if auto_rewrite:
        col = m.group(2)
        inner_select = m.group(3)
        inner_where = m.group(4) or ""
        # Extract FROM table from inner_select
        from_match = re.search(r"FROM\s+(\S+)", inner_select, re.IGNORECASE)
        if not from_match:
            return _RuleResult(triggered=True, rewritten=False, new_sql=sql,
                                original_fragment=original_fragment)
        inner_table = from_match.group(1)
        # Build a correlation: add a join condition on the NOT IN column
        # We need to find the selected column in the inner SELECT
        sel_match = re.search(r"SELECT\s+(\w+(?:\.\w+)?)\s+FROM", inner_select, re.IGNORECASE)
        if not sel_match:
            return _RuleResult(triggered=True, rewritten=False, new_sql=sql,
                                original_fragment=original_fragment)
        inner_col = sel_match.group(1)
        alias = "subq"
        inner_where_clause = inner_where.strip()
        if inner_where_clause:
            correlated = f"WHERE {alias}.{inner_col} = {col} {inner_where_clause}"
        else:
            correlated = f"WHERE {alias}.{inner_col} = {col}"
        rewritten_fragment = (
            f"WHERE NOT EXISTS (SELECT 1 FROM {inner_table} {alias} {correlated})"
        )
        new_sql = sql.replace(original_fragment, rewritten_fragment, 1)
        return _RuleResult(
            triggered=True,
            rewritten=True,
            new_sql=new_sql,
            original_fragment=original_fragment,
            rewritten_fragment=rewritten_fragment,
        )

    return _RuleResult(
        triggered=True,
        rewritten=False,
        new_sql=sql,
        original_fragment=original_fragment,
    )


def _rule_leading_wildcard(sql: str, auto_rewrite: bool) -> _RuleResult:
    """Warn about leading-wildcard LIKE patterns that prevent index use."""
    m = _first_match(r"\bLIKE\s+'%[^']+'\s*", sql)
    if not m:
        return _RuleResult(triggered=False, rewritten=False, new_sql=sql)
    return _RuleResult(
        triggered=True,
        rewritten=False,
        new_sql=sql,
        original_fragment=m.group(0).strip(),
    )


def _rule_or_union_suggestion(sql: str, auto_rewrite: bool) -> _RuleResult:
    """Warn when OR connects predicates on different columns (suggest UNION ALL)."""
    # Simple heuristic: OR in WHERE between different column references
    where_m = re.search(
        r"\bWHERE\b(.+?)(?:\bGROUP\b|\bORDER\b|\bHAVING\b|\bLIMIT\b|$)",
        sql, re.IGNORECASE | re.DOTALL,
    )
    if not where_m:
        return _RuleResult(triggered=False, rewritten=False, new_sql=sql)

    clause = where_m.group(1)
    # Find OR that connects predicates referencing distinct columns
    or_parts = re.split(r"\bOR\b", clause, flags=re.IGNORECASE)
    if len(or_parts) < 2:
        return _RuleResult(triggered=False, rewritten=False, new_sql=sql)

    col_per_part: list[set[str]] = []
    for part in or_parts:
        cols = set(re.findall(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:=|<|>|LIKE|IN)", part, re.IGNORECASE))
        col_per_part.append(cols)

    if len(col_per_part) >= 2 and col_per_part[0] != col_per_part[1]:
        first_or = re.search(r"\bOR\b", clause, re.IGNORECASE)
        return _RuleResult(
            triggered=True,
            rewritten=False,
            new_sql=sql,
            original_fragment=first_or.group(0) if first_or else "OR",
        )

    return _RuleResult(triggered=False, rewritten=False, new_sql=sql)


def _rule_count_distinct_large(sql: str, auto_rewrite: bool) -> _RuleResult:
    """Warn about COUNT(DISTINCT ...) which can be expensive on large tables."""
    m = _first_match(r"\bCOUNT\s*\(\s*DISTINCT\b", sql)
    if not m:
        return _RuleResult(triggered=False, rewritten=False, new_sql=sql)
    return _RuleResult(
        triggered=True,
        rewritten=False,
        new_sql=sql,
        original_fragment=m.group(0),
    )


def _rule_scalar_subquery_in_select(sql: str, auto_rewrite: bool) -> _RuleResult:
    """Warn about correlated scalar subqueries in the SELECT list (N+1 risk)."""
    # Detect SELECT (...subquery...) pattern
    m = re.search(
        r"\bSELECT\b[^(]*\(\s*SELECT\b",
        sql, re.IGNORECASE | re.DOTALL,
    )
    if not m:
        return _RuleResult(triggered=False, rewritten=False, new_sql=sql)
    return _RuleResult(
        triggered=True,
        rewritten=False,
        new_sql=sql,
        original_fragment="(SELECT ...) in SELECT list",
    )


# ---------------------------------------------------------------------------
# Snowflake-specific rules
# ---------------------------------------------------------------------------

def _rule_sf_lower_like_to_ilike(sql: str, auto_rewrite: bool) -> _RuleResult:
    """Rewrite LOWER(col) LIKE LOWER('...') / UPPER variant → col ILIKE '...'."""
    # LOWER(col) LIKE LOWER('literal')  or  LOWER(col) LIKE 'literal'
    pattern = (
        r"(?:LOWER|UPPER)\s*\(\s*(\w+(?:\.\w+)?)\s*\)\s+LIKE\s+"
        r"(?:(?:LOWER|UPPER)\s*\(\s*('[^']*')\s*\)|('[^']*'))"
    )
    m = re.search(pattern, sql, re.IGNORECASE)
    if not m:
        return _RuleResult(triggered=False, rewritten=False, new_sql=sql)

    original_fragment = m.group(0)
    col = m.group(1)
    literal = m.group(2) or m.group(3)
    rewritten_fragment = f"{col} ILIKE {literal}"

    if auto_rewrite:
        new_sql = re.sub(re.escape(original_fragment), rewritten_fragment, sql, count=1)
        return _RuleResult(
            triggered=True,
            rewritten=True,
            new_sql=new_sql,
            original_fragment=original_fragment,
            rewritten_fragment=rewritten_fragment,
        )
    return _RuleResult(
        triggered=True,
        rewritten=False,
        new_sql=sql,
        original_fragment=original_fragment,
        rewritten_fragment=rewritten_fragment,
    )


def _rule_sf_simple_case_to_iff(sql: str, auto_rewrite: bool) -> _RuleResult:
    """Rewrite binary CASE WHEN cond THEN x ELSE y END → IFF(cond, x, y)."""
    # Only match simple single-branch CASE (exactly one WHEN … ELSE … END).
    # Uses negative lookahead instead of character classes to avoid excluding
    # individual letters that appear in the keywords (e.g. 'e' in 'ELSE').
    pattern = (
        r"\bCASE\s+WHEN\s+"
        r"((?:(?!\bWHEN\b|\bELSE\b|\bEND\b).)+?)\s+"
        r"THEN\s+"
        r"((?:(?!\bELSE\b|\bEND\b).)+?)\s+"
        r"ELSE\s+"
        r"((?:(?!\bEND\b).)+?)\s+"
        r"END\b"
    )
    m = re.search(pattern, sql, re.IGNORECASE | re.DOTALL)
    if not m:
        return _RuleResult(triggered=False, rewritten=False, new_sql=sql)

    # Exclude multi-branch CASE (extra WHEN inside the same CASE block)
    full = m.group(0)
    inner = m.group(1) + m.group(2) + m.group(3)
    if re.search(r"\bWHEN\b", inner, re.IGNORECASE):
        return _RuleResult(triggered=False, rewritten=False, new_sql=sql)

    cond = m.group(1).strip()
    then_val = m.group(2).strip()
    else_val = m.group(3).strip()
    rewritten_fragment = f"IFF({cond}, {then_val}, {else_val})"

    if auto_rewrite:
        new_sql = sql.replace(full, rewritten_fragment, 1)
        return _RuleResult(
            triggered=True,
            rewritten=True,
            new_sql=new_sql,
            original_fragment=full,
            rewritten_fragment=rewritten_fragment,
        )
    return _RuleResult(
        triggered=True,
        rewritten=False,
        new_sql=sql,
        original_fragment=full,
        rewritten_fragment=rewritten_fragment,
    )


def _rule_sf_qualify_row_number(sql: str, auto_rewrite: bool) -> _RuleResult:
    """Rewrite outer-WHERE ROW_NUMBER() = 1 subquery → QUALIFY ROW_NUMBER() = 1."""
    # Pattern: SELECT ... FROM (SELECT ..., ROW_NUMBER() OVER (...) AS rn ...) subq WHERE subq.rn = 1
    # Also handles: WHERE rn = 1 or WHERE rn <= N
    pattern = (
        r"SELECT\s+(.*?)\s+FROM\s*\(\s*(SELECT\s+.*?ROW_NUMBER\s*\(\s*\)\s+OVER\s*\([^)]+\)\s+AS\s+(\w+).*?)\)\s+"
        r"(?:AS\s+)?\w+\s+WHERE\s+\3\s*(?:=|<=)\s*(\d+)"
    )
    m = re.search(pattern, sql, re.IGNORECASE | re.DOTALL)
    if not m:
        return _RuleResult(triggered=False, rewritten=False, new_sql=sql)

    outer_cols = m.group(1).strip()
    inner_sql = m.group(2).strip()
    rn_alias = m.group(3)
    rn_limit = m.group(4)

    # Strip the ROW_NUMBER alias column from the inner SELECT
    inner_cleaned = re.sub(
        r",?\s*ROW_NUMBER\s*\(\s*\)\s+OVER\s*\([^)]+\)\s+AS\s+" + re.escape(rn_alias),
        "",
        inner_sql,
        flags=re.IGNORECASE,
    ).strip()

    # Extract OVER clause for QUALIFY
    over_m = re.search(r"ROW_NUMBER\s*\(\s*\)\s+OVER\s*(\([^)]+\))", m.group(2), re.IGNORECASE)
    over_clause = over_m.group(1) if over_m else "()"

    rewritten_fragment = (
        f"{inner_cleaned}\nQUALIFY ROW_NUMBER() OVER {over_clause} <= {rn_limit}"
    )

    if auto_rewrite:
        new_sql = sql.replace(m.group(0), rewritten_fragment, 1)
        return _RuleResult(
            triggered=True,
            rewritten=True,
            new_sql=new_sql,
            original_fragment=m.group(0)[:120] + ("…" if len(m.group(0)) > 120 else ""),
            rewritten_fragment=rewritten_fragment[:120] + ("…" if len(rewritten_fragment) > 120 else ""),
        )
    return _RuleResult(
        triggered=True,
        rewritten=False,
        new_sql=sql,
        original_fragment=m.group(0)[:120],
    )


def _rule_sf_date_trunc_suggestion(sql: str, auto_rewrite: bool) -> _RuleResult:
    """Suggest DATE_TRUNC instead of TO_CHAR/DATE_FORMAT for date grouping."""
    m = _first_match(r"\b(?:TO_CHAR|DATE_FORMAT)\s*\(", sql)
    if not m:
        return _RuleResult(triggered=False, rewritten=False, new_sql=sql)
    return _RuleResult(
        triggered=True,
        rewritten=False,
        new_sql=sql,
        original_fragment=m.group(0).strip(),
    )


def _rule_sf_nvl_to_coalesce(sql: str, auto_rewrite: bool) -> _RuleResult:
    """Rewrite NVL(x, y) → COALESCE(x, y) for ANSI-standard consistency."""
    pattern = r"\bNVL\s*\("
    m = _first_match(pattern, sql)
    if not m:
        return _RuleResult(triggered=False, rewritten=False, new_sql=sql)

    if auto_rewrite:
        new_sql = re.sub(r"\bNVL\s*\(", "COALESCE(", sql, flags=re.IGNORECASE)
        return _RuleResult(
            triggered=True,
            rewritten=True,
            new_sql=new_sql,
            original_fragment="NVL(",
            rewritten_fragment="COALESCE(",
        )
    return _RuleResult(
        triggered=True,
        rewritten=False,
        new_sql=sql,
        original_fragment="NVL(",
        rewritten_fragment="COALESCE(",
    )


def _rule_sf_between_for_ranges(sql: str, auto_rewrite: bool) -> _RuleResult:
    """Rewrite col >= x AND col <= y → col BETWEEN x AND y for readability."""
    pattern = (
        r"(\w+(?:\.\w+)?)\s*>=\s*([^\s]+)\s+AND\s+\1\s*<=\s*([^\s,)]+)"
    )
    m = re.search(pattern, sql, re.IGNORECASE)
    if not m:
        return _RuleResult(triggered=False, rewritten=False, new_sql=sql)

    original_fragment = m.group(0)
    col = m.group(1)
    low = m.group(2)
    high = m.group(3)
    rewritten_fragment = f"{col} BETWEEN {low} AND {high}"

    if auto_rewrite:
        new_sql = sql.replace(original_fragment, rewritten_fragment, 1)
        return _RuleResult(
            triggered=True,
            rewritten=True,
            new_sql=new_sql,
            original_fragment=original_fragment,
            rewritten_fragment=rewritten_fragment,
        )
    return _RuleResult(
        triggered=True,
        rewritten=False,
        new_sql=sql,
        original_fragment=original_fragment,
        rewritten_fragment=rewritten_fragment,
    )


def _rule_sf_cluster_key_hint(sql: str, auto_rewrite: bool) -> _RuleResult:
    """Add an informational note when WHERE filters on high-cardinality date columns."""
    m = re.search(
        r"\bWHERE\b.+?\b(created_at|updated_at|event_date|order_date|transaction_date)\b",
        sql, re.IGNORECASE | re.DOTALL,
    )
    if not m:
        return _RuleResult(triggered=False, rewritten=False, new_sql=sql)
    return _RuleResult(
        triggered=True,
        rewritten=False,
        new_sql=sql,
        original_fragment=m.group(1),
    )


# ---------------------------------------------------------------------------
# Redshift-specific rules
# ---------------------------------------------------------------------------

def _rule_rs_ilike_to_lower_like(sql: str, auto_rewrite: bool) -> _RuleResult:
    """Rewrite ILIKE → LOWER(col) LIKE LOWER('...') for Redshift compatibility."""
    pattern = r"(\w+(?:\.\w+)?)\s+ILIKE\s+('[^']*')"
    m = re.search(pattern, sql, re.IGNORECASE)
    if not m:
        return _RuleResult(triggered=False, rewritten=False, new_sql=sql)

    original_fragment = m.group(0)
    col = m.group(1)
    literal = m.group(2)
    rewritten_fragment = f"LOWER({col}) LIKE LOWER({literal})"

    if auto_rewrite:
        new_sql = re.sub(
            pattern,
            lambda mo: f"LOWER({mo.group(1)}) LIKE LOWER({mo.group(2)})",
            sql,
            flags=re.IGNORECASE,
        )
        return _RuleResult(
            triggered=True,
            rewritten=True,
            new_sql=new_sql,
            original_fragment=original_fragment,
            rewritten_fragment=rewritten_fragment,
        )
    return _RuleResult(
        triggered=True,
        rewritten=False,
        new_sql=sql,
        original_fragment=original_fragment,
        rewritten_fragment=rewritten_fragment,
    )


def _rule_rs_approximate_count_distinct(sql: str, auto_rewrite: bool) -> _RuleResult:
    """Rewrite COUNT(DISTINCT col) → APPROXIMATE COUNT(DISTINCT col) for Redshift."""
    pattern = r"\bCOUNT\s*\(\s*DISTINCT\s+(\w+(?:\.\w+)?)\s*\)"
    m = re.search(pattern, sql, re.IGNORECASE)
    if not m:
        return _RuleResult(triggered=False, rewritten=False, new_sql=sql)

    original_fragment = m.group(0)
    rewritten_fragment = f"APPROXIMATE COUNT(DISTINCT {m.group(1)})"

    if auto_rewrite:
        new_sql = re.sub(
            pattern,
            lambda mo: f"APPROXIMATE COUNT(DISTINCT {mo.group(1)})",
            sql,
            flags=re.IGNORECASE,
        )
        return _RuleResult(
            triggered=True,
            rewritten=True,
            new_sql=new_sql,
            original_fragment=original_fragment,
            rewritten_fragment=rewritten_fragment,
        )
    return _RuleResult(
        triggered=True,
        rewritten=False,
        new_sql=sql,
        original_fragment=original_fragment,
        rewritten_fragment=rewritten_fragment,
    )


def _rule_rs_distkey_sortkey_hint(sql: str, auto_rewrite: bool) -> _RuleResult:
    """Add informational hint about DISTKEY/SORTKEY for JOIN columns."""
    join_m = re.search(
        r"\bJOIN\s+(\S+)\s+(?:(?:AS\s+)?\w+\s+)?ON\s+(\S+)\s*=\s*(\S+)",
        sql, re.IGNORECASE,
    )
    if not join_m:
        return _RuleResult(triggered=False, rewritten=False, new_sql=sql)

    join_col_right = join_m.group(3).split(".")[-1]
    hint = (
        f"-- Redshift hint: consider DISTKEY({join_col_right}) on joined tables "
        f"and SORTKEY on frequently filtered columns\n"
    )
    if auto_rewrite:
        new_sql = hint + sql
        return _RuleResult(
            triggered=True,
            rewritten=True,
            new_sql=new_sql,
            original_fragment=join_m.group(0),
            rewritten_fragment=hint.strip(),
        )
    return _RuleResult(
        triggered=True,
        rewritten=False,
        new_sql=sql,
        original_fragment=join_m.group(0),
        rewritten_fragment=hint.strip(),
    )


def _rule_rs_qualify_unsupported(sql: str, auto_rewrite: bool) -> _RuleResult:
    """Warn that QUALIFY is not supported in Redshift; suggest subquery workaround."""
    if not re.search(r"\bQUALIFY\b", sql, re.IGNORECASE):
        return _RuleResult(triggered=False, rewritten=False, new_sql=sql)

    # Extract QUALIFY clause
    m = re.search(r"\bQUALIFY\b\s+(.+?)(?:;|$)", sql, re.IGNORECASE | re.DOTALL)
    qualify_expr = m.group(1).strip() if m else "ROW_NUMBER() OVER (...)"

    if auto_rewrite:
        # Wrap the query as a CTE and move QUALIFY to an outer WHERE
        qualify_stripped = re.sub(r"\bQUALIFY\b\s+.+$", "", sql, flags=re.IGNORECASE | re.DOTALL).strip()
        rewritten_fragment = (
            f"SELECT * FROM (\n  {qualify_stripped}\n) _q\nWHERE {qualify_expr}"
        )
        return _RuleResult(
            triggered=True,
            rewritten=True,
            new_sql=rewritten_fragment,
            original_fragment=f"QUALIFY {qualify_expr[:60]}",
            rewritten_fragment=f"WHERE {qualify_expr[:60]} (outer subquery)",
        )
    return _RuleResult(
        triggered=True,
        rewritten=False,
        new_sql=sql,
        original_fragment=f"QUALIFY {qualify_expr[:60] if m else ''}",
    )


def _rule_rs_nvl_alias(sql: str, auto_rewrite: bool) -> _RuleResult:
    """Rewrite NVL(x, y) → COALESCE(x, y) for Redshift ANSI compliance."""
    pattern = r"\bNVL\s*\("
    m = _first_match(pattern, sql)
    if not m:
        return _RuleResult(triggered=False, rewritten=False, new_sql=sql)

    if auto_rewrite:
        new_sql = re.sub(r"\bNVL\s*\(", "COALESCE(", sql, flags=re.IGNORECASE)
        return _RuleResult(
            triggered=True,
            rewritten=True,
            new_sql=new_sql,
            original_fragment="NVL(",
            rewritten_fragment="COALESCE(",
        )
    return _RuleResult(triggered=True, rewritten=False, new_sql=sql, original_fragment="NVL(")


def _rule_rs_between_ranges(sql: str, auto_rewrite: bool) -> _RuleResult:
    """Rewrite col >= x AND col <= y → col BETWEEN x AND y for Redshift sort-key pruning."""
    return _rule_sf_between_for_ranges(sql, auto_rewrite)


# ---------------------------------------------------------------------------
# Rule registries
# ---------------------------------------------------------------------------

_COMMON_RULES: list[_OptimizationRule] = [
    _OptimizationRule(
        rule_id="common_select_star",
        description=(
            "SELECT * retrieves all columns, preventing column pruning and increasing I/O. "
            "Specify explicit column names."
        ),
        severity=OptimizationSeverity.WARNING,
        apply=_rule_select_star,
    ),
    _OptimizationRule(
        rule_id="common_redundant_distinct",
        description=(
            "DISTINCT is redundant when GROUP BY already guarantees one row per group. "
            "Removed DISTINCT to reduce sort overhead."
        ),
        severity=OptimizationSeverity.INFO,
        apply=_rule_redundant_distinct,
    ),
    _OptimizationRule(
        rule_id="common_not_in_subquery",
        description=(
            "NOT IN with a subquery can produce unexpected results on NULLs and forces a "
            "full subquery scan. Rewritten to NOT EXISTS with a correlated subquery."
        ),
        severity=OptimizationSeverity.WARNING,
        apply=_rule_not_in_subquery,
    ),
    _OptimizationRule(
        rule_id="common_leading_wildcard",
        description=(
            "LIKE '%...' patterns with a leading wildcard prevent partition/micro-partition "
            "pruning and index use. Consider CONTAINS(), full-text search, or a suffix index."
        ),
        severity=OptimizationSeverity.WARNING,
        apply=_rule_leading_wildcard,
    ),
    _OptimizationRule(
        rule_id="common_or_union_suggestion",
        description=(
            "OR conditions across different columns can prevent efficient predicate pushdown. "
            "Consider rewriting as UNION ALL with one condition per branch."
        ),
        severity=OptimizationSeverity.INFO,
        apply=_rule_or_union_suggestion,
    ),
    _OptimizationRule(
        rule_id="common_count_distinct",
        description=(
            "COUNT(DISTINCT ...) requires a full sort/hash of the column. For large tables, "
            "consider HyperLogLog approximations (APPROX_COUNT_DISTINCT / APPROXIMATE COUNT(DISTINCT))."
        ),
        severity=OptimizationSeverity.INFO,
        apply=_rule_count_distinct_large,
    ),
    _OptimizationRule(
        rule_id="common_scalar_subquery_select",
        description=(
            "Scalar correlated subqueries in the SELECT list are executed once per row (N+1). "
            "Rewrite using a LEFT JOIN or window function."
        ),
        severity=OptimizationSeverity.WARNING,
        apply=_rule_scalar_subquery_in_select,
    ),
]

_SNOWFLAKE_RULES: list[_OptimizationRule] = [
    _OptimizationRule(
        rule_id="sf_lower_like_to_ilike",
        description=(
            "LOWER(col) LIKE LOWER('...') disables micro-partition pruning. "
            "Replaced with the native Snowflake ILIKE operator."
        ),
        severity=OptimizationSeverity.WARNING,
        apply=_rule_sf_lower_like_to_ilike,
    ),
    _OptimizationRule(
        rule_id="sf_simple_case_to_iff",
        description=(
            "Single-branch CASE WHEN … ELSE … END can be simplified to Snowflake's IFF() "
            "for clarity and a minor parse-overhead reduction."
        ),
        severity=OptimizationSeverity.INFO,
        apply=_rule_sf_simple_case_to_iff,
    ),
    _OptimizationRule(
        rule_id="sf_qualify_row_number",
        description=(
            "Outer-WHERE ROW_NUMBER() = 1 subquery pattern rewritten using Snowflake's "
            "native QUALIFY clause, removing the extra subquery layer."
        ),
        severity=OptimizationSeverity.WARNING,
        apply=_rule_sf_qualify_row_number,
    ),
    _OptimizationRule(
        rule_id="sf_date_trunc_suggestion",
        description=(
            "TO_CHAR / DATE_FORMAT for date grouping prevents micro-partition pruning. "
            "Use DATE_TRUNC('month', col) to keep the column as a DATE type."
        ),
        severity=OptimizationSeverity.INFO,
        apply=_rule_sf_date_trunc_suggestion,
    ),
    _OptimizationRule(
        rule_id="sf_nvl_to_coalesce",
        description=(
            "NVL() is a non-standard alias. Replaced with COALESCE() for ANSI compliance "
            "and compatibility with all Snowflake contexts."
        ),
        severity=OptimizationSeverity.INFO,
        apply=_rule_sf_nvl_to_coalesce,
    ),
    _OptimizationRule(
        rule_id="sf_between_ranges",
        description=(
            "col >= x AND col <= y rewritten as col BETWEEN x AND y. "
            "Snowflake can leverage cluster key pruning more efficiently with BETWEEN."
        ),
        severity=OptimizationSeverity.INFO,
        apply=_rule_sf_between_for_ranges,
    ),
    _OptimizationRule(
        rule_id="sf_cluster_key_hint",
        description=(
            "Query filters on a date/timestamp column that is a common cluster key candidate. "
            "Ensure the table is clustered on this column for optimal micro-partition pruning."
        ),
        severity=OptimizationSeverity.INFO,
        apply=_rule_sf_cluster_key_hint,
    ),
]

_REDSHIFT_RULES: list[_OptimizationRule] = [
    _OptimizationRule(
        rule_id="rs_ilike_to_lower_like",
        description=(
            "ILIKE is not supported in Redshift. "
            "Rewritten as LOWER(col) LIKE LOWER('...') for case-insensitive matching."
        ),
        severity=OptimizationSeverity.ERROR,
        apply=_rule_rs_ilike_to_lower_like,
    ),
    _OptimizationRule(
        rule_id="rs_approximate_count_distinct",
        description=(
            "COUNT(DISTINCT col) on large Redshift tables is expensive. "
            "Rewritten to APPROXIMATE COUNT(DISTINCT col) using HyperLogLog (±2% error)."
        ),
        severity=OptimizationSeverity.INFO,
        apply=_rule_rs_approximate_count_distinct,
    ),
    _OptimizationRule(
        rule_id="rs_distkey_sortkey_hint",
        description=(
            "JOIN detected. Added Redshift DISTKEY/SORTKEY hint comment. "
            "Co-locating rows on the join key via DISTKEY eliminates redistribution."
        ),
        severity=OptimizationSeverity.INFO,
        apply=_rule_rs_distkey_sortkey_hint,
    ),
    _OptimizationRule(
        rule_id="rs_qualify_unsupported",
        description=(
            "QUALIFY is not supported in Redshift. "
            "Rewritten as a subquery with the window-function filter in the outer WHERE clause."
        ),
        severity=OptimizationSeverity.ERROR,
        apply=_rule_rs_qualify_unsupported,
    ),
    _OptimizationRule(
        rule_id="rs_nvl_to_coalesce",
        description=(
            "NVL() is non-standard. Replaced with COALESCE() for Redshift ANSI compliance."
        ),
        severity=OptimizationSeverity.INFO,
        apply=_rule_rs_nvl_alias,
    ),
    _OptimizationRule(
        rule_id="rs_between_ranges",
        description=(
            "col >= x AND col <= y rewritten as col BETWEEN x AND y for Redshift "
            "SORTKEY range-scan efficiency."
        ),
        severity=OptimizationSeverity.INFO,
        apply=_rule_rs_between_ranges,
    ),
]


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class SQLOptimizationEngine:
    """Rewrite SQL queries according to Snowflake and Redshift best practices."""

    _DIALECT_RULES: dict[SQLDialect, list[_OptimizationRule]] = {
        SQLDialect.SNOWFLAKE: _SNOWFLAKE_RULES,
        SQLDialect.REDSHIFT: _REDSHIFT_RULES,
    }

    def optimize(self, request: SQLOptimizationRequest) -> SQLOptimizationResponse:
        """Run all applicable rules and return an optimization report."""
        sql = request.sql.strip()
        rules = _COMMON_RULES + self._DIALECT_RULES[request.dialect]

        applied: list[AppliedRule] = []
        rewrite_count = 0

        for rule in rules:
            result = rule.apply(sql, request.auto_rewrite)
            if not result.triggered:
                continue

            applied.append(
                AppliedRule(
                    rule_id=rule.rule_id,
                    description=rule.description,
                    severity=rule.severity,
                    rewritten=result.rewritten,
                    original_fragment=result.original_fragment,
                    rewritten_fragment=result.rewritten_fragment,
                )
            )

            if result.rewritten:
                sql = result.new_sql
                rewrite_count += 1

        warning_count = sum(
            1 for a in applied
            if a.severity in (OptimizationSeverity.WARNING, OptimizationSeverity.ERROR)
            and not a.rewritten
        )

        return SQLOptimizationResponse(
            original_sql=request.sql.strip(),
            optimized_sql=sql,
            dialect=request.dialect,
            rules_applied=applied,
            rewrite_count=rewrite_count,
            warning_count=warning_count,
            fully_optimized=warning_count == 0,
        )
