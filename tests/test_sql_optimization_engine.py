"""Tests for SQLOptimizationEngine covering Snowflake and Redshift rules."""
from __future__ import annotations

import pytest

from app.schemas.optimization import SQLDialect, SQLOptimizationRequest
from app.services.sql_optimization_engine import SQLOptimizationEngine


@pytest.fixture()
def engine() -> SQLOptimizationEngine:
    return SQLOptimizationEngine()


def _optimize(engine: SQLOptimizationEngine, sql: str, dialect: SQLDialect = SQLDialect.SNOWFLAKE, auto_rewrite: bool = True):
    return engine.optimize(SQLOptimizationRequest(sql=sql, dialect=dialect, auto_rewrite=auto_rewrite))


# ---------------------------------------------------------------------------
# Common rules
# ---------------------------------------------------------------------------

class TestSelectStar:
    def test_warns_on_select_star(self, engine):
        result = _optimize(engine, "SELECT * FROM orders")
        ids = [r.rule_id for r in result.rules_applied]
        assert "common_select_star" in ids

    def test_no_warning_on_explicit_columns(self, engine):
        result = _optimize(engine, "SELECT id, name FROM orders")
        ids = [r.rule_id for r in result.rules_applied]
        assert "common_select_star" not in ids

    def test_sql_unchanged_cannot_auto_rewrite(self, engine):
        sql = "SELECT * FROM orders"
        result = _optimize(engine, sql)
        assert result.optimized_sql == sql


class TestRedundantDistinct:
    def test_removes_distinct_with_group_by(self, engine):
        sql = "SELECT DISTINCT customer_id FROM orders GROUP BY customer_id"
        result = _optimize(engine, sql)
        assert "SELECT DISTINCT" not in result.optimized_sql
        ids = [r.rule_id for r in result.rules_applied]
        assert "common_redundant_distinct" in ids

    def test_keeps_distinct_without_group_by(self, engine):
        sql = "SELECT DISTINCT customer_id FROM orders"
        result = _optimize(engine, sql)
        assert "DISTINCT" in result.optimized_sql

    def test_no_rewrite_when_auto_rewrite_false(self, engine):
        sql = "SELECT DISTINCT customer_id FROM orders GROUP BY customer_id"
        result = _optimize(engine, sql, auto_rewrite=False)
        assert "DISTINCT" in result.optimized_sql
        rule = next(r for r in result.rules_applied if r.rule_id == "common_redundant_distinct")
        assert rule.rewritten is False


class TestNotInSubquery:
    def test_rewrites_not_in_to_not_exists(self, engine):
        sql = "SELECT id FROM orders WHERE customer_id NOT IN (SELECT id FROM customers)"
        result = _optimize(engine, sql)
        assert "NOT EXISTS" in result.optimized_sql
        assert "NOT IN" not in result.optimized_sql

    def test_rule_triggered(self, engine):
        sql = "SELECT id FROM orders WHERE customer_id NOT IN (SELECT id FROM customers)"
        result = _optimize(engine, sql)
        ids = [r.rule_id for r in result.rules_applied]
        assert "common_not_in_subquery" in ids


class TestLeadingWildcard:
    def test_warns_on_leading_wildcard(self, engine):
        sql = "SELECT name FROM products WHERE name LIKE '%widget'"
        result = _optimize(engine, sql)
        ids = [r.rule_id for r in result.rules_applied]
        assert "common_leading_wildcard" in ids

    def test_no_warning_trailing_only(self, engine):
        sql = "SELECT name FROM products WHERE name LIKE 'widget%'"
        result = _optimize(engine, sql)
        ids = [r.rule_id for r in result.rules_applied]
        assert "common_leading_wildcard" not in ids


class TestCountDistinct:
    def test_flags_count_distinct(self, engine):
        sql = "SELECT COUNT(DISTINCT user_id) FROM events"
        result = _optimize(engine, sql)
        ids = [r.rule_id for r in result.rules_applied]
        assert "common_count_distinct" in ids

    def test_no_flag_plain_count(self, engine):
        sql = "SELECT COUNT(user_id) FROM events"
        result = _optimize(engine, sql)
        ids = [r.rule_id for r in result.rules_applied]
        assert "common_count_distinct" not in ids


class TestScalarSubqueryInSelect:
    def test_flags_scalar_subquery(self, engine):
        sql = "SELECT id, (SELECT name FROM users WHERE users.id = orders.user_id) FROM orders"
        result = _optimize(engine, sql)
        ids = [r.rule_id for r in result.rules_applied]
        assert "common_scalar_subquery_select" in ids


# ---------------------------------------------------------------------------
# Snowflake-specific rules
# ---------------------------------------------------------------------------

