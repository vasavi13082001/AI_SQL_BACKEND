"""Product API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.product_service import ProductService
from app.schemas.product import ProductCreate, ProductResponse, ProductUpdate, ProductListResponse
from logging import getLogger

logger = getLogger(__name__)

router = APIRouter(prefix="/products", tags=["products"])


@router.get("/", response_model=list[ProductListResponse])
async def list_products(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    is_active: bool = Query(True)
):
    """List all products with pagination and filtering."""
    products = ProductService.get_products(
        db,
        skip=skip,
        limit=limit,
        is_active=is_active
    )
    logger.info(f"Fetched {len(products)} products")
    return products


@router.post("/", response_model=ProductResponse, status_code=201)
async def create_product(
    product_create: ProductCreate,
    db: Session = Depends(get_db)
):
    """Create a new product."""
    # Check if SKU already exists
    existing_product = ProductService.get_product_by_sku(db, product_create.sku)
    if existing_product:
        logger.warning(f"Attempt to create product with existing SKU: {product_create.sku}")
        raise HTTPException(status_code=400, detail="Product SKU already exists")
    
    product = ProductService.create_product(db, product_create)
    return product


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(product_id: int, db: Session = Depends(get_db)):
    """Get a specific product by ID."""
    product = ProductService.get_product(db, product_id)
    if not product:
        logger.warning(f"Product not found: {product_id}")
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.get("/search/", response_model=list[ProductListResponse])
async def search_products(
    q: str = Query(..., min_length=1),
    db: Session = Depends(get_db)
):
    """Search products by name or description."""
    products = ProductService.search_products(db, q)
    logger.info(f"Product search for '{q}': found {len(products)} results")
    return products


@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: int,
    product_update: ProductUpdate,
    db: Session = Depends(get_db)
):
    """Update a product's information."""
    product = ProductService.update_product(db, product_id, product_update)
    if not product:
        logger.warning(f"Product not found for update: {product_id}")
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.delete("/{product_id}", status_code=204)
async def delete_product(product_id: int, db: Session = Depends(get_db)):
    """Delete a product."""
    success = ProductService.delete_product(db, product_id)
    if not success:
        logger.warning(f"Product not found for deletion: {product_id}")
        raise HTTPException(status_code=404, detail="Product not found")
    return None
