"""Natural language query parsing for business questions."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta


@dataclass
class FilterCondition:
    """Represents a normalized filter expression."""

    field: str
    operator: str
    value: str


@dataclass
class DateRange:
    """Represents an extracted date range."""

    start_date: str
    end_date: str
    granularity: str = "day"


@dataclass
class ParsedQuery:
    """Structured output for parsed natural language questions."""

    metrics: list[str] = field(default_factory=list)
    dimensions: list[str] = field(default_factory=list)
    filters: list[FilterCondition] = field(default_factory=list)
    aggregations: list[str] = field(default_factory=list)
    date_range: DateRange | None = None
    original_query: str = ""
    memory_applied: bool = False


class NaturalLanguageQueryParser:
    """Rule-based parser for extracting analytics query components."""

    METRIC_KEYWORDS = {
        "revenue": ["revenue", "sales", "gmv", "income"],
        "profit": ["profit", "margin"],
        "orders": ["orders", "order count", "purchases", "transactions"],
        "users": ["users", "customers", "clients", "buyers"],
        "cost": ["cost", "expense", "spend"],
        "quantity": ["quantity", "units", "volume"],
    }

    DIMENSION_KEYWORDS = {
        "region": ["region", "country", "state", "city", "market"],
        "product": ["product", "category", "sku", "item"],
        "channel": ["channel", "source", "campaign"],
        "customer_segment": ["segment", "customer type", "tier"],
        "date": ["day", "date", "week", "month", "quarter", "year"],
    }

    AGGREGATION_KEYWORDS = {
        "sum": ["sum", "total", "overall"],
        "avg": ["average", "avg", "mean"],
        "count": ["count", "number of", "how many"],
        "min": ["minimum", "lowest", "min"],
        "max": ["maximum", "highest", "max"],
    }

    FILTER_PATTERNS = [
        re.compile(
            (
                r"(?:\bwhere\b|\band\b)\s*"
                r"(?P<field>[a-z_][a-z_ ]*?)\s*"
                r"(?P<op>>=|<=|!=|=|>|<)\s*"
                r"(?P<value>[\w\-\.]+)"
                r"(?=\s+(?:and|or|in|for|last|this|from|between)\b|$)"
            ),
            flags=re.IGNORECASE,
        ),
        re.compile(
            (
                r"(?:\bwhere\b|\band\b)\s*"
                r"(?P<field>[a-z_][a-z_ ]*?)\s+"
                r"(?:is|equals|equal to)\s+"
                r"(?P<value>[a-z0-9_\- ]+)"
                r"(?=\s+(?:and|or|in|for|last|this|from|between)\b|$)"
            ),
            flags=re.IGNORECASE,
        ),
        re.compile(
            (
                r"\b(?P<field>[a-z_][a-z0-9_]*)\s*"
                r"(?P<op>>=|<=|!=|=|>|<)\s*"
                r"(?P<value>[\w\-\.]+)"
            ),
            flags=re.IGNORECASE,
        ),
    ]

    def parse(
        self,
        question: str,
        reference_date: date | None = None,
        prior_queries: list[ParsedQuery] | None = None,
    ) -> ParsedQuery:
        """Parse a natural language question into structured query parts."""
        normalized = self._normalize_text(question)
        reference = reference_date or date.today()

        parsed = ParsedQuery(original_query=question)
        parsed.metrics = self._extract_metrics(normalized)
        parsed.dimensions = self._extract_dimensions(normalized)
        parsed.aggregations = self._extract_aggregations(normalized)
        parsed.filters = self._extract_filters(normalized)
        parsed.date_range = self._extract_date_range(normalized, reference)

        if prior_queries:
            parsed = self._merge_with_conversation_memory(
                parsed=parsed,
                normalized_query=normalized,
                prior_queries=prior_queries,
            )

        return parsed

    @staticmethod
    def _normalize_text(text: str) -> str:
        normalized = text.lower().strip()
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized

    def _extract_metrics(self, text: str) -> list[str]:
        metrics: list[str] = []
        for canonical, keywords in self.METRIC_KEYWORDS.items():
            if any(keyword in text for keyword in keywords):
                metrics.append(canonical)
        return metrics

    def _extract_dimensions(self, text: str) -> list[str]:
        dimensions: list[str] = []

        grouping_matches = re.findall(r"(?:by|per)\s+([a-z_ ]+?)(?:\bwhere\b|\bfor\b|\bin\b|$)", text)
        for match in grouping_matches:
            tokens = [token.strip() for token in re.split(r",| and ", match) if token.strip()]
            for token in tokens:
                canonical = self._canonical_dimension(token)
                if canonical and canonical not in dimensions:
                    dimensions.append(canonical)

        for canonical, keywords in self.DIMENSION_KEYWORDS.items():
            if any(keyword in text for keyword in keywords) and canonical not in dimensions:
                dimensions.append(canonical)

        return dimensions

    def _extract_aggregations(self, text: str) -> list[str]:
        aggregations: list[str] = []
        for canonical, keywords in self.AGGREGATION_KEYWORDS.items():
            if any(keyword in text for keyword in keywords):
                aggregations.append(canonical)
        return aggregations

    def _extract_filters(self, text: str) -> list[FilterCondition]:
        filters: list[FilterCondition] = []

        for pattern in self.FILTER_PATTERNS:
            for match in pattern.finditer(text):
                field = self._normalize_field(match.group("field"))
                value = match.group("value").strip()
                operator = match.groupdict().get("op") or "="
                if field and value:
                    filters.append(FilterCondition(field=field, operator=operator, value=value))

        contextual_patterns = [
            re.compile(r"\bfor\s+([a-z0-9_\- ]+)", flags=re.IGNORECASE),
            re.compile(r"\bin\s+([a-z0-9_\- ]+)", flags=re.IGNORECASE),
        ]

        for pattern in contextual_patterns:
            for match in pattern.finditer(text):
                phrase = match.group(1).strip()
                phrase = re.split(r"\b(last|this|today|yesterday|from|between)\b", phrase)[0].strip()
                if not phrase or phrase in {"total", "all"}:
                    continue

                inferred_field = self._infer_filter_field(phrase)
                if not any(
                    f.field == inferred_field and f.value == phrase
                    for f in filters
                ):
                    filters.append(FilterCondition(field=inferred_field, operator="=", value=phrase))

        return filters

    def _extract_date_range(self, text: str, reference: date) -> DateRange | None:
        if "today" in text:
            return self._to_date_range(reference, reference)

        if "yesterday" in text:
            day = reference - timedelta(days=1)
            return self._to_date_range(day, day)

        if "this month" in text:
            start = reference.replace(day=1)
            return self._to_date_range(start, reference, "month")

        if "last month" in text:
            first_this_month = reference.replace(day=1)
            end_last_month = first_this_month - timedelta(days=1)
            start_last_month = end_last_month.replace(day=1)
            return self._to_date_range(start_last_month, end_last_month, "month")

        if "this year" in text:
            start = reference.replace(month=1, day=1)
            return self._to_date_range(start, reference, "year")

        if "last year" in text:
            year = reference.year - 1
            start = date(year, 1, 1)
            end = date(year, 12, 31)
            return self._to_date_range(start, end, "year")

        last_days_match = re.search(r"last\s+(\d+)\s+days", text)
        if last_days_match:
            days = int(last_days_match.group(1))
            end = reference
            start = reference - timedelta(days=days - 1)
            return self._to_date_range(start, end)

        explicit_range = re.search(
            r"(?:from|between)\s+(\d{4}-\d{2}-\d{2})\s+(?:to|and)\s+(\d{4}-\d{2}-\d{2})",
            text,
        )
        if explicit_range:
            start = datetime.strptime(explicit_range.group(1), "%Y-%m-%d").date()
            end = datetime.strptime(explicit_range.group(2), "%Y-%m-%d").date()
            if start <= end:
                return self._to_date_range(start, end)

        return None

    @staticmethod
    def _to_date_range(start: date, end: date, granularity: str = "day") -> DateRange:
        return DateRange(
            start_date=start.isoformat(),
            end_date=end.isoformat(),
            granularity=granularity,
        )

    def _canonical_dimension(self, token: str) -> str | None:
        token = token.strip()
        for canonical, keywords in self.DIMENSION_KEYWORDS.items():
            if token == canonical or any(keyword in token for keyword in keywords):
                return canonical
        return token.replace(" ", "_") if token else None

    @staticmethod
    def _normalize_field(field: str) -> str:
        cleaned = field.strip().lower()
        cleaned = re.sub(r"^(where|and|with)\s+", "", cleaned)
        field = re.sub(r"\s+", "_", cleaned)
        return re.sub(r"[^a-z0-9_]", "", field)

    def _infer_filter_field(self, phrase: str) -> str:
        phrase = phrase.strip().lower()
        for canonical, keywords in self.DIMENSION_KEYWORDS.items():
            if any(keyword in phrase for keyword in keywords):
                return canonical
        return "category"

    def _merge_with_conversation_memory(
        self,
        parsed: ParsedQuery,
        normalized_query: str,
        prior_queries: list[ParsedQuery],
    ) -> ParsedQuery:
        """Carry forward intent from prior turns when the current turn is underspecified."""
        latest_with_metrics = self._latest_non_empty(prior_queries, "metrics")
        latest_with_dimensions = self._latest_non_empty(prior_queries, "dimensions")
        latest_with_aggs = self._latest_non_empty(prior_queries, "aggregations")
        latest_with_filters = self._latest_non_empty(prior_queries, "filters")
        latest_with_dates = self._latest_non_empty(prior_queries, "date_range")

        reference_tokens = {
            "same",
            "again",
            "also",
            "those",
            "them",
            "it",
            "that",
            "previous",
            "before",
        }
        has_reference = any(token in normalized_query for token in reference_tokens)

        used_memory = False

        if (not parsed.metrics or has_reference) and latest_with_metrics:
            for metric in latest_with_metrics.metrics:
                if metric not in parsed.metrics:
                    parsed.metrics.append(metric)
                    used_memory = True

        if (not parsed.dimensions or has_reference) and latest_with_dimensions:
            for dimension in latest_with_dimensions.dimensions:
                if dimension not in parsed.dimensions:
                    parsed.dimensions.append(dimension)
                    used_memory = True

        if (not parsed.aggregations or has_reference) and latest_with_aggs:
            for aggregation in latest_with_aggs.aggregations:
                if aggregation not in parsed.aggregations:
                    parsed.aggregations.append(aggregation)
                    used_memory = True

        if (not parsed.filters or has_reference) and latest_with_filters:
            existing = {(flt.field, flt.operator, flt.value) for flt in parsed.filters}
            for filter_condition in latest_with_filters.filters:
                key = (filter_condition.field, filter_condition.operator, filter_condition.value)
                if key not in existing:
                    parsed.filters.append(filter_condition)
                    existing.add(key)
                    used_memory = True

        if parsed.date_range is None and latest_with_dates and latest_with_dates.date_range is not None:
            parsed.date_range = latest_with_dates.date_range
            used_memory = True

        parsed.memory_applied = used_memory
        return parsed

    @staticmethod
    def _latest_non_empty(prior_queries: list[ParsedQuery], field_name: str) -> ParsedQuery | None:
        for previous in reversed(prior_queries):
            value = getattr(previous, field_name)
            if value:
                return previous
        return None