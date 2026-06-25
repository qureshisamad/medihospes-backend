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
from app.models.roster import RosterAssignment, RosterChangeLog
from app.models.rotation import RotationPattern
from app.models.shift_type import ShiftType
from app.models.user import User
from app.schemas.roster import (
    CellRead,
    CellUpsert,
    EmployeeHours,
    SubstituteCandidate,
)
from app.schemas.rotation import (
    AutoFillRequest,
    AutoFillResult,
    CascadeRequest,
    CascadeResult,
    ChangeLogRead,
)
from app.services.hours_service import employee_hours_summary, month_bounds
from app.services.rotation_service import auto_fill_month, cascade_employee
from app.services.substitution_service import suggest_substitutes

router = APIRouter(prefix="/roster", tags=["Roster"])


def _log(
    db: Session,
    action: str,
    detail: str,
    user_id: int,
    employee_name: str | None = None,
    work_date=None,
) -> None:
    db.add(
        RosterChangeLog(
            action=action,
            detail=detail,
            employee_name=employee_name,
            work_date=work_date,
            changed_by=user_id,
        )
    )


@router.get("", response_model=list[CellRead])
def get_roster(
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    department_id: int | None = Query(None),
    job_title: str | None = Query(None),
    site_id: int | None = Query(None),
    db: Session = Depends(get_db),
    _u: User = Depends(require_edit),
):
    """Return every roster cell for the month (optionally one dept/role/house)."""
    start, end = month_bounds(year, month)
    q = db.query(RosterAssignment).filter(
        RosterAssignment.work_date >= start,
        RosterAssignment.work_date <= end,
    )
    if department_id is not None or job_title is not None or site_id is not None:
        q = q.join(Employee, Employee.id == RosterAssignment.employee_id)
        if department_id is not None:
            q = q.filter(Employee.department_id == department_id)
        if job_title is not None:
            q = q.filter(Employee.job_title == job_title)
        if site_id is not None:
            q = q.filter(Employee.site_id == site_id)
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
    cell.is_manual = True  # hand-set → auto-fill will preserve it

    new_label = (
        st.code if body.shift_type_id is not None else body.absence_code.value
    )
    _log(
        db,
        "manual_set",
        f"Set {new_label}",
        user.id,
        employee_name=f"{emp.last_name} {emp.first_name}",
        work_date=body.work_date,
    )

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
        emp = db.query(Employee).filter(Employee.id == employee_id).first()
        db.delete(cell)
        _log(
            db,
            "manual_clear",
            "Cleared cell",
            _u.id,
            employee_name=(f"{emp.last_name} {emp.first_name}" if emp else None),
            work_date=work_date,
        )
        db.commit()


@router.delete("/month")
def clear_month(
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    department_id: int | None = Query(None),
    job_title: str | None = Query(None),
    site_id: int | None = Query(None),
    keep_absences: bool = Query(
        False, description="If true, keep absence cells (vacation/sick/etc.)"
    ),
    db: Session = Depends(get_db),
    user: User = Depends(require_edit),
):
    """Clear every roster cell for the month within the current scope
    (optional department/category/house). Use keep_absences to preserve entered
    vacations/sick leave. Logged so the action is auditable."""
    start, end = month_bounds(year, month)
    q = db.query(RosterAssignment).filter(
        RosterAssignment.work_date >= start,
        RosterAssignment.work_date <= end,
    )
    if department_id is not None or job_title is not None or site_id is not None:
        emp_ids = db.query(Employee.id)
        if department_id is not None:
            emp_ids = emp_ids.filter(Employee.department_id == department_id)
        if job_title is not None:
            emp_ids = emp_ids.filter(Employee.job_title == job_title)
        if site_id is not None:
            emp_ids = emp_ids.filter(Employee.site_id == site_id)
        q = q.filter(RosterAssignment.employee_id.in_(emp_ids.subquery()))
    if keep_absences:
        q = q.filter(RosterAssignment.absence_code.is_(None))

    count = q.count()
    q.delete(synchronize_session=False)

    scope = []
    if department_id is not None:
        scope.append(f"dept {department_id}")
    if job_title is not None:
        scope.append(job_title)
    if site_id is not None:
        scope.append(f"site {site_id}")
    _log(
        db,
        "clear_month",
        f"Cleared {count} cells for {year}-{month:02d}"
        + (f" ({', '.join(scope)})" if scope else "")
        + (" — absences kept" if keep_absences else ""),
        user.id,
    )
    db.commit()
    return {"cleared": count}


@router.post("/auto-fill", response_model=AutoFillResult)
def auto_fill(
    body: AutoFillRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_edit),
):
    """Auto-fill the month for a category. Manual edits and absences are kept
    as fixed points (pass reset_manual=True to discard manual edits and refill
    from scratch). The system reports gaps it can't staff; it never overrides a
    human decision silently (req v2.0 §4)."""
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
        reset_manual=body.reset_manual,
    )
    mode = "reset (manual edits cleared)" if body.reset_manual else "manual edits kept"
    _log(
        db,
        "auto_fill",
        f"Auto-fill {pattern.name} {body.year}-{body.month:02d} "
        f"— {result['filled_cells']} cells, {mode}",
        user.id,
    )
    db.commit()
    return AutoFillResult(**result)


@router.post("/cascade", response_model=CascadeResult)
def cascade(
    body: CascadeRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_edit),
):
    """Re-derive ONE employee's later days from the (just-edited) cell, leaving
    everyone else untouched. Uses the category's rotation cycle order."""
    pattern = (
        db.query(RotationPattern)
        .filter(RotationPattern.id == body.pattern_id)
        .first()
    )
    if not pattern:
        raise HTTPException(status_code=404, detail="Rotation pattern not found")
    emp = db.query(Employee).filter(Employee.id == body.employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    result = cascade_employee(
        db, pattern, body.employee_id, body.work_date, user.id
    )
    _log(
        db,
        "cascade",
        f"Cascaded {result['updated']} following day(s) from "
        f"{body.work_date.isoformat()}",
        user.id,
        employee_name=f"{emp.last_name} {emp.first_name}",
        work_date=body.work_date,
    )
    db.commit()
    return CascadeResult(**result)


@router.get("/history", response_model=list[ChangeLogRead])
def get_history(
    limit: int = Query(100, le=500),
    db: Session = Depends(get_db),
    _u: User = Depends(require_edit),
):
    """Most recent roster changes (manual edits, auto-fills, cascades)."""
    return (
        db.query(RosterChangeLog)
        .order_by(RosterChangeLog.changed_at.desc())
        .limit(limit)
        .all()
    )


@router.get("/substitutes", response_model=list[SubstituteCandidate])
def get_substitutes(
    role: str = Query(..., description="Role/job_title of the gap to fill"),
    work_date: date = Query(...),
    exclude_employee_id: int | None = Query(None),
    shift_type_id: int | None = Query(None),
    site_id: int | None = Query(None, description="House of the gap to fill"),
    db: Session = Depends(get_db),
    _u: User = Depends(require_edit),
):
    """Suggest valid, available substitutes — the manager picks one. The system
    never auto-assigns (req v2.0 §4). Same-house staff first; flexible-location
    staff offered as cross-house."""
    return suggest_substitutes(
        db, role, work_date, exclude_employee_id, shift_type_id, site_id
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
