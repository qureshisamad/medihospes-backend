"""Employee model — a scheduled person (v2).

Employees have NO system access (req v2.0 §1.2 / §2.6): they never log in.
They are *data the manager edits*, not accounts. Login accounts live in the
`User` model (Manager / HR only).

Contract awareness (req v2.0 §1.4, §2.4): every employee's role, site,
location and contractual hour limit are stored here. Part-time vs full-time
"parameter hours" (e.g. 104.28h vs 130.35h, req v2.0 §1.6) are monthly and
drive the overtime ("ORE SUPP.") calculation.
"""

import enum
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ContractType(str, enum.Enum):
    PART_TIME = "part_time"
    FULL_TIME = "full_time"


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    codice_fiscale: Mapped[Optional[str]] = mapped_column(
        String(16), unique=True, nullable=True, index=True
    )

    # --- Role / placement (from contract) ---
    department_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("departments.id"), index=True
    )
    site_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("sites.id"), nullable=True, index=True
    )
    job_title: Mapped[str] = mapped_column(
        String(100), comment="Role, e.g. doctor, admin, OSS — drives substitution"
    )
    location: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="Contract location (e.g. Location X)"
    )

    # --- Contract hours ---
    contract_type: Mapped[ContractType] = mapped_column(Enum(ContractType))
    monthly_hour_limit: Mapped[float] = mapped_column(
        Float,
        comment="Contractual parameter hours per month (e.g. 104.28 / 130.35)",
    )

    # --- Flexibility flags (req v2.0 §1.4) ---
    flexible_shift: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="Rotates morning<->afternoon weekly"
    )
    flexible_location: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="Rotates between locations weekly"
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    department = relationship("Department", back_populates="employees")
    site = relationship("Site", back_populates="employees")
    assignments = relationship(
        "RosterAssignment",
        back_populates="employee",
        foreign_keys="RosterAssignment.employee_id",
    )
    coverable_roles = relationship(
        "EmployeeCoverage",
        back_populates="employee",
        cascade="all, delete-orphan",
    )
