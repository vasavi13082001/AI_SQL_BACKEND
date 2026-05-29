"""Authentication API endpoints."""
from datetime import timedelta
from logging import getLogger

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import User
from app.schemas.auth import Token
from app.schemas.user import UserCreate, UserResponse, UserRole
from app.services.auth_service import (
    authenticate_user,
    create_access_token,
    get_current_active_user,
)
from app.services.user_service import UserService

logger = getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> Token:
    """Issue an access token for valid credentials."""
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username/email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    expires_in = settings.access_token_expire_minutes * 60
    expires_delta = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": str(user.id), "role": user.role},
        expires_delta=expires_delta,
    )
    return Token(
        access_token=access_token,
        expires_in=expires_in,
        user_role=UserRole(user.role),
    )


@router.post("/register", response_model=UserResponse, status_code=201)
async def register_user(
    user_create: UserCreate,
    db: Session = Depends(get_db),
) -> UserResponse:
    """Public registration endpoint. New users are always analysts."""
    existing_user = UserService.get_user_by_email(db, user_create.email)
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    existing_username = UserService.get_user_by_username(db, user_create.username)
    if existing_username:
        raise HTTPException(status_code=400, detail="Username already taken")

    sanitized_user_create = user_create.model_copy(update={"role": UserRole.ANALYST})
    created_user = UserService.create_user(db, sanitized_user_create)
    logger.info(f"New user registered: {created_user.username}")
    return created_user


@router.get("/me", response_model=UserResponse)
async def get_my_profile(current_user: User = Depends(get_current_active_user)) -> UserResponse:
    """Return current authenticated user profile."""
    return current_user