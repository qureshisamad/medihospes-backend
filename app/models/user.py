"""User model — system login accounts (v2).

v2.0 has exactly two access levels, both full-edit: Manager and HR
(req v2.0 §1.2, §2.6, §4). Employees have NO access and are modelled separately
in `Employee` — they are never User rows.

(The "Administrative Operator" mentioned in the Q&A also edits the schedule;
pending confirmation it is treated as an HR-level account rather than a third
distinct permission tier — the Core Design Principles state only two levels.)
"""

import enum
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UserRole(str, enum.Enum):
    MANAGER = "manager"
    HR = "hr"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole), default=UserRole.MANAGER
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
