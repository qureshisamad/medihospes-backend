"""Clinic / Location model."""

from typing import Optional

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Clinic(Base):
    __tablename__ = "clinics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(150), unique=True)
    code: Mapped[str] = mapped_column(
        String(20), unique=True, comment="Short code e.g. ME-I, ME-II"
    )
    address: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)

    # Relationships
    shifts = relationship("Shift", back_populates="clinic")
