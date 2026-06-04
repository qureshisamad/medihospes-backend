"""Site / Location model (v2 — reshaped from Clinic).

A Site is a physical facility (e.g. ME-I, ME-II). The geolocation fields from
v1 are dropped: v2.0 has no clock-in / geofencing. "Location" in the contract
sense (the flexible Location X / Location Y rotation, req v2.0 §1.4) is modelled
on the Employee contract, not here, pending clarification of site-vs-location.
"""

from typing import Optional

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Site(Base):
    __tablename__ = "sites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(150), unique=True)
    code: Mapped[str] = mapped_column(
        String(20), unique=True, comment="Short code e.g. ME-I, ME-II"
    )
    address: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)

    # Relationships
    employees = relationship("Employee", back_populates="site")
