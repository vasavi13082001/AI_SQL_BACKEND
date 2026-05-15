"""Product service with business logic."""
from sqlalchemy.orm import Session
from app.models import Product
from app.schemas.product import ProductCreate, ProductUpdate
from logging import getLogger

logger = getLogger(__name__)


class ProductService:
    """Service class for product operations."""
    
    @staticmethod
    def get_product(db: Session, product_id: int) -> Product:
        """Get product by ID."""
        return db.query(Product).filter(Product.id == product_id).first()
    
    @staticmethod
    def get_product_by_sku(db: Session, sku: str) -> Product:
        """Get product by SKU."""
        return db.query(Product).filter(Product.sku == sku).first()
    
    @staticmethod
    def get_products(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        is_active: bool = True
    ) -> list[Product]:
        """Get all products with pagination and filtering."""
        query = db.query(Product)
        if is_active is not None:
            query = query.filter(Product.is_active == is_active)
        return query.offset(skip).limit(limit).all()
    
    @staticmethod
    def create_product(db: Session, product_create: ProductCreate) -> Product:
        """Create a new product."""
        db_product = Product(**product_create.model_dump())
        db.add(db_product)
        db.commit()
        db.refresh(db_product)
        
        logger.info(f"Product created: {db_product.name} (SKU: {db_product.sku})")
        return db_product
    
    @staticmethod
    def update_product(
        db: Session,
        product_id: int,
        product_update: ProductUpdate
    ) -> Product:
        """Update product information."""
        db_product = db.query(Product).filter(Product.id == product_id).first()
        if not db_product:
            return None
        
        update_data = product_update.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_product, key, value)
        
        db.add(db_product)
        db.commit()
        db.refresh(db_product)
        
        logger.info(f"Product updated: {db_product.name}")
        return db_product
    
    @staticmethod
    def delete_product(db: Session, product_id: int) -> bool:
        """Delete product."""
        db_product = db.query(Product).filter(Product.id == product_id).first()
        if not db_product:
            return False
        
        db.delete(db_product)
        db.commit()
        
        logger.info(f"Product deleted: {db_product.name}")
        return True
    
    @staticmethod
    def search_products(db: Session, query_str: str) -> list[Product]:
        """Search products by name or description."""
        return db.query(Product).filter(
            (Product.name.ilike(f"%{query_str}%")) |
            (Product.description.ilike(f"%{query_str}%"))
        ).all()
