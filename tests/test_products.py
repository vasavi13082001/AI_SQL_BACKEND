"""Test examples for products API."""
import pytest
from uuid import uuid4
from app.models import User
from app.services.auth_service import get_password_hash


@pytest.fixture
def admin_token_headers(client, db_session):
    """Create an admin user and return authorization headers."""
    username = "admin_product_user"
    password = "AdminPass123!"

    admin = db_session.query(User).filter(User.username == username).first()
    if not admin:
        admin = User(
            email="admin_products@example.com",
            username=username,
            full_name="Admin Product Test",
            hashed_password=get_password_hash(password),
            role="admin",
            is_superuser=True,
            is_active=True,
        )
        db_session.add(admin)
        db_session.commit()

    login_response = client.post(
        "/api/v1/auth/token",
        data={"username": username, "password": password},
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_list_products(client, admin_token_headers):
    """Test listing products."""
    response = client.get("/api/v1/products/", headers=admin_token_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_create_product(client, admin_token_headers):
    """Test creating a product."""
    suffix = uuid4().hex[:8]
    product_data = {
        "name": "Test Product",
        "description": "A test product",
        "price": 99.99,
        "stock": 10,
        "sku": f"TEST-{suffix}"
    }
    response = client.post("/api/v1/products/", json=product_data, headers=admin_token_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == product_data["name"]
    assert data["price"] == product_data["price"]


def test_get_product_not_found(client, admin_token_headers):
    """Test getting non-existent product."""
    response = client.get("/api/v1/products/9999", headers=admin_token_headers)
    assert response.status_code == 404
