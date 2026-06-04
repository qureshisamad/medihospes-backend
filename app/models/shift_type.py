"""ShiftType model — configurable shift definitions (v2).

Replaces the v1 hard-coded MORNING/EVENING/NIGHT enum. The manager confirmed
5 shift types that vary by site/location/role (req v2.0 §1.3). Known so far:

    A   (Morning)      08:00 - 14:00   6h
    B   (Afternoon)    09:00 - 16:30   7h
    C   (Night)        21:00 - 00:30   8h   (crosses midnight)
    P/N (Aftn/Night)   15:00 - 24:00   9h
    5th type           TBD             TBD

Times are stored as plain clock times; duration is stored explicitly so the
roster/overtime engine never has to guess across midnight.
"""

from datetime import time
from typing import Optional

from sqlalchemy import Boolean, Float, Integer, String, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ShiftType(Base):
    __tablename__ = "shift_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    code: Mapped[str] = mapped_column(
        String(10), unique=True, index=True, comment="e.g. A, B, C, P/N"
    )
    name: Mapped[str] = mapped_column(String(100))
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    duration_hours: Mapped[float] = mapped_column(
        Float, comment="Paid duration in hours (handles midnight crossing)"
    )
    crosses_midnight: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    assignments = relationship("RosterAssignment", back_populates="shift_type")
