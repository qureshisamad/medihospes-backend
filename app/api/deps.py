"""Shared FastAPI dependencies — auth, DB session.

v2.0 has two access levels, BOTH full-edit: Manager and HR (req v2.0 §1.2).
There is therefore no read-only tier — any authenticated user may edit. The
``require_edit`` dependency exists to make that intent explicit at call sites
(and to give us one place to tighten later if a read-only role is ever added).
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User

bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Decode JWT and return the authenticated User (Manager or HR)."""
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload["sub"])
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    return user


def require_edit(current_user: User = Depends(get_current_user)) -> User:
    """Both Manager and HR have full edit rights — this just requires login."""
    return current_user
