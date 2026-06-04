"""Department model — Administrative, OSS, Auxiliaries, COC (v2)."""

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Department(Base):
    """A clinic department. The four confirmed departments are
    Administrative, OSS, Auxiliaries and COC (req v2.0 §1.1)."""

    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)

    # Relationships
    employees = relationship("Employee", back_populates="department")
