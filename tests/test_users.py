"""Test examples for users API."""
import pytest
from uuid import uuid4
from app.models import User
from app.services.auth_service import get_password_hash


@pytest.fixture
def admin_token_headers(client, db_session):
    """Create an admin user and return authorization headers."""
    username = "admin_test_user"
    password = "AdminPass123!"

    admin = db_session.query(User).filter(User.username == username).first()
    if not admin:
        admin = User(
            email="admin_test@example.com",
            username=username,
            full_name="Admin Test",
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


def test_list_users(client, admin_token_headers):
    """Test listing users."""
    response = client.get("/api/v1/users/", headers=admin_token_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_create_user(client, admin_token_headers):
    """Test creating a user."""
    suffix = uuid4().hex[:8]
    user_data = {
        "email": f"test_{suffix}@example.com",
        "username": f"testuser_{suffix}",
        "full_name": "Test User",
        "password": "testpass123",
        "role": "analyst",
    }
    response = client.post("/api/v1/users/", json=user_data, headers=admin_token_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == user_data["email"]
    assert data["username"] == user_data["username"]


def test_get_user_not_found(client, admin_token_headers):
    """Test getting non-existent user."""
    response = client.get("/api/v1/users/9999", headers=admin_token_headers)
    assert response.status_code == 404
