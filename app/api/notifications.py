"""Notification endpoints — list unread, mark as read."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.notification import Notification
from app.models.user import User
from app.schemas.notification import NotificationRead

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("/", response_model=list[NotificationRead])
def list_notifications(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return unread notifications for the authenticated user, newest first."""
    notifications = (
        db.query(Notification)
        .filter(
            Notification.user_id == user.id,
            Notification.is_read == False,  # noqa: E712
        )
        .order_by(Notification.created_at.desc())
        .all()
    )
    return notifications


@router.post("/{notification_id}/read", status_code=204)
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Mark a single notification as read. Verifies ownership."""
    notification = (
        db.query(Notification)
        .filter(Notification.id == notification_id)
        .first()
    )
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )
    if notification.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to modify this notification",
        )
    notification.is_read = True
    db.commit()
