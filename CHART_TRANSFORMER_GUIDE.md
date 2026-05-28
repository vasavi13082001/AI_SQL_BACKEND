# Chart Data Transformer - Usage Guide

Transform SQL query results into chart-ready JSON structures for visualization. Supports line charts, bar charts, pie charts, and KPI widgets with automatic data aggregation and formatting.

## Quick Start

### 1. Line Chart

Transform time-series or sequential data into line charts:

```python
from app.schemas.visualization import ChartDataRequest, ChartType
from app.services.chart_data_transformer import transform_query_results

# Query results from Snowflake/Redshift
query_result = [
    {"date": "2024-01-01", "revenue": 1000, "region": "East"},
    {"date": "2024-01-01", "revenue": 800, "region": "West"},
    {"date": "2024-01-02", "revenue": 1200, "region": "East"},
    {"date": "2024-01-02", "revenue": 950, "region": "West"},
]

# Transform to chart data
request = ChartDataRequest(
    query_result=query_result,
    chart_type=ChartType.LINE,
    title="Daily Revenue by Region",
    x_field="date",
    y_field="revenue",
    series_field="region",  # Optional: creates multiple series
    options={
        "x_axis_label": "Date",
        "y_axis_label": "Revenue ($)",
        "colors": {
            "East": "#1f77b4",
            "West": "#ff7f0e"
        }
    }
)

response = transform_query_results(request)
if response.success:
    chart_data = response.chart
    # Use chart_data for visualization library
```

**Output JSON Structure:**
```json
{
  "type": "line",
  "title": "Daily Revenue by Region",
  "x_axis_label": "Date",
  "y_axis_label": "Revenue ($)",
  "x_axis_type": "category",
  "series": [
    {
      "name": "East",
      "color": "#1f77b4",
      "data": [
        {"x": "2024-01-01", "y": 1000},
        {"x": "2024-01-02", "y": 1200}
      ]
    },
    {
      "name": "West",
      "color": "#ff7f0e",
      "data": [
        {"x": "2024-01-01", "y": 800},
        {"x": "2024-01-02", "y": 950}
      ]
    }
  ],
  "legend": true,
  "grid": true,
  "smooth": true
}
```

### 2. Bar Chart

Create categorical comparisons and grouped bar charts:

```python
# Sales by category
query_result = [
    {"category": "Electronics", "sales": 150000},
    {"category": "Clothing", "sales": 95000},
    {"category": "Home", "sales": 120000},
]

request = ChartDataRequest(
    query_result=query_result,
    chart_type=ChartType.BAR,
    title="Sales by Category",
    x_field="category",
    y_field="sales",
    options={
        "x_axis_label": "Product Category",
        "y_axis_label": "Sales ($)",
        "orientation": "vertical"
    }
)

response = transform_query_results(request)
```

**Stacked Bar Chart:**
```python
query_result = [
    {"month": "January", "region": "East", "sales": 10000},
    {"month": "January", "region": "West", "sales": 8000},
    {"month": "February", "region": "East", "sales": 12000},
    {"month": "February", "region": "West", "sales": 9500},
]

request = ChartDataRequest(
    query_result=query_result,
    chart_type=ChartType.BAR,
    title="Sales by Month and Region",
    x_field="month",
    y_field="sales",
    series_field="region",
    options={
        "stacked": True,
        "colors": {
            "East": "#2ca02c",
            "West": "#d62728"
        }
    }
)

response = transform_query_results(request)
```

**Output JSON Structure:**
```json
{
  "type": "bar",
  "title": "Sales by Category",
  "x_axis_label": "Product Category",
  "y_axis_label": "Sales ($)",
  "series": [
    {
      "name": "sales",
      "data": [
        {"x": "Electronics", "y": 150000},
        {"x": "Clothing", "y": 95000},
        {"x": "Home", "y": 120000}
      ]
    }
  ],
  "orientation": "vertical",
  "stacked": false,
  "legend": true
}
```

### 3. Pie Chart

Display proportional data and market share:

```python
# Market share
query_result = [
    {"product": "Product A", "market_share": 35},
    {"product": "Product B", "market_share": 25},
    {"product": "Product C", "market_share": 40},
]

request = ChartDataRequest(
    query_result=query_result,
    chart_type=ChartType.PIE,
    title="Market Share Distribution",
    label_field="product",
    value_field="market_share",
    options={
        "donut": False,
        "show_percentage": True,
        "colors": {
            "Product A": "#e74c3c",
            "Product B": "#3498db",
            "Product C": "#2ecc71"
        }
    }
)

response = transform_query_results(request)
```

**Donut Chart Variant:**
```python
request = ChartDataRequest(
    query_result=query_result,
    chart_type=ChartType.PIE,
    title="Market Share",
    label_field="product",
    value_field="market_share",
    options={"donut": True}  # Creates donut instead of pie
)
```

