"""Test examples for products API."""
import pytest
from fastapi.testclient import TestClient
from app import create_app

client = TestClient(create_app())


def test_list_products():
    """Test listing products."""
    response = client.get("/api/v1/products/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_create_product():
    """Test creating a product."""
    product_data = {
        "name": "Test Product",
        "description": "A test product",
        "price": 99.99,
        "stock": 10,
        "sku": "TEST-001"
    }
    response = client.post("/api/v1/products/", json=product_data)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == product_data["name"]
    assert data["price"] == product_data["price"]


def test_get_product_not_found():
    """Test getting non-existent product."""
    response = client.get("/api/v1/products/9999")
    assert response.status_code == 404
