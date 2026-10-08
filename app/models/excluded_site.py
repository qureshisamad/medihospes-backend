"""EmployeeExcludedSite — per-employee site restrictions (v2, "Dipendenti
Speciali" location half).

Some staff — typically gap-fillers who move between houses — must NOT be
scheduled at certain sites. Each row excludes one employee from one site. This
is an EXCLUSION list: the person is otherwise treated as available (subject to
their flexibility), minus these houses.

Enforcement (mirrors the shift_restriction timing rule): a substitute is not
offered for a gap in an excluded house, and a manual assignment / cross-house
loan into an excluded house is blocked.
"""

from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class EmployeeExcludedSite(Base):
    __tablename__ = "employee_excluded_sites"
    __table_args__ = (
        UniqueConstraint(
            "employee_id", "site_id", name="uq_employee_excluded_site"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    employee_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("employees.id", ondelete="CASCADE"), index=True
    )
    site_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sites.id", ondelete="CASCADE"), index=True
    )

    # Relationships
    employee = relationship("Employee", back_populates="excluded_sites")