**Output JSON Structure:**
```json
{
  "type": "pie",
  "title": "Market Share Distribution",
  "donut": false,
  "show_percentage": true,
  "slices": [
    {
      "label": "Product A",
      "value": 35,
      "percentage": 33.33,
      "color": "#e74c3c"
    },
    {
      "label": "Product B",
      "value": 25,
      "percentage": 23.81,
      "color": "#3498db"
    },
    {
      "label": "Product C",
      "value": 40,
      "percentage": 42.86,
      "color": "#2ecc71"
    }
  ]
}
```

### 4. KPI Widgets

Display key performance indicators with change tracking:

```python
# Current metrics with previous period comparison
query_result = [
    {
        "metric": "Total Revenue",
        "value": 250000,
        "previous_value": 225000,
        "target": 300000
    },
    {
        "metric": "Total Orders",
        "value": 5000,
        "previous_value": 4800
    },
    {
        "metric": "Customer Growth",
        "value": 2500,
        "previous_value": 2300
    },
]

request = ChartDataRequest(
    query_result=query_result,
    chart_type=ChartType.KPI,
    title="Business Metrics Dashboard",
    label_field="metric",
    value_field="value",
    options={
        "layout": "grid",
        "columns": 3,
        "units": {
            "Total Revenue": "$",
            "Total Orders": " orders",
            "Customer Growth": " users"
        },
        "formats": {
            "Total Revenue": "currency",
            "Total Orders": "number",
            "Customer Growth": "number"
        },
        "colors": {
            "Total Revenue": "#27ae60",
            "Total Orders": "#3498db",
            "Customer Growth": "#9b59b6"
        }
    }
)

response = transform_query_results(request)
```

**Output JSON Structure:**
```json
{
  "type": "kpi",
  "title": "Business Metrics Dashboard",
  "layout": "grid",
  "columns": 3,
  "kpis": [
    {
      "label": "Total Revenue",
      "value": 250000,
      "unit": "$",
      "format": "currency",
      "previous_value": 225000,
      "change_percentage": 11.11,
      "change_direction": "up",
      "target": 300000,
      "color": "#27ae60"
    },
    {
      "label": "Total Orders",
      "value": 5000,
      "unit": " orders",
      "format": "number",
      "previous_value": 4800,
      "change_percentage": 4.17,
      "change_direction": "up"
    },
    {
      "label": "Customer Growth",
      "value": 2500,
      "unit": " users",
      "format": "number",
      "previous_value": 2300,
      "change_percentage": 8.7,
      "change_direction": "up"
    }
  ]
}
```

## API Endpoints

### Transform to Chart (Generic)

**POST** `/api/v1/visualization/transform`

Generic endpoint for any chart type transformation.

**Request Body:**
```json
{
  "query_result": [
    {"date": "2024-01-01", "value": 100},
    {"date": "2024-01-02", "value": 150}
  ],
  "chart_type": "line",
  "title": "Sample Chart",
  "x_field": "date",
  "y_field": "value"
}
```

### Line Chart Shortcut

**POST** `/api/v1/visualization/line-chart`

Convenience endpoint for line charts.

### Bar Chart Shortcut

**POST** `/api/v1/visualization/bar-chart`

Convenience endpoint for bar charts.

### Pie Chart Shortcut

**POST** `/api/v1/visualization/pie-chart`

Convenience endpoint for pie charts.

### KPI Widget Shortcut

**POST** `/api/v1/visualization/kpi-widget`

Convenience endpoint for KPI widgets.

## Parameters Reference

### Common Parameters

- **query_result** (required): List of dictionaries from SQL query
- **chart_type** (required): "line", "bar", "pie", or "kpi"
- **title** (required): Chart title
- **aggregation** (optional): "sum", "avg", "count", "min", "max", "last" (default: "sum")
- **options** (optional): Dictionary of additional options

### Line Chart Parameters

- **x_field** (required): X-axis field name
- **y_field** (required): Y-axis/value field name
- **series_field** (optional): Field to group into multiple series

**Line Chart Options:**
```python
options = {
    "x_axis_label": "X Label",
    "y_axis_label": "Y Label",
    "x_axis_type": "category" or "time",
    "colors": {"series_name": "#hex_color"},
    "legend": True,
    "grid": True,
    "smooth": True
}
```

### Bar Chart Parameters

- **x_field** (required): Category/X-axis field name
- **y_field** (required): Value/Y-axis field name
- **series_field** (optional): Field to group into multiple series

**Bar Chart Options:**
```python
options = {
    "x_axis_label": "Categories",
    "y_axis_label": "Values",
    "orientation": "vertical" or "horizontal",
    "stacked": True or False,
    "colors": {"series_name": "#hex_color"},
    "legend": True,
    "grid": True
}
```

