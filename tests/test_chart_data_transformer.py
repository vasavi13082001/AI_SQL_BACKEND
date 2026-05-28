"""Tests for chart data transformer service."""
import pytest
from decimal import Decimal
from datetime import datetime, date

from app.schemas.visualization import ChartType
from app.schemas.visualization import ChartDataRequest
from app.services.chart_data_transformer import transform_query_results


class TestLineChartTransformation:
    """Test line chart transformations."""

    def test_simple_line_chart(self):
        """Test basic line chart transformation."""
        query_result = [
            {"date": "2024-01-01", "revenue": 1000},
            {"date": "2024-01-02", "revenue": 1200},
            {"date": "2024-01-03", "revenue": 950},
        ]

        request = ChartDataRequest(
            query_result=query_result,
            chart_type=ChartType.LINE,
            title="Daily Revenue",
            x_field="date",
            y_field="revenue",
        )

        response = transform_query_results(request)

        assert response.success is True
        assert response.chart is not None
        assert response.chart.title == "Daily Revenue"
        assert len(response.chart.series) == 1
        assert len(response.chart.series[0].data) == 3
        assert response.row_count == 3

    def test_line_chart_with_multiple_series(self):
        """Test line chart with multiple series."""
        query_result = [
            {"date": "2024-01-01", "region": "East", "revenue": 1000},
            {"date": "2024-01-01", "region": "West", "revenue": 800},
            {"date": "2024-01-02", "region": "East", "revenue": 1200},
            {"date": "2024-01-02", "region": "West", "revenue": 950},
        ]

        request = ChartDataRequest(
            query_result=query_result,
            chart_type=ChartType.LINE,
            title="Revenue by Region",
            x_field="date",
            y_field="revenue",
            series_field="region",
        )

        response = transform_query_results(request)

        assert response.success is True
        assert len(response.chart.series) == 2
        series_names = {s.name for s in response.chart.series}
        assert series_names == {"East", "West"}

    def test_line_chart_with_aggregation(self):
        """Test line chart with data aggregation."""
        query_result = [
            {"date": "2024-01-01", "revenue": 100},
            {"date": "2024-01-01", "revenue": 200},
            {"date": "2024-01-01", "revenue": 300},
        ]

        request = ChartDataRequest(
            query_result=query_result,
            chart_type=ChartType.LINE,
            title="Daily Revenue",
            x_field="date",
            y_field="revenue",
            aggregation="sum",
        )

        response = transform_query_results(request)

        assert response.success is True
        assert response.chart.series[0].data[0].y == 600  # 100 + 200 + 300

    def test_line_chart_missing_x_field_fails(self):
        """Test line chart fails without x_field."""
        query_result = [{"revenue": 1000}]

        request = ChartDataRequest(
            query_result=query_result,
            chart_type=ChartType.LINE,
            title="Test",
            x_field=None,
            y_field="revenue",
        )

        response = transform_query_results(request)

        assert response.success is False
        assert "x_field is required" in response.error_message


class TestBarChartTransformation:
    """Test bar chart transformations."""

    def test_simple_bar_chart(self):
        """Test basic bar chart transformation."""
        query_result = [
            {"category": "A", "value": 100},
            {"category": "B", "value": 150},
            {"category": "C", "value": 120},
        ]

        request = ChartDataRequest(
            query_result=query_result,
            chart_type=ChartType.BAR,
            title="Category Sales",
            x_field="category",
            y_field="value",
        )

        response = transform_query_results(request)

        assert response.success is True
        assert response.chart is not None
        assert response.chart.title == "Category Sales"
        assert len(response.chart.series) == 1
        assert len(response.chart.series[0].data) == 3

    def test_stacked_bar_chart(self):
        """Test stacked bar chart."""
        query_result = [
            {"month": "Jan", "region": "East", "sales": 100},
            {"month": "Jan", "region": "West", "sales": 80},
            {"month": "Feb", "region": "East", "sales": 120},
            {"month": "Feb", "region": "West", "sales": 95},
        ]

        request = ChartDataRequest(
            query_result=query_result,
            chart_type=ChartType.BAR,
            title="Sales by Month and Region",
            x_field="month",
            y_field="sales",
            series_field="region",
            options={"stacked": True},
        )

        response = transform_query_results(request)

        assert response.success is True
        assert response.chart.stacked is True
        assert len(response.chart.series) == 2


