"""
Database configuration and session management.
Provides SQLAlchemy engine, session factory, and base class for models.
"""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from sqlalchemy.pool import NullPool
from app.config import get_settings
import logging

logger = logging.getLogger(__name__)

settings = get_settings()

# Create engine
engine = create_engine(
    settings.database_url,
    echo=settings.database_echo,
    poolclass=NullPool if settings.environment == "testing" else None,
)

# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)

# Declarative base for models
Base = declarative_base()


def get_db() -> Session:
    """
    Dependency for FastAPI to get database session.
    Usage in routes: async def route(db: Session = Depends(get_db))
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database - create all tables."""
    logger.info("Initializing database...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialized successfully")


def close_db():
    """Close database connection."""
    logger.info("Closing database connection...")
    engine.dispose()
    logger.info("Database connection closed")


# Enable foreign keys for SQLite (if using SQLite)
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    """Enable foreign key support for SQLite."""
    if "sqlite" in settings.database_url.lower():
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