### Pie Chart Parameters

- **label_field** (required): Label/slice name field
- **value_field** (optional): Value field (use y_field as fallback)

**Pie Chart Options:**
```python
options = {
    "donut": True or False,
    "show_percentage": True,
    "colors": {"label": "#hex_color"},
    "legend": True
}
```

### KPI Widget Parameters

- **label_field** (required): KPI metric name field
- **value_field** (optional): Value field (use y_field as fallback)

**Expected Fields in Query Result:**
- `previous_value`: Previous period value for change calculation
- `target`: Target value for progress tracking

**KPI Widget Options:**
```python
options = {
    "layout": "grid", "row", or "column",
    "columns": 2,  # For grid layout
    "units": {"metric_name": "unit"},
    "formats": {"metric_name": "number|currency|percentage|custom"},
    "colors": {"metric_name": "#hex_color"}
}
```

## Aggregation Methods

When data rows have multiple values for the same X value:

- **sum**: Add all values (default)
- **avg**: Calculate average
- **count**: Count number of values
- **min**: Get minimum value
- **max**: Get maximum value
- **last**: Use last value in sequence

## Data Type Support

The transformer automatically handles:
- Numbers (int, float)
- Decimal values
- String numbers (converted to float)
- Date and datetime objects
- Null/None values (skipped)

## Error Handling

All transformations return a `ChartDataResponse`:

```python
{
  "success": True/False,
  "chart": {...},  # Chart data if successful
  "row_count": 100,
  "error_message": "Error description if failed",
  "warnings": ["Warning 1", "Warning 2"],
  "metadata": {...}
}
```

Check the `success` field and `error_message` for details on failures.

## Examples with Real SQL

### Example 1: Daily Revenue Trend

```sql
-- Snowflake SQL
SELECT 
    DATE_TRUNC('day', created_at) as date,
    COALESCE(SUM(order_total), 0) as revenue
FROM orders
WHERE created_at >= CURRENT_DATE - 30
GROUP BY 1
ORDER BY 1
```

```python
# Transform to chart
request = ChartDataRequest(
    query_result=query_rows,
    chart_type=ChartType.LINE,
    title="Revenue Last 30 Days",
    x_field="date",
    y_field="revenue"
)
```

### Example 2: Product Performance Comparison

```sql
-- SQL
SELECT 
    p.name as product,
    COALESCE(SUM(oi.quantity), 0) as units_sold,
    COALESCE(SUM(oi.price * oi.quantity), 0) as total_revenue
FROM products p
LEFT JOIN order_items oi ON p.id = oi.product_id
GROUP BY p.id, p.name
ORDER BY 3 DESC
LIMIT 10
```

```python
# Transform to chart
request = ChartDataRequest(
    query_result=query_rows,
    chart_type=ChartType.BAR,
    title="Top 10 Products by Revenue",
    x_field="product",
    y_field="total_revenue",
    options={
        "y_axis_label": "Revenue ($)"
    }
)
```

### Example 3: Regional Sales Distribution

```sql
-- SQL
SELECT 
    r.region_name,
    COALESCE(SUM(o.total), 0) as sales
FROM regions r
LEFT JOIN orders o ON r.id = o.region_id
GROUP BY r.id, r.region_name
```

```python
# Transform to pie chart
request = ChartDataRequest(
    query_result=query_rows,
    chart_type=ChartType.PIE,
    title="Sales by Region",
    label_field="region_name",
    value_field="sales"
)
```

### Example 4: Dashboard KPIs

```sql
-- SQL
SELECT 
    'Total Revenue' as metric,
    COALESCE(SUM(total), 0) as value,
    LAG(COALESCE(SUM(total), 0)) OVER (ORDER BY DATE_TRUNC('month', created_at)) as previous_value
FROM orders
WHERE DATE_TRUNC('month', created_at) = DATE_TRUNC('month', CURRENT_DATE)
GROUP BY 1

UNION ALL

SELECT 
    'Active Orders',
    COUNT(DISTINCT id),
    NULL
FROM orders
WHERE status = 'active'
```

```python
# Transform to KPI widgets
request = ChartDataRequest(
    query_result=query_rows,
    chart_type=ChartType.KPI,
    title="Today's Metrics",
    label_field="metric",
    value_field="value",
    options={
        "columns": 2,
        "units": {"Total Revenue": "$"}
    }
)
```

## Testing

Run the test suite:

```bash
pytest tests/test_chart_data_transformer.py -v
```

Test coverage includes:
- Basic chart transformations for all types
- Multiple series grouping
- Data aggregation methods
- Data type handling (Decimal, string numbers, dates)
- Null value handling
- Percentage calculations for KPIs
- Error cases and edge conditions