class TestPieChartTransformation:
    """Test pie chart transformations."""

    def test_simple_pie_chart(self):
        """Test basic pie chart transformation."""
        query_result = [
            {"label": "Product A", "value": 300},
            {"label": "Product B", "value": 200},
            {"label": "Product C", "value": 100},
        ]

        request = ChartDataRequest(
            query_result=query_result,
            chart_type=ChartType.PIE,
            title="Sales Distribution",
            label_field="label",
            value_field="value",
        )

        response = transform_query_results(request)

        assert response.success is True
        assert response.chart is not None
        assert len(response.chart.slices) == 3
        
        # Check percentages
        percentages = [s.percentage for s in response.chart.slices]
        assert abs(sum(percentages) - 100) < 0.01

    def test_donut_chart(self):
        """Test donut chart variant."""
        query_result = [
            {"label": "A", "value": 50},
            {"label": "B", "value": 30},
            {"label": "C", "value": 20},
        ]

        request = ChartDataRequest(
            query_result=query_result,
            chart_type=ChartType.PIE,
            title="Market Share",
            label_field="label",
            value_field="value",
            options={"donut": True},
        )

        response = transform_query_results(request)

        assert response.success is True
        assert response.chart.donut is True


class TestKPIWidgetTransformation:
    """Test KPI widget transformations."""

    def test_simple_kpi_widget(self):
        """Test basic KPI widget."""
        query_result = [
            {"metric": "Total Revenue", "value": 100000},
            {"metric": "Total Orders", "value": 2500},
            {"metric": "Active Users", "value": 1200},
        ]

        request = ChartDataRequest(
            query_result=query_result,
            chart_type=ChartType.KPI,
            title="Key Metrics",
            label_field="metric",
            value_field="value",
        )

        response = transform_query_results(request)

        assert response.success is True
        assert response.chart is not None
        assert len(response.chart.kpis) == 3
        assert response.chart.kpis[0].label == "Total Revenue"
        assert response.chart.kpis[0].value == 100000

    def test_kpi_with_change_percentage(self):
        """Test KPI with previous value and change calculation."""
        query_result = [
            {
                "metric": "Revenue",
                "value": 110000,
                "previous_value": 100000,
            },
            {
                "metric": "Orders",
                "value": 2400,
                "previous_value": 2500,
            },
        ]

        request = ChartDataRequest(
            query_result=query_result,
            chart_type=ChartType.KPI,
            title="Metrics with Change",
            label_field="metric",
            value_field="value",
        )

        response = transform_query_results(request)

        assert response.success is True
        kpis = {kpi.label: kpi for kpi in response.chart.kpis}
        
        # Check revenue KPI
        assert kpis["Revenue"].change_percentage == 10.0
        assert kpis["Revenue"].change_direction == "up"
        
        # Check orders KPI
        assert kpis["Orders"].change_percentage == -4.0
        assert kpis["Orders"].change_direction == "down"

    def test_kpi_with_units_and_format(self):
        """Test KPI with units and formatting options."""
        query_result = [
            {"metric": "Revenue", "value": 100000},
            {"metric": "Growth", "value": 15.5},
        ]

        request = ChartDataRequest(
            query_result=query_result,
            chart_type=ChartType.KPI,
            title="Formatted Metrics",
            label_field="metric",
            value_field="value",
            options={
                "units": {"Revenue": "$", "Growth": "%"},
                "formats": {"Revenue": "currency", "Growth": "percentage"},
            },
        )

        response = transform_query_results(request)

        assert response.success is True
        kpis = {kpi.label: kpi for kpi in response.chart.kpis}
        assert kpis["Revenue"].unit == "$"
        assert kpis["Revenue"].format == "currency"
        assert kpis["Growth"].unit == "%"
        assert kpis["Growth"].format == "percentage"


