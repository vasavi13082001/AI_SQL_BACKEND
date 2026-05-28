"""Service for transforming SQL query results into chart-ready JSON structures."""
from __future__ import annotations

from logging import getLogger
from typing import Any, Optional
from decimal import Decimal
from datetime import datetime, date

from app.schemas.visualization import (
    BarChartData,
    ChartDataRequest,
    ChartDataResponse,
    ChartType,
    DataPoint,
    KPIValue,
    KPIWidgetData,
    LineChartData,
    PieChartData,
    PieSlice,
    Series,
)

logger = getLogger(__name__)


class ChartDataTransformer:
    """Transform SQL query results into chart-ready JSON structures."""

    def __init__(self):
        """Initialize the transformer."""
        self.warnings: list[str] = []

    def transform(self, request: ChartDataRequest) -> ChartDataResponse:
        """Transform raw query results into chart-ready data."""
        self.warnings = []

        try:
            if not request.query_result:
                return ChartDataResponse(
                    success=False,
                    row_count=0,
                    error_message="Query result is empty"
                )

            # Route to appropriate transformation method
            if request.chart_type == ChartType.LINE:
                chart = self._transform_to_line_chart(request)
            elif request.chart_type == ChartType.BAR:
                chart = self._transform_to_bar_chart(request)
            elif request.chart_type == ChartType.PIE:
                chart = self._transform_to_pie_chart(request)
            elif request.chart_type == ChartType.KPI:
                chart = self._transform_to_kpi_widget(request)
            else:
                return ChartDataResponse(
                    success=False,
                    row_count=len(request.query_result),
                    error_message=f"Unsupported chart type: {request.chart_type}"
                )

            return ChartDataResponse(
                success=True,
                chart=chart,
                row_count=len(request.query_result),
                warnings=self.warnings,
                metadata={
                    "chart_type": request.chart_type,
                    "aggregation": request.aggregation,
                }
            )

        except Exception as exc:
            logger.error(f"Chart transformation failed: {str(exc)}")
            return ChartDataResponse(
                success=False,
                row_count=len(request.query_result),
                error_message=f"Transformation failed: {str(exc)}",
                warnings=self.warnings
            )

    def _transform_to_line_chart(self, request: ChartDataRequest) -> LineChartData:
        """Transform data into line chart format."""
        if not request.x_field:
            raise ValueError("x_field is required for line charts")
        if not request.y_field:
            raise ValueError("y_field is required for line charts")

        # Group data by series if series_field is provided
        if request.series_field:
            series_data = self._group_by_series(
                request.query_result,
                request.x_field,
                request.y_field,
                request.series_field,
                request.aggregation
            )
        else:
            series_data = {
                request.y_field: self._extract_points(
                    request.query_result,
                    request.x_field,
                    request.y_field,
                    request.aggregation
                )
            }

        # Apply colors from options if provided
        colors = request.options.get("colors", {})
        series_list = [
            Series(
                name=name,
                data=points,
                color=colors.get(name)
            )
            for name, points in series_data.items()
        ]

        x_axis_type = request.options.get("x_axis_type", "category")
        if self._is_date_field(request.query_result, request.x_field):
            x_axis_type = "time"

        return LineChartData(
            title=request.title,
            x_axis_label=request.options.get("x_axis_label", request.x_field),
            y_axis_label=request.options.get("y_axis_label", request.y_field),
            series=series_list,
            x_axis_type=x_axis_type,
            legend=request.options.get("legend", True),
            grid=request.options.get("grid", True),
            smooth=request.options.get("smooth", True),
            metadata=request.options.get("metadata", {})
        )

    def _transform_to_bar_chart(self, request: ChartDataRequest) -> BarChartData:
        """Transform data into bar chart format."""
        if not request.x_field:
            raise ValueError("x_field is required for bar charts")
        if not request.y_field:
            raise ValueError("y_field is required for bar charts")

        # Group data by series if series_field is provided
        if request.series_field:
            series_data = self._group_by_series(
                request.query_result,
                request.x_field,
                request.y_field,
                request.series_field,
                request.aggregation
            )
        else:
            series_data = {
                request.y_field: self._extract_points(
                    request.query_result,
                    request.x_field,
                    request.y_field,
                    request.aggregation
                )
            }

        # Apply colors from options
        colors = request.options.get("colors", {})
        series_list = [
            Series(
                name=name,
                data=points,
                color=colors.get(name)
            )
            for name, points in series_data.items()
        ]

        return BarChartData(
            title=request.title,
            x_axis_label=request.options.get("x_axis_label", request.x_field),
            y_axis_label=request.options.get("y_axis_label", request.y_field),
            series=series_list,
            legend=request.options.get("legend", True),
            grid=request.options.get("grid", True),
            orientation=request.options.get("orientation", "vertical"),
            stacked=request.options.get("stacked", False),
            metadata=request.options.get("metadata", {})
        )

    def _transform_to_pie_chart(self, request: ChartDataRequest) -> PieChartData:
        """Transform data into pie chart format."""
        if not request.label_field:
            raise ValueError("label_field is required for pie charts")
        if not request.value_field and not request.y_field:
            raise ValueError("value_field or y_field is required for pie charts")

        value_field = request.value_field or request.y_field
        
        # Group and aggregate data
        slices_data = self._aggregate_by_field(
            request.query_result,
            request.label_field,
            value_field,
            request.aggregation
        )

        # Calculate percentages and prepare slices
        total = sum(val for _, val in slices_data.items())
        colors = request.options.get("colors", {})
        
        slices = [
            PieSlice(
                label=label,
                value=value,
                color=colors.get(label),
                percentage=round((value / total * 100), 2) if total > 0 else 0
            )
            for label, value in slices_data.items()
        ]

        return PieChartData(
            title=request.title,
            slices=slices,
            legend=request.options.get("legend", True),
            donut=request.options.get("donut", False),
            show_percentage=request.options.get("show_percentage", True),
            metadata=request.options.get("metadata", {})
        )

    def _transform_to_kpi_widget(self, request: ChartDataRequest) -> KPIWidgetData:
        """Transform data into KPI widget format."""
        if not request.label_field:
            raise ValueError("label_field is required for KPI widgets")
        if not request.value_field and not request.y_field:
            raise ValueError("value_field or y_field is required for KPI widgets")

        value_field = request.value_field or request.y_field
        
        kpis: list[KPIValue] = []
        colors = request.options.get("colors", {})
        formats = request.options.get("formats", {})
        units = request.options.get("units", {})

        for row in request.query_result:
            if request.label_field not in row or value_field not in row:
                self.warnings.append(
                    f"Skipping row missing {request.label_field} or {value_field}"
                )
                continue

            label = str(row[request.label_field])
            value = row[value_field]
            
            # Prepare KPI value
            previous_value = None
            change_percentage = None
            change_direction = None
            
            # Check for previous value in row
            if "previous_value" in row:
                previous_value = row["previous_value"]
                change_percentage = self._calculate_change_percentage(
                    value,
                    previous_value
                )
                change_direction = "up" if change_percentage > 0 else ("down" if change_percentage < 0 else "neutral")

            kpi = KPIValue(
                label=label,
                value=value,
                unit=units.get(label),
                format=formats.get(label, "number"),
                previous_value=previous_value,
                change_percentage=change_percentage,
                change_direction=change_direction,
                target=row.get("target"),
                color=colors.get(label)
            )
            kpis.append(kpi)

        return KPIWidgetData(
            title=request.title,
            kpis=kpis,
            layout=request.options.get("layout", "grid"),
            columns=request.options.get("columns", 2),
            metadata=request.options.get("metadata", {})
        )

    @staticmethod
    def _extract_points(
        data: list[dict[str, Any]],
        x_field: str,
        y_field: str,
        aggregation: str = "sum"
    ) -> list[DataPoint]:
        """Extract and optionally aggregate data points."""
        points_dict: dict[str, list[float]] = {}

        for row in data:
            if x_field not in row or y_field not in row:
                continue

            x_val = str(row[x_field])
            y_val = ChartDataTransformer._to_float(row[y_field])

            if y_val is None:
                continue

            if x_val not in points_dict:
                points_dict[x_val] = []
            points_dict[x_val].append(y_val)

        # Aggregate based on method
        points = [
            DataPoint(
                x=x,
                y=ChartDataTransformer._aggregate_values(values, aggregation)
            )
            for x, values in points_dict.items()
        ]

        return sorted(points, key=lambda p: (isinstance(p.x, str), p.x))

    @staticmethod
    def _group_by_series(
        data: list[dict[str, Any]],
        x_field: str,
        y_field: str,
        series_field: str,
        aggregation: str = "sum"
    ) -> dict[str, list[DataPoint]]:
        """Group data by series field and extract points."""
        series_dict: dict[str, dict[str, list[float]]] = {}

        for row in data:
            if x_field not in row or y_field not in row or series_field not in row:
                continue

            series_name = str(row[series_field])
            x_val = str(row[x_field])
            y_val = ChartDataTransformer._to_float(row[y_field])

            if y_val is None:
                continue

            if series_name not in series_dict:
                series_dict[series_name] = {}
            if x_val not in series_dict[series_name]:
                series_dict[series_name][x_val] = []

            series_dict[series_name][x_val].append(y_val)

        # Convert to DataPoint lists
        result: dict[str, list[DataPoint]] = {}
        for series_name, points_dict in series_dict.items():
            result[series_name] = [
                DataPoint(
                    x=x,
                    y=ChartDataTransformer._aggregate_values(values, aggregation)
                )
                for x, values in points_dict.items()
            ]
            # Sort points
            result[series_name].sort(key=lambda p: (isinstance(p.x, str), p.x))

        return result

    @staticmethod
    def _aggregate_by_field(
        data: list[dict[str, Any]],
        label_field: str,
        value_field: str,
        aggregation: str = "sum"
    ) -> dict[str, float]:
        """Aggregate data by label field."""
        result: dict[str, list[float]] = {}

        for row in data:
            if label_field not in row or value_field not in row:
                continue

            label = str(row[label_field])
            value = ChartDataTransformer._to_float(row[value_field])

            if value is None:
                continue

            if label not in result:
                result[label] = []
            result[label].append(value)

        # Aggregate
        return {
            label: ChartDataTransformer._aggregate_values(values, aggregation)
            for label, values in result.items()
        }

    @staticmethod
    def _to_float(value: Any) -> Optional[float]:
        """Convert value to float, handling various types."""
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                return None
        return None

    @staticmethod
    def _aggregate_values(values: list[float], aggregation: str) -> float:
        """Aggregate a list of values."""
        if not values:
            return 0.0

        if aggregation == "sum":
            return sum(values)
        elif aggregation == "avg":
            return sum(values) / len(values)
        elif aggregation == "count":
            return float(len(values))
        elif aggregation == "min":
            return min(values)
        elif aggregation == "max":
            return max(values)
        elif aggregation == "last":
            return values[-1]
        else:
            return sum(values)  # Default to sum

    @staticmethod
    def _calculate_change_percentage(current: Any, previous: Any) -> Optional[float]:
        """Calculate percentage change from previous to current value."""
        current_float = ChartDataTransformer._to_float(current)
        previous_float = ChartDataTransformer._to_float(previous)

        if current_float is None or previous_float is None:
            return None

        if previous_float == 0:
            return 100.0 if current_float > 0 else (0.0 if current_float == 0 else -100.0)

        return round(((current_float - previous_float) / abs(previous_float)) * 100, 2)

    @staticmethod
    def _is_date_field(data: list[dict[str, Any]], field_name: str) -> bool:
        """Detect if a field contains date/datetime values."""
        if not data:
            return False

        for row in data:
            if field_name not in row:
                continue
            value = row[field_name]
            if isinstance(value, (datetime, date)):
                return True
            if isinstance(value, str):
                # Simple heuristic: check if it looks like a date
                if any(c in value for c in ["-", "/"]) and len(value) >= 8:
                    return True
            return False

        return False


# Singleton instance
_transformer = ChartDataTransformer()


def transform_query_results(request: ChartDataRequest) -> ChartDataResponse:
    """Public function to transform query results into chart-ready data."""
    return _transformer.transform(request)
