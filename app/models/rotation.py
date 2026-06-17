"""Rotation library (v2) — the "shifting library" for a staff category.

A RotationPattern is an ordered, repeating cycle of shift types defined for one
category (job_title), e.g. the Educatori cycle: M/Ed → P/N/Ed → S → R.

The manager fills in the first day of the month for each employee; the auto-fill
service then advances every employee through this cycle for the rest of the
month (each employee offset by whatever they were given on day 1). The result
is always editable afterwards — absences entered later are never overwritten.

This is intentionally per-category: it is rolled out to Educatori first, then to
other categories over time (client request, June 2026).
"""

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class RotationPattern(Base):
    __tablename__ = "rotation_patterns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    job_title: Mapped[str] = mapped_column(
        String(100), index=True, comment="Category this rotation applies to"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    steps = relationship(
        "RotationStep",
        back_populates="pattern",
        cascade="all, delete-orphan",
        order_by="RotationStep.position",
    )


class RotationStep(Base):
    """One position in the cycle, pointing at the shift type worked there."""

    __tablename__ = "rotation_steps"
    __table_args__ = (
        UniqueConstraint("pattern_id", "position", name="uq_pattern_position"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    pattern_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("rotation_patterns.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer, comment="0-based order in cycle")
    shift_type_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("shift_types.id")
    )

    pattern = relationship("RotationPattern", back_populates="steps")
    shift_type = relationship("ShiftType")
