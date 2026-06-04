"""EmployeeCoverage — configurable cross-role substitution exceptions (v2).

Default rule (req v2.0 §1.4, §2.3): substitution is strictly role-matched —
a doctor can only be replaced by a doctor, an admin by an admin, etc.

Exceptions are per-employee and explicit: e.g. "HR can cover for a Manager".
Each row grants one employee the ability to cover one additional role. Roles
with no coverage row beyond their own are effectively non-interchangeable.
"""

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class EmployeeCoverage(Base):
    __tablename__ = "employee_coverage"
    __table_args__ = (
        UniqueConstraint(
            "employee_id", "coverable_role", name="uq_employee_coverable_role"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    employee_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("employees.id", ondelete="CASCADE"), index=True
    )
    coverable_role: Mapped[str] = mapped_column(
        String(100), comment="An additional job_title this employee may cover"
    )

    # Relationships
    employee = relationship("Employee", back_populates="coverable_roles")
