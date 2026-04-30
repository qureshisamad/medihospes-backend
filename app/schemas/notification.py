"""Notification response schemas."""

from datetime import datetime

from pydantic import BaseModel


class NotificationRead(BaseModel):
    id: int
    notification_type: str
    title: str
    message: str
    related_shift_id: int | None
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}
