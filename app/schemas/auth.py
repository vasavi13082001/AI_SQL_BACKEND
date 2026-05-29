"""Authentication request/response schemas."""
from pydantic import BaseModel

from app.schemas.user import UserRole


class Token(BaseModel):
    """JWT token response."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user_role: UserRole


class TokenPayload(BaseModel):
    """Expected JWT claims used by the API."""

    sub: str
    role: UserRole