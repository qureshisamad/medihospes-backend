"""Shift Booking model — links a user to a claimed shift."""

import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class BookingStatus(str, enum.Enum):
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


class ShiftBooking(Base):
    __tablename__ = "shift_bookings"
    __table_args__ = (
        UniqueConstraint("shift_id", "user_id", name="uq_shift_user"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    shift_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("shifts.id"), index=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), index=True
    )
    status: Mapped[BookingStatus] = mapped_column(
        Enum(BookingStatus), default=BookingStatus.CONFIRMED
    )
    booked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    shift = relationship("Shift", back_populates="bookings")
    user = relationship("User", back_populates="bookings")
