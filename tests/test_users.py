"""Test examples for users API."""
import pytest
from fastapi.testclient import TestClient
from app import create_app

client = TestClient(create_app())


def test_list_users():
    """Test listing users."""
    response = client.get("/api/v1/users/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_create_user():
    """Test creating a user."""
    user_data = {
        "email": "test@example.com",
        "username": "testuser",
        "full_name": "Test User",
        "password": "testpass123"
    }
    response = client.post("/api/v1/users/", json=user_data)
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == user_data["email"]
    assert data["username"] == user_data["username"]


def test_get_user_not_found():
    """Test getting non-existent user."""
    response = client.get("/api/v1/users/9999")
    assert response.status_code == 404
