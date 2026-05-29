"""API endpoints for chart data transformation and visualization."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from logging import getLogger

from app.models import User
from app.schemas.visualization import ChartDataRequest, ChartDataResponse
from app.schemas.user import UserRole
from app.services.auth_service import require_roles
from app.services.chart_data_transformer import transform_query_results

logger = getLogger(__name__)

router = APIRouter(prefix="/visualization", tags=["Visualization"])


@router.post(
    "/transform",
    response_model=ChartDataResponse,
    summary="Transform SQL query results into chart-ready JSON",
    description=(
        "Convert raw SQL query results into chart-ready JSON structures for visualization. "
        "Supports line charts, bar charts, pie charts, and KPI widgets with automatic data "
        "aggregation and formatting."
    ),
    status_code=status.HTTP_200_OK,
)
async def transform_to_chart(
    request: ChartDataRequest,
    _current_user: User = Depends(
        require_roles(UserRole.ANALYST, UserRole.DATA_ENGINEER, UserRole.ADMIN)
    ),
) -> ChartDataResponse:
    """Transform raw query results into chart-ready data."""
    try:
        logger.info(
            f"Chart transformation requested: type={request.chart_type}, "
            f"title={request.title}, rows={len(request.query_result)}"
        )

        response = transform_query_results(request)

        if response.success:
            logger.info(
                f"Chart transformation successful: type={request.chart_type}, "
                f"rows_processed={response.row_count}"
            )
        else:
            logger.warning(
                f"Chart transformation failed: {response.error_message}"
            )

        return response

    except Exception as exc:
        logger.error(f"Chart transformation error: {str(exc)}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Chart transformation failed: {str(exc)}",
        ) from exc


@router.post(
    "/line-chart",
    response_model=ChartDataResponse,
    summary="Create a line chart from query results",
    description=(
        "Convenience endpoint for transforming query results into a line chart. "
        "Requires x_field (for X-axis) and y_field (for Y-axis). "
        "Optionally specify series_field to create multiple series."
    ),
    status_code=status.HTTP_200_OK,
)
async def create_line_chart(
    request: ChartDataRequest,
    _current_user: User = Depends(
        require_roles(UserRole.ANALYST, UserRole.DATA_ENGINEER, UserRole.ADMIN)
    ),
) -> ChartDataResponse:
    """Create line chart from query results."""
    from app.schemas.visualization import ChartType
    
    request.chart_type = ChartType.LINE
    return await transform_to_chart(request, _current_user)


@router.post(
    "/bar-chart",
    response_model=ChartDataResponse,
    summary="Create a bar chart from query results",
    description=(
        "Convenience endpoint for transforming query results into a bar chart. "
        "Requires x_field (for categories) and y_field (for values). "
        "Optionally specify series_field to create multiple series or set stacked=true for stacked bars."
    ),
    status_code=status.HTTP_200_OK,
)
async def create_bar_chart(
    request: ChartDataRequest,
    _current_user: User = Depends(
        require_roles(UserRole.ANALYST, UserRole.DATA_ENGINEER, UserRole.ADMIN)
    ),
) -> ChartDataResponse:
    """Create bar chart from query results."""
    from app.schemas.visualization import ChartType
    
    request.chart_type = ChartType.BAR
    return await transform_to_chart(request, _current_user)


@router.post(
    "/pie-chart",
    response_model=ChartDataResponse,
    summary="Create a pie chart from query results",
    description=(
        "Convenience endpoint for transforming query results into a pie chart. "
        "Requires label_field (for slice labels) and value_field or y_field (for values). "
        "Use options[\"donut\"] = true for a donut chart variant."
    ),
    status_code=status.HTTP_200_OK,
)
async def create_pie_chart(
    request: ChartDataRequest,
    _current_user: User = Depends(
        require_roles(UserRole.ANALYST, UserRole.DATA_ENGINEER, UserRole.ADMIN)
    ),
) -> ChartDataResponse:
    """Create pie chart from query results."""
    from app.schemas.visualization import ChartType
    
    request.chart_type = ChartType.PIE
    return await transform_to_chart(request, _current_user)


@router.post(
    "/kpi-widget",
    response_model=ChartDataResponse,
    summary="Create KPI widgets from query results",
    description=(
        "Convenience endpoint for transforming query results into KPI widgets. "
        "Requires label_field (for KPI names) and value_field or y_field (for values). "
        "Supports optional previous_value field for change calculation and target field for progress."
    ),
    status_code=status.HTTP_200_OK,
)
async def create_kpi_widget(
    request: ChartDataRequest,
    _current_user: User = Depends(
        require_roles(UserRole.ANALYST, UserRole.DATA_ENGINEER, UserRole.ADMIN)
    ),
) -> ChartDataResponse:
    """Create KPI widget from query results."""
    from app.schemas.visualization import ChartType
    
    request.chart_type = ChartType.KPI
    return await transform_to_chart(request, _current_user)
