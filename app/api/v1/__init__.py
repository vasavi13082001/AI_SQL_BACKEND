"""API v1 routes initialization."""
from fastapi import APIRouter
from app.api.v1 import auth, users, products, snowflake, optimization, visualization

router = APIRouter(prefix="/api/v1")

# Include routers
router.include_router(auth.router)
router.include_router(users.router)
router.include_router(products.router)
router.include_router(snowflake.router)
router.include_router(optimization.router)
router.include_router(visualization.router)

__all__ = ["router"]
