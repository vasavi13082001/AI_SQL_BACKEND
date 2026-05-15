"""Common utilities and helpers."""
import hashlib
from datetime import datetime, timedelta
from typing import Optional
import logging

logger = logging.getLogger(__name__)


def hash_password(password: str) -> str:
    """Hash password using SHA256."""
    # In production, use bcrypt or argon2
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash."""
    return hash_password(plain_password) == hashed_password


def get_pagination_params(skip: int = 0, limit: int = 100) -> tuple[int, int]:
    """Validate and return pagination parameters."""
    skip = max(0, skip)
    limit = min(max(1, limit), 1000)  # Max 1000 items
    return skip, limit


def format_datetime(dt: Optional[datetime]) -> Optional[str]:
    """Format datetime to ISO string."""
    if dt is None:
        return None
    return dt.isoformat()


def parse_datetime(dt_str: str) -> datetime:
    """Parse ISO format datetime string."""
    return datetime.fromisoformat(dt_str)


def calculate_time_diff(start: datetime, end: datetime) -> str:
    """Calculate human-readable time difference."""
    diff = end - start
    seconds = diff.total_seconds()
    
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        return f"{int(seconds // 60)}m"
    else:
        return f"{int(seconds // 3600)}h"


def is_valid_email(email: str) -> bool:
    """Basic email validation."""
    return "@" in email and "." in email.split("@")[1]


def sanitize_search_query(query: str) -> str:
    """Sanitize search query to prevent SQL injection."""
    # Remove special characters that could cause issues
    return query.replace("%", "").replace("_", "").strip()


def paginate_queryset(queryset, skip: int, limit: int):
    """Apply pagination to queryset."""
    return queryset.offset(skip).limit(limit).all()
