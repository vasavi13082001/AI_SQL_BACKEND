"""Pydantic schemas for chart visualization and data transformation."""
from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class ChartType(str, Enum):
    """Supported chart types for visualization."""
    LINE = "line"
    BAR = "bar"
    PIE = "pie"
    KPI = "kpi"


class DataPoint(BaseModel):
    """A single data point in a chart."""
    x: str | float = Field(..., description="X-axis value (label or timestamp)")
    y: float = Field(..., description="Y-axis numeric value")
    label: Optional[str] = Field(None, description="Optional label for the point")


class Series(BaseModel):
    """A data series for line/bar charts."""
    name: str = Field(..., description="Series name/legend label")
    data: list[DataPoint] = Field(..., description="Array of data points")
    color: Optional[str] = Field(None, description="Optional hex color code (e.g., #FF5733)")


class LineChartData(BaseModel):
    """Chart-ready data structure for line charts."""
    type: ChartType = Field(ChartType.LINE, description="Chart type identifier")
    title: str = Field(..., description="Chart title")
    x_axis_label: str = Field(default="X", description="X-axis label")
    y_axis_label: str = Field(default="Y", description="Y-axis label")
    series: list[Series] = Field(..., description="One or more data series")
    x_axis_type: str = Field(default="category", description="X-axis type: 'category' or 'time'")
    legend: bool = Field(default=True, description="Show legend")
    grid: bool = Field(default=True, description="Show grid lines")
    smooth: bool = Field(default=True, description="Use smooth curves for line charts")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class BarChartData(BaseModel):
    """Chart-ready data structure for bar charts."""
    type: ChartType = Field(ChartType.BAR, description="Chart type identifier")
    title: str = Field(..., description="Chart title")
    x_axis_label: str = Field(default="Category", description="X-axis label")
    y_axis_label: str = Field(default="Value", description="Y-axis label")
    series: list[Series] = Field(..., description="One or more data series")
    legend: bool = Field(default=True, description="Show legend")
    grid: bool = Field(default=True, description="Show grid lines")
    orientation: str = Field(default="vertical", description="Chart orientation: 'vertical' or 'horizontal'")
    stacked: bool = Field(default=False, description="Stack bars")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class PieSlice(BaseModel):
    """A single slice in a pie chart."""
    label: str = Field(..., description="Slice label")
    value: float = Field(..., gt=0, description="Slice value (must be positive)")
    color: Optional[str] = Field(None, description="Optional hex color code")
    percentage: Optional[float] = Field(None, description="Calculated percentage")


class PieChartData(BaseModel):
    """Chart-ready data structure for pie/donut charts."""
    type: ChartType = Field(ChartType.PIE, description="Chart type identifier")
    title: str = Field(..., description="Chart title")
    slices: list[PieSlice] = Field(..., description="Pie slices with labels and values")
    legend: bool = Field(default=True, description="Show legend")
    donut: bool = Field(default=False, description="Use donut chart variant")
    show_percentage: bool = Field(default=True, description="Show percentage labels")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class KPIValue(BaseModel):
    """Individual KPI metric."""
    label: str = Field(..., description="KPI label (e.g., 'Total Revenue')")
    value: float | int | str = Field(..., description="Current KPI value")
    unit: Optional[str] = Field(None, description="Unit of measurement (e.g., '$', '%', 'users')")
    format: str = Field(default="number", description="Format type: 'number', 'currency', 'percentage', 'custom'")
    previous_value: Optional[float | int] = Field(None, description="Previous period value for comparison")
    change_percentage: Optional[float] = Field(None, description="Percentage change from previous value")
    change_direction: Optional[str] = Field(None, description="Change direction: 'up', 'down', 'neutral'")
    target: Optional[float | int] = Field(None, description="Target value for progress tracking")
    color: Optional[str] = Field(None, description="Optional hex color code")


class KPIWidgetData(BaseModel):
    """Chart-ready data structure for KPI widgets/dashboards."""
    type: ChartType = Field(ChartType.KPI, description="Chart type identifier")
    title: str = Field(..., description="Widget title")
    kpis: list[KPIValue] = Field(..., min_items=1, description="One or more KPI metrics")
    layout: str = Field(default="grid", description="Layout type: 'grid', 'row', 'column'")
    columns: int = Field(default=2, description="Grid columns for layout")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class ChartDataRequest(BaseModel):
    """Request to transform raw query results into chart data."""
    query_result: list[dict[str, Any]] = Field(
        ...,
        description="Raw query result rows as list of dictionaries"
    )
    chart_type: ChartType = Field(
        ...,
        description="Type of chart to generate"
    )
    title: str = Field(
        ...,
        description="Chart title"
    )
    x_field: Optional[str] = Field(
        None,
        description="Field name for X-axis (required for line/bar charts)"
    )
    y_field: Optional[str] = Field(
        None,
        description="Field name for Y-axis or value (required for most charts)"
    )
    label_field: Optional[str] = Field(
        None,
        description="Field name for labels/categories (used in pie charts, KPIs)"
    )
    series_field: Optional[str] = Field(
        None,
        description="Field name for grouping into multiple series (optional for line/bar)"
    )
    value_field: Optional[str] = Field(
        None,
        description="Alternative field name for values (e.g., for KPI metrics)"
    )
    aggregation: str = Field(
        default="sum",
        description="Aggregation method: 'sum', 'avg', 'count', 'min', 'max', 'last'"
    )
    options: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional chart options (colors, labels, formatting, etc.)"
    )


class ChartDataResponse(BaseModel):
    """Response containing chart-ready data."""
    success: bool = Field(..., description="Whether transformation was successful")
    chart: LineChartData | BarChartData | PieChartData | KPIWidgetData | None = Field(
        None,
        description="Chart-ready data structure (null if failed)"
    )
    row_count: int = Field(default=0, description="Number of rows processed")
    error_message: Optional[str] = Field(None, description="Error details if transformation failed")
    warnings: list[str] = Field(default_factory=list, description="Non-critical warnings")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Processing metadata")