class TestDataTypeHandling:
    """Test handling of various data types."""

    def test_decimal_values(self):
        """Test Decimal type conversion."""
        query_result = [
            {"date": "2024-01-01", "amount": Decimal("100.50")},
            {"date": "2024-01-02", "amount": Decimal("200.75")},
        ]

        request = ChartDataRequest(
            query_result=query_result,
            chart_type=ChartType.LINE,
            title="Amounts",
            x_field="date",
            y_field="amount",
        )

        response = transform_query_results(request)

        assert response.success is True
        assert response.chart.series[0].data[0].y == 100.5

    def test_string_numbers(self):
        """Test string number conversion."""
        query_result = [
            {"category": "A", "value": "150"},
            {"category": "B", "value": "200"},
        ]

        request = ChartDataRequest(
            query_result=query_result,
            chart_type=ChartType.BAR,
            title="Values",
            x_field="category",
            y_field="value",
        )

        response = transform_query_results(request)

        assert response.success is True
        assert response.chart.series[0].data[0].y == 150.0

    def test_null_values_skipped(self):
        """Test that null values are skipped."""
        query_result = [
            {"date": "2024-01-01", "value": 100},
            {"date": "2024-01-02", "value": None},
            {"date": "2024-01-03", "value": 200},
        ]

        request = ChartDataRequest(
            query_result=query_result,
            chart_type=ChartType.LINE,
            title="Test",
            x_field="date",
            y_field="value",
        )

        response = transform_query_results(request)

        assert response.success is True
        assert len(response.chart.series[0].data) == 2

    def test_date_detection(self):
        """Test automatic date field detection."""
        query_result = [
            {"date": date(2024, 1, 1), "value": 100},
            {"date": date(2024, 1, 2), "value": 200},
        ]

        request = ChartDataRequest(
            query_result=query_result,
            chart_type=ChartType.LINE,
            title="Time Series",
            x_field="date",
            y_field="value",
        )

        response = transform_query_results(request)

        assert response.success is True
        assert response.chart.x_axis_type == "time"


class TestAggregationMethods:
    """Test different aggregation methods."""

    def test_sum_aggregation(self):
        """Test sum aggregation."""
        query_result = [
            {"group": "A", "value": 10},
            {"group": "A", "value": 20},
            {"group": "A", "value": 30},
        ]

        request = ChartDataRequest(
            query_result=query_result,
            chart_type=ChartType.BAR,
            title="Sum Test",
            x_field="group",
            y_field="value",
            aggregation="sum",
        )

        response = transform_query_results(request)
        assert response.chart.series[0].data[0].y == 60

    def test_average_aggregation(self):
        """Test average aggregation."""
        query_result = [
            {"group": "A", "value": 10},
            {"group": "A", "value": 20},
            {"group": "A", "value": 30},
        ]

        request = ChartDataRequest(
            query_result=query_result,
            chart_type=ChartType.BAR,
            title="Avg Test",
            x_field="group",
            y_field="value",
            aggregation="avg",
        )

        response = transform_query_results(request)
        assert response.chart.series[0].data[0].y == 20.0

    def test_count_aggregation(self):
        """Test count aggregation."""
        query_result = [
            {"group": "A", "value": 10},
            {"group": "A", "value": 20},
            {"group": "A", "value": 30},
        ]

        request = ChartDataRequest(
            query_result=query_result,
            chart_type=ChartType.BAR,
            title="Count Test",
            x_field="group",
            y_field="value",
            aggregation="count",
        )

        response = transform_query_results(request)
        assert response.chart.series[0].data[0].y == 3.0


class TestEmptyAndEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_query_result(self):
        """Test with empty query result."""
        request = ChartDataRequest(
            query_result=[],
            chart_type=ChartType.LINE,
            title="Empty",
            x_field="x",
            y_field="y",
        )

        response = transform_query_results(request)

        assert response.success is False
        assert "empty" in response.error_message.lower()

    def test_invalid_chart_type(self):
        """Test with invalid chart type."""
        query_result = [{"x": 1, "y": 2}]

        request = ChartDataRequest(
            query_result=query_result,
            chart_type="invalid_type",  # type: ignore
            title="Invalid",
            x_field="x",
            y_field="y",
        )

        response = transform_query_results(request)

        assert response.success is False

    def test_missing_required_fields(self):
        """Test with missing required fields in query result."""
        query_result = [
            {"x": "A"},  # Missing y field
            {"x": "B", "y": 100},
        ]

        request = ChartDataRequest(
            query_result=query_result,
            chart_type=ChartType.BAR,
            title="Missing Fields",
            x_field="x",
            y_field="y",
        )

        response = transform_query_results(request)

        assert response.success is True
        # Should only process the valid row
        assert len(response.chart.series[0].data) == 1

    def test_options_with_colors(self):
        """Test applying custom colors."""
        query_result = [
            {"label": "A", "value": 100},
            {"label": "B", "value": 200},
        ]

        request = ChartDataRequest(
            query_result=query_result,
            chart_type=ChartType.PIE,
            title="Colored Pie",
            label_field="label",
            value_field="value",
            options={
                "colors": {
                    "A": "#FF5733",
                    "B": "#33FF57",
                }
            },
        )

        response = transform_query_results(request)

        assert response.success is True
        assert response.chart.slices[0].color == "#FF5733"