class TestSnowflakeLowerLikeToIlike:
    def test_rewrites_lower_like_lower(self, engine):
        sql = "SELECT * FROM products WHERE LOWER(name) LIKE LOWER('%widget%')"
        result = _optimize(engine, sql)
        assert "ILIKE" in result.optimized_sql
        assert "LOWER" not in result.optimized_sql

    def test_rewrites_upper_like(self, engine):
        sql = "SELECT id FROM t WHERE UPPER(col) LIKE UPPER('TEST%')"
        result = _optimize(engine, sql)
        assert "ILIKE" in result.optimized_sql

    def test_rule_triggered(self, engine):
        sql = "SELECT id FROM t WHERE LOWER(col) LIKE LOWER('val%')"
        result = _optimize(engine, sql)
        ids = [r.rule_id for r in result.rules_applied]
        assert "sf_lower_like_to_ilike" in ids


class TestSnowflakeSimpleCaseToIff:
    def test_rewrites_simple_case(self, engine):
        sql = "SELECT id, CASE WHEN active = 1 THEN 'yes' ELSE 'no' END AS status FROM users"
        result = _optimize(engine, sql)
        assert "IFF(" in result.optimized_sql
        assert "CASE WHEN" not in result.optimized_sql

    def test_does_not_rewrite_multi_branch_case(self, engine):
        sql = (
            "SELECT CASE WHEN score > 90 THEN 'A' "
            "WHEN score > 80 THEN 'B' "
            "ELSE 'C' END FROM grades"
        )
        result = _optimize(engine, sql)
        # Multi-branch CASE must NOT be touched
        assert "IFF(" not in result.optimized_sql

    def test_rule_id_in_applied(self, engine):
        sql = "SELECT CASE WHEN x = 1 THEN 'a' ELSE 'b' END FROM t"
        result = _optimize(engine, sql)
        ids = [r.rule_id for r in result.rules_applied]
        assert "sf_simple_case_to_iff" in ids


class TestSnowflakeNvlToCoalesce:
    def test_rewrites_nvl(self, engine):
        sql = "SELECT NVL(email, 'unknown') FROM users"
        result = _optimize(engine, sql)
        assert "COALESCE(" in result.optimized_sql
        assert "NVL(" not in result.optimized_sql

    def test_rule_triggered(self, engine):
        sql = "SELECT NVL(col, 0) FROM t"
        result = _optimize(engine, sql)
        ids = [r.rule_id for r in result.rules_applied]
        assert "sf_nvl_to_coalesce" in ids


class TestSnowflakeBetweenRanges:
    def test_rewrites_range_to_between(self, engine):
        sql = "SELECT id FROM sales WHERE amount >= 100 AND amount <= 500"
        result = _optimize(engine, sql)
        assert "BETWEEN" in result.optimized_sql
        assert ">=" not in result.optimized_sql

    def test_rule_triggered(self, engine):
        sql = "SELECT id FROM t WHERE qty >= 10 AND qty <= 20"
        result = _optimize(engine, sql)
        ids = [r.rule_id for r in result.rules_applied]
        assert "sf_between_ranges" in ids


class TestSnowflakeDateTruncSuggestion:
    def test_flags_to_char(self, engine):
        sql = "SELECT TO_CHAR(created_at, 'YYYY-MM') FROM orders GROUP BY 1"
        result = _optimize(engine, sql)
        ids = [r.rule_id for r in result.rules_applied]
        assert "sf_date_trunc_suggestion" in ids

    def test_flags_date_format(self, engine):
        sql = "SELECT DATE_FORMAT(order_date, '%Y-%m') FROM orders"
        result = _optimize(engine, sql)
        ids = [r.rule_id for r in result.rules_applied]
        assert "sf_date_trunc_suggestion" in ids


class TestSnowflakeClusterKeyHint:
    def test_hints_on_date_column(self, engine):
        sql = "SELECT id FROM orders WHERE created_at > '2024-01-01'"
        result = _optimize(engine, sql)
        ids = [r.rule_id for r in result.rules_applied]
        assert "sf_cluster_key_hint" in ids

    def test_no_hint_when_no_date_column(self, engine):
        sql = "SELECT id FROM orders WHERE status = 'shipped'"
        result = _optimize(engine, sql)
        ids = [r.rule_id for r in result.rules_applied]
        assert "sf_cluster_key_hint" not in ids


# ---------------------------------------------------------------------------
# Redshift-specific rules
# ---------------------------------------------------------------------------

class TestRedshiftIlikeToLowerLike:
    def test_rewrites_ilike(self, engine):
        sql = "SELECT id FROM products WHERE name ILIKE '%widget%'"
        result = _optimize(engine, sql, dialect=SQLDialect.REDSHIFT)
        assert "ILIKE" not in result.optimized_sql
        assert "LOWER(" in result.optimized_sql

    def test_rule_triggered(self, engine):
        sql = "SELECT id FROM t WHERE col ILIKE 'val%'"
        result = _optimize(engine, sql, dialect=SQLDialect.REDSHIFT)
        ids = [r.rule_id for r in result.rules_applied]
        assert "rs_ilike_to_lower_like" in ids


