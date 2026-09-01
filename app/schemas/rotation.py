"""Rotation library schemas (v2)."""

from datetime import date, datetime

from pydantic import BaseModel


class RotationStepRead(BaseModel):
    position: int
    shift_type_id: int

    model_config = {"from_attributes": True}


class CoverageItem(BaseModel):
    shift_type_id: int
    required_count: int = 1


class RotationPatternCreate(BaseModel):
    name: str
    job_title: str
    site_id: int | None = None  # house this rotation staffs (None = category-wide)
    # Ordered cycle: shift_type_id at each position (index = position)
    shift_type_ids: list[int]
    min_rest_hours: float = 11.0
    coverage: list[CoverageItem] = []


class RotationPatternUpdate(BaseModel):
    name: str | None = None
    job_title: str | None = None
    site_id: int | None = None
    is_active: bool | None = None
    shift_type_ids: list[int] | None = None
    min_rest_hours: float | None = None
    coverage: list[CoverageItem] | None = None


class RotationPatternRead(BaseModel):
    id: int
    name: str
    job_title: str
    site_id: int | None
    site_name: str | None
    is_active: bool
    shift_type_ids: list[int]
    min_rest_hours: float
    coverage: list[CoverageItem]

    model_config = {"from_attributes": True}


class AutoFillRequest(BaseModel):
    year: int
    month: int
    pattern_id: int
    department_id: int | None = None
    # Only used by the staggered-cycle fallback (when no coverage is defined).
    auto_stagger: bool = True
    # True = discard manual edits and fill from scratch. Default keeps them.
    reset_manual: bool = False
    # Surplus staff to bench as "pending" (excluded from the rotation) when the
    # house has more people than the coverage total needs (objective: pending).
    pending_employee_ids: list[int] = []


class CascadeRequest(BaseModel):
    """Re-derive ONE employee's later days from a (just-edited) cell."""

    employee_id: int
    work_date: date
    pattern_id: int


class CascadeResult(BaseModel):
    updated: int


class SwapRequest(BaseModel):
    """Exchange two employees' cells on a day (assign a shift to one without
    leaving it on the other — keeps coverage balanced)."""

    employee_a_id: int
    employee_b_id: int
    work_date: date


class ChangeLogRead(BaseModel):
    id: int
    action: str
    employee_name: str | None
    work_date: date | None
    detail: str
    changed_at: datetime

    model_config = {"from_attributes": True}


class AutoFillResult(BaseModel):
    filled_cells: int
    employees_filled: int
    skipped: list[str]      # cycle mode: employees with no valid day-1 seed
    warnings: list[str]     # e.g. shift-order rest check
    unmet: list[str]        # per-day coverage shortfalls (e.g. from absences)
    alerts: list[str] = []  # manager-facing: headcount≠total, bad day-1 seed
