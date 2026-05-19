"""Tests for natural language query parsing."""

from datetime import date

from app.services.nl_query_parser import NaturalLanguageQueryParser


def test_extracts_metrics_dimensions_aggregation_filters_and_date_range():
    parser = NaturalLanguageQueryParser()

    query = (
        "What is the total revenue by region and product category "
        "where status = active in west last 30 days"
    )

    result = parser.parse(query, reference_date=date(2026, 5, 19))

    assert "revenue" in result.metrics
    assert "region" in result.dimensions
    assert "product" in result.dimensions
    assert "sum" in result.aggregations

    assert any(f.field == "status" and f.operator == "=" and f.value == "active" for f in result.filters)
    assert any(f.value == "west" for f in result.filters)

    assert result.date_range is not None
    assert result.date_range.start_date == "2026-04-20"
    assert result.date_range.end_date == "2026-05-19"


def test_extracts_average_and_explicit_date_interval():
    parser = NaturalLanguageQueryParser()

    query = "Show average order count by channel from 2026-01-01 to 2026-03-31"
    result = parser.parse(query)

    assert "orders" in result.metrics
    assert "avg" in result.aggregations
    assert "channel" in result.dimensions

    assert result.date_range is not None
    assert result.date_range.start_date == "2026-01-01"
    assert result.date_range.end_date == "2026-03-31"


def test_extracts_this_month_range_and_count_aggregation():
    parser = NaturalLanguageQueryParser()
    query = "How many users by customer tier this month"

    result = parser.parse(query, reference_date=date(2026, 5, 19))

    assert "users" in result.metrics
    assert "count" in result.aggregations
    assert "customer_segment" in result.dimensions

    assert result.date_range is not None
    assert result.date_range.start_date == "2026-05-01"
    assert result.date_range.end_date == "2026-05-19"
    assert result.date_range.granularity == "month"


def test_extracts_last_year_range():
    parser = NaturalLanguageQueryParser()
    query = "Give me max profit by region for enterprise customers last year"

    result = parser.parse(query, reference_date=date(2026, 5, 19))

    assert "profit" in result.metrics
    assert "max" in result.aggregations
    assert "region" in result.dimensions
    assert result.date_range is not None
    assert result.date_range.start_date == "2025-01-01"
    assert result.date_range.end_date == "2025-12-31"