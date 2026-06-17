"""Roster endpoints (v2) — the monthly grid, substitution & hours.

This is the heart of v2.0: Manager/HR fill in each (employee, day) cell by
hand. The system validates and calculates but never assigns anyone itself
(req v2.0 §4 Human-in-the-Loop).
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import require_edit
from app.core.database import get_db
from app.models.employee import Employee
from app.models.roster import RosterAssignment
from app.models.rotation import RotationPattern
from app.models.shift_type import ShiftType
from app.models.user import User
from app.schemas.roster import (
    CellRead,
    CellUpsert,
    EmployeeHours,
    SubstituteCandidate,
)
from app.schemas.rotation import AutoFillRequest, AutoFillResult
from app.services.hours_service import employee_hours_summary, month_bounds
from app.services.rotation_service import auto_fill_month
from app.services.substitution_service import suggest_substitutes

router = APIRouter(prefix="/roster", tags=["Roster"])


@router.get("", response_model=list[CellRead])
def get_roster(
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    department_id: int | None = Query(None),
    job_title: str | None = Query(None),
    db: Session = Depends(get_db),
    _u: User = Depends(require_edit),
):
    """Return every roster cell for the given month (optionally one dept/role)."""
    start, end = month_bounds(year, month)
    q = db.query(RosterAssignment).filter(
        RosterAssignment.work_date >= start,
        RosterAssignment.work_date <= end,
    )
    if department_id is not None or job_title is not None:
        q = q.join(Employee, Employee.id == RosterAssignment.employee_id)
        if department_id is not None:
            q = q.filter(Employee.department_id == department_id)
        if job_title is not None:
            q = q.filter(Employee.job_title == job_title)
    return q.order_by(RosterAssignment.work_date).all()


@router.put("/cell", response_model=CellRead)
def upsert_cell(
    body: CellUpsert,
    db: Session = Depends(get_db),
    user: User = Depends(require_edit),
):
    """Create or replace a single roster cell (assign a shift or an absence)."""
    emp = db.query(Employee).filter(Employee.id == body.employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    if body.shift_type_id is not None:
        st = (
            db.query(ShiftType)
            .filter(ShiftType.id == body.shift_type_id)
            .first()
        )
        if not st:
            raise HTTPException(status_code=404, detail="Shift type not found")

    cell = (
        db.query(RosterAssignment)
        .filter(
            RosterAssignment.employee_id == body.employee_id,
            RosterAssignment.work_date == body.work_date,
        )
        .first()
    )
    if cell is None:
        cell = RosterAssignment(
            employee_id=body.employee_id,
            work_date=body.work_date,
            created_by=user.id,
        )
        db.add(cell)

    cell.shift_type_id = body.shift_type_id
    cell.absence_code = body.absence_code
    cell.site_id = body.site_id
    cell.substitutes_for_id = body.substitutes_for_id
    cell.notes = body.notes

    db.commit()
    db.refresh(cell)
    return cell


@router.delete("/cell", status_code=204)
def delete_cell(
    employee_id: int = Query(...),
    work_date: date = Query(...),
    db: Session = Depends(get_db),
    _u: User = Depends(require_edit),
):
    cell = (
        db.query(RosterAssignment)
        .filter(
            RosterAssignment.employee_id == employee_id,
            RosterAssignment.work_date == work_date,
        )
        .first()
    )
    if cell:
        db.delete(cell)
        db.commit()


@router.post("/auto-fill", response_model=AutoFillResult)
def auto_fill(
    body: AutoFillRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_edit),
):
    """Propagate a rotation across the month from each employee's day-1 seed.

    The manager sets day 1 for each employee first; this fills days 2..end by
    advancing each through the cycle. Absences already entered are preserved.
    Every cell remains editable afterwards (req: 'always modifiable')."""
    pattern = (
        db.query(RotationPattern)
        .filter(RotationPattern.id == body.pattern_id)
        .first()
    )
    if not pattern:
        raise HTTPException(status_code=404, detail="Rotation pattern not found")

    result = auto_fill_month(
        db,
        pattern,
        body.year,
        body.month,
        user.id,
        body.department_id,
        auto_stagger=body.auto_stagger,
    )
    return AutoFillResult(**result)


@router.get("/substitutes", response_model=list[SubstituteCandidate])
def get_substitutes(
    role: str = Query(..., description="Role/job_title of the gap to fill"),
    work_date: date = Query(...),
    exclude_employee_id: int | None = Query(None),
    shift_type_id: int | None = Query(None),
    db: Session = Depends(get_db),
    _u: User = Depends(require_edit),
):
    """Suggest valid, available substitutes — the manager picks one. The system
    never auto-assigns (req v2.0 §4)."""
    return suggest_substitutes(
        db, role, work_date, exclude_employee_id, shift_type_id
    )


@router.get("/hours", response_model=list[EmployeeHours])
def get_hours(
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    department_id: int | None = Query(None),
    db: Session = Depends(get_db),
    _u: User = Depends(require_edit),
):
    """Per-employee worked hours, overtime (ORE SUPP.) and limit alerts."""
    q = db.query(Employee).filter(Employee.is_active.is_(True))
    if department_id is not None:
        q = q.filter(Employee.department_id == department_id)
    employees = q.order_by(Employee.last_name).all()
    return [employee_hours_summary(db, e, year, month) for e in employees]


@router.get("/alerts", response_model=list[EmployeeHours])
def get_alerts(
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    db: Session = Depends(get_db),
    _u: User = Depends(require_edit),
):
    """Only employees approaching or over their monthly limit."""
    employees = db.query(Employee).filter(Employee.is_active.is_(True)).all()
    summaries = [employee_hours_summary(db, e, year, month) for e in employees]
    return [s for s in summaries if s["approaching_limit"] or s["over_limit"]]
