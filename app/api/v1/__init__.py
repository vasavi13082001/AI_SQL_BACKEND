"""API v1 routes initialization."""
from fastapi import APIRouter
from app.api.v1 import users, products, snowflake

router = APIRouter(prefix="/api/v1")

# Include routers
router.include_router(users.router)
router.include_router(products.router)
router.include_router(snowflake.router)

__all__ = ["router"]
