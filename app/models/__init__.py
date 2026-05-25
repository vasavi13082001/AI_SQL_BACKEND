"""Models package initialization."""
from app.models.user import User
from app.models.product import Product
from app.models.query_analytics import (
    ExecutionAnalytics,
    GeneratedSQL,
    QueryHistory,
    UserPrompt,
    WarehousePerformanceMetric,
)

__all__ = [
    "User",
    "Product",
    "QueryHistory",
    "UserPrompt",
    "GeneratedSQL",
    "ExecutionAnalytics",
    "WarehousePerformanceMetric",
]
