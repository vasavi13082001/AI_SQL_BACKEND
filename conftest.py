"""Pytest configuration and fixtures."""
import pytest
import sys
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import Base, get_db
from app import create_app


@pytest.fixture(scope="session")
def test_db_url():
    """Test database URL."""
    return "sqlite:///./test.db"


@pytest.fixture(scope="session")
def engine(test_db_url):
    """Create test database engine."""
    engine = create_engine(
        test_db_url,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(engine):
    """Create database session for tests."""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    yield session
    session.close()


@pytest.fixture
def app():
    """Create FastAPI test app."""
    return create_app()


@pytest.fixture
def client(app, db_session):
    """Create test client."""
    def override_get_db():
        try:
            yield db_session
        finally:
            db_session.close()
    
    app.dependency_overrides[get_db] = override_get_db
    
    from fastapi.testclient import TestClient
    return TestClient(app)
