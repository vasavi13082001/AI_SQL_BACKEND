"""Product model definition."""
from sqlalchemy import Column, Integer, String, Float, Text
from app.database import Base
from datetime import datetime


class Product(Base):
    """Product model for database."""
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), index=True, nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Float, nullable=False)
    stock = Column(Integer, default=0, nullable=False)
    sku = Column(String(100), unique=True, index=True, nullable=False)
    is_active = Column(Integer, default=1, nullable=False)
    created_at = Column(String, default=datetime.utcnow, nullable=False)
    updated_at = Column(String, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f"<Product(id={self.id}, name={self.name}, price={self.price})>"