class TestRedshiftApproximateCountDistinct:
    def test_rewrites_count_distinct(self, engine):
        sql = "SELECT COUNT(DISTINCT user_id) FROM events"
        result = _optimize(engine, sql, dialect=SQLDialect.REDSHIFT)
        assert "APPROXIMATE COUNT(DISTINCT" in result.optimized_sql

    def test_rule_triggered(self, engine):
        sql = "SELECT COUNT(DISTINCT order_id) FROM orders"
        result = _optimize(engine, sql, dialect=SQLDialect.REDSHIFT)
        ids = [r.rule_id for r in result.rules_applied]
        assert "rs_approximate_count_distinct" in ids


class TestRedshiftDistkeySortkeyHint:
    def test_adds_hint_comment_on_join(self, engine):
        sql = "SELECT o.id FROM orders o JOIN customers c ON o.customer_id = c.id"
        result = _optimize(engine, sql, dialect=SQLDialect.REDSHIFT)
        assert "Redshift hint" in result.optimized_sql

    def test_rule_triggered(self, engine):
        sql = "SELECT o.id FROM orders o JOIN customers c ON o.customer_id = c.id"
        result = _optimize(engine, sql, dialect=SQLDialect.REDSHIFT)
        ids = [r.rule_id for r in result.rules_applied]
        assert "rs_distkey_sortkey_hint" in ids


class TestRedshiftQualifyUnsupported:
    def test_rewrites_qualify(self, engine):
        sql = (
            "SELECT id, ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY created_at DESC) AS rn "
            "FROM events QUALIFY rn = 1"
        )
        result = _optimize(engine, sql, dialect=SQLDialect.REDSHIFT)
        assert "QUALIFY" not in result.optimized_sql
        assert "WHERE" in result.optimized_sql

    def test_rule_triggered(self, engine):
        sql = "SELECT id FROM t QUALIFY ROW_NUMBER() OVER (PARTITION BY x ORDER BY y) = 1"
        result = _optimize(engine, sql, dialect=SQLDialect.REDSHIFT)
        ids = [r.rule_id for r in result.rules_applied]
        assert "rs_qualify_unsupported" in ids


class TestRedshiftNvlToCoalesce:
    def test_rewrites_nvl(self, engine):
        sql = "SELECT NVL(score, 0) FROM results"
        result = _optimize(engine, sql, dialect=SQLDialect.REDSHIFT)
        assert "COALESCE(" in result.optimized_sql

    def test_rule_triggered(self, engine):
        sql = "SELECT NVL(col, '') FROM t"
        result = _optimize(engine, sql, dialect=SQLDialect.REDSHIFT)
        ids = [r.rule_id for r in result.rules_applied]
        assert "rs_nvl_to_coalesce" in ids


class TestRedshiftBetweenRanges:
    def test_rewrites_range_to_between(self, engine):
        sql = "SELECT id FROM sales WHERE amount >= 100 AND amount <= 500"
        result = _optimize(engine, sql, dialect=SQLDialect.REDSHIFT)
        assert "BETWEEN" in result.optimized_sql


# ---------------------------------------------------------------------------
# Response-level assertions
# ---------------------------------------------------------------------------

class TestResponseMeta:
    def test_rewrite_count_increments(self, engine):
        # NVL -> COALESCE + BETWEEN rewrite
        sql = "SELECT NVL(x, 0) FROM t WHERE qty >= 10 AND qty <= 20"
        result = _optimize(engine, sql)
        assert result.rewrite_count >= 2

    def test_fully_optimized_when_no_warnings(self, engine):
        sql = "SELECT id, name FROM users WHERE status = 'active'"
        result = _optimize(engine, sql)
        assert result.fully_optimized is True

    def test_not_fully_optimized_with_select_star(self, engine):
        sql = "SELECT * FROM users"
        result = _optimize(engine, sql)
        assert result.fully_optimized is False

    def test_original_sql_preserved(self, engine):
        sql = "SELECT NVL(col, 0) FROM t"
        result = _optimize(engine, sql)
        assert result.original_sql == sql

    def test_dialect_echoed(self, engine):
        sql = "SELECT id FROM t"
        result = _optimize(engine, sql, dialect=SQLDialect.REDSHIFT)
        assert result.dialect == SQLDialect.REDSHIFT

    def test_analysis_only_no_rewrites(self, engine):
        sql = "SELECT NVL(col, 0) FROM t WHERE qty >= 1 AND qty <= 10"
        result = _optimize(engine, sql, auto_rewrite=False)
        assert result.rewrite_count == 0
        assert result.optimized_sql == sql
