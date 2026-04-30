"""User / Employee model."""

import enum
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class UserRole(str, enum.Enum):
    STAFF = "staff"
    ADMIN = "admin"


class JobTitle(str, enum.Enum):
    ADMINISTRATIVE = "administrative"
    NURSE = "nurse"
    DOCTOR = "doctor"
    TECHNICIAN = "technician"
    SUPPORT = "support"


class ContractType(str, enum.Enum):
    PART_TIME = "part_time"
    FULL_TIME = "full_time"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    codice_fiscale: Mapped[Optional[str]] = mapped_column(
        String(16), unique=True, nullable=True, index=True
    )
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole), default=UserRole.STAFF
    )
    job_title: Mapped[JobTitle] = mapped_column(Enum(JobTitle))
    contract_type: Mapped[ContractType] = mapped_column(Enum(ContractType))
    weekly_hour_limit: Mapped[float] = mapped_column(
        Float, default=36.0, comment="Max contracted weekly hours"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    bookings = relationship("ShiftBooking", back_populates="user")
    time_entries = relationship("TimeEntry", back_populates="user")
    notifications = relationship("Notification", back_populates="user")
