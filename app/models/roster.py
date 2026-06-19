"""RosterAssignment — one cell of the monthly roster grid (v2).

Replaces the v1 Shift + ShiftBooking ("open shift" + "claim") model. There is
no claiming: the Manager/HR assign every cell by hand (req v2.0 §4 Human-in-
the-Loop). A cell for an (employee, work_date) is EITHER:

  * a worked shift  -> shift_type_id set, absence_code NULL
  * an absence      -> absence_code set, shift_type_id NULL

Substitutions (req v2.0 §2.3): when one employee covers a gap left by another,
``substitutes_for_id`` records who they are standing in for. The substitute's
hours still accrue to the substitute and may push them into overtime.
"""

import enum
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AbsenceCode(str, enum.Enum):
    """Absence / substitution categories (req v2.0 §1.5)."""

    VACATION = "B"            # Ferie
    SICK_LEAVE = "B1"         # Malattia
    TEMP_TRANSFER = "B2"      # Trasferimento temporaneo
    FIXED_SUB = "C1"          # Sostituzione fissa
    VARIABLE_SUB = "C2"       # Sostituzione variabile
    SOLIDARITY = "SOL"        # Solidarity Hours (20H Solidarietà)


class RosterAssignment(Base):
    __tablename__ = "roster_assignments"
    __table_args__ = (
        UniqueConstraint(
            "employee_id", "work_date", name="uq_employee_workdate"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    employee_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("employees.id"), index=True
    )
    work_date: Mapped[date] = mapped_column(Date, index=True)

    # Exactly one of these two is set:
    shift_type_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("shift_types.id"), nullable=True
    )
    absence_code: Mapped[Optional[AbsenceCode]] = mapped_column(
        Enum(AbsenceCode), nullable=True
    )

    # Optional per-cell site override (flexible-location rotation)
    site_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("sites.id"), nullable=True
    )

    # Substitution linkage
    substitutes_for_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("employees.id"), nullable=True
    )

    notes: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    is_manual: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="True = set by hand; auto-fill preserves it as a fixed point",
    )
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    employee = relationship(
        "Employee", back_populates="assignments", foreign_keys=[employee_id]
    )
    substitutes_for = relationship(
        "Employee", foreign_keys=[substitutes_for_id]
    )
    shift_type = relationship("ShiftType", back_populates="assignments")
    site = relationship("Site")


class RosterChangeLog(Base):
    """Audit trail of roster modifications so the manager can review changes."""

    __tablename__ = "roster_change_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    action: Mapped[str] = mapped_column(
        String(30), comment="manual_set | manual_clear | auto_fill | cascade"
    )
    employee_name: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True
    )
    work_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    detail: Mapped[str] = mapped_column(String(400))
    changed_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
