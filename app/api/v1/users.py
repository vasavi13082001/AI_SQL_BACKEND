"""User API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.user_service import UserService
from app.schemas.user import UserCreate, UserResponse, UserUpdate, UserListResponse
from logging import getLogger

logger = getLogger(__name__)

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/", response_model=list[UserListResponse])
async def list_users(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000)
):
    """List all users with pagination."""
    users = UserService.get_users(db, skip=skip, limit=limit)
    logger.info(f"Fetched {len(users)} users")
    return users


@router.post("/", response_model=UserResponse, status_code=201)
async def create_user(
    user_create: UserCreate,
    db: Session = Depends(get_db)
):
    """Create a new user."""
    # Check if user already exists
    existing_user = UserService.get_user_by_email(db, user_create.email)
    if existing_user:
        logger.warning(f"Attempt to create user with existing email: {user_create.email}")
        raise HTTPException(status_code=400, detail="Email already registered")
    
    existing_username = UserService.get_user_by_username(db, user_create.username)
    if existing_username:
        logger.warning(f"Attempt to create user with existing username: {user_create.username}")
        raise HTTPException(status_code=400, detail="Username already taken")
    
    user = UserService.create_user(db, user_create)
    return user


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, db: Session = Depends(get_db)):
    """Get a specific user by ID."""
    user = UserService.get_user(db, user_id)
    if not user:
        logger.warning(f"User not found: {user_id}")
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_update: UserUpdate,
    db: Session = Depends(get_db)
):
    """Update a user's information."""
    user = UserService.update_user(db, user_id, user_update)
    if not user:
        logger.warning(f"User not found for update: {user_id}")
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.delete("/{user_id}", status_code=204)
async def delete_user(user_id: int, db: Session = Depends(get_db)):
    """Delete a user."""
    success = UserService.delete_user(db, user_id)
    if not success:
        logger.warning(f"User not found for deletion: {user_id}")
        raise HTTPException(status_code=404, detail="User not found")
    return None
