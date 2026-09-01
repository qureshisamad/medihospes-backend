"""Roster schemas (v2) — monthly grid cells, substitution, hours/overtime."""

from datetime import date, datetime

from pydantic import BaseModel, model_validator

from app.models.roster import AbsenceCode


class CellUpsert(BaseModel):
    """Assign or update one roster cell. At most one of shift_type_id /
    absence_code (a cell is either worked or an absence). A cell may also hold
    just a free-text note (comment) with no shift or absence."""

    employee_id: int
    work_date: date
    shift_type_id: int | None = None
    absence_code: AbsenceCode | None = None
    site_id: int | None = None
    substitutes_for_id: int | None = None
    is_pending: bool = False
    notes: str | None = None

    @model_validator(mode="after")
    def _valid_combo(self):
        if self.shift_type_id is not None and self.absence_code is not None:
            raise ValueError(
                "Provide only one of shift_type_id or absence_code"
            )
        if self.is_pending and (
            self.shift_type_id is not None or self.absence_code is not None
        ):
            raise ValueError(
                "A pending cell cannot also have a shift or absence"
            )
        # A cell must carry something: a shift, an absence, a pending mark, or a note.
        if (
            self.shift_type_id is None
            and self.absence_code is None
            and not self.is_pending
            and not (self.notes and self.notes.strip())
        ):
            raise ValueError(
                "Provide a shift, an absence, a pending mark, or a note"
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
    is_pending: bool
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
