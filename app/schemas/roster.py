"""Roster schemas (v2) — monthly grid cells, substitution, hours/overtime."""

from datetime import date, datetime

from pydantic import BaseModel, model_validator

from app.models.roster import AbsenceCode


class CellUpsert(BaseModel):
    """Assign or update one roster cell. Exactly one of shift_type_id /
    absence_code must be provided (a cell is either worked or an absence)."""

    employee_id: int
    work_date: date
    shift_type_id: int | None = None
    absence_code: AbsenceCode | None = None
    site_id: int | None = None
    substitutes_for_id: int | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def _exactly_one(self):
        if bool(self.shift_type_id) == bool(self.absence_code):
            raise ValueError(
                "Provide exactly one of shift_type_id or absence_code"
            )
        return self


class CellRead(BaseModel):
    id: int
    employee_id: int
    work_date: date
    shift_type_id: int | None
    absence_code: AbsenceCode | None
    site_id: int | None
    substitutes_for_id: int | None
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SubstituteCandidate(BaseModel):
    """A human-in-the-loop suggestion — never auto-applied (req v2.0 §4)."""

    employee_id: int
    name: str
    job_title: str
    is_cross_role: bool
    is_cross_site: bool = False
    on_rest: bool = False
    booked_hours: float
    monthly_hour_limit: float
    remaining_hours: float
    would_cause_overtime: bool


class EmployeeHours(BaseModel):
    employee_id: int
    name: str
    job_title: str
    department: str
    contract_type: str
    monthly_hour_limit: float
    worked_hours: float
    overtime_hours: float       # ORE SUPP.
    remaining_hours: float
    utilisation_pct: float
    approaching_limit: bool     # fires the manager alert
    over_limit: bool
