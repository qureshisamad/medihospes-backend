"""Rotation library schemas (v2)."""

from pydantic import BaseModel


class RotationStepRead(BaseModel):
    position: int
    shift_type_id: int

    model_config = {"from_attributes": True}


class RotationPatternCreate(BaseModel):
    name: str
    job_title: str
    # Ordered cycle: shift_type_id at each position (index = position)
    shift_type_ids: list[int]


class RotationPatternUpdate(BaseModel):
    name: str | None = None
    job_title: str | None = None
    is_active: bool | None = None
    shift_type_ids: list[int] | None = None


class RotationPatternRead(BaseModel):
    id: int
    name: str
    job_title: str
    is_active: bool
    shift_type_ids: list[int]

    model_config = {"from_attributes": True}


class AutoFillRequest(BaseModel):
    year: int
    month: int
    pattern_id: int
    department_id: int | None = None
    # True: stagger starts automatically (balanced, no manual day-1 needed).
    # False: use each employee's existing day-1 shift as their start.
    auto_stagger: bool = True


class AutoFillResult(BaseModel):
    filled_cells: int
    employees_filled: int
    skipped: list[str]      # manual mode: employees with no valid day-1 seed
    warnings: list[str]     # e.g. duplicate day-1 shifts → identical schedules
