"""Hours & overtime engine (v2).

Calculates, per employee per month: hours worked, overtime ("ORE SUPP." —
hours beyond the contractual monthly limit, req v2.0 §1.6) and the remaining
allowance. Raises the manager-facing "approaching limit" alert.

CALCULATE-ONLY: this module never changes a schedule. It surfaces numbers and
alerts; a human decides what to do (req v2.0 §4).

NOTE: the exact part-time parameter-hours formula (e.g. 104.28 vs 130.35) is a
documented OPEN item (req v2.0 §2.5) — until the meeting clarifies it, the
monthly limit stored on the employee contract is treated as the cap.
"""

import calendar
from datetime import date

from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.roster import RosterAssignment
from app.models.shift_type import ShiftType

# Alert when the employee has used this fraction of their monthly hours.
APPROACHING_THRESHOLD = 0.90


def month_bounds(year: int, month: int) -> tuple[date, date]:
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def worked_hours(db: Session, employee_id: int, year: int, month: int) -> float:
    """Sum the duration of all WORKED (non-absence) cells in the month.

    Substitution shifts count toward the substitute's own hours, so no special
    casing is needed here — the cell belongs to whoever actually works it."""
    start, end = month_bounds(year, month)
    rows = (
        db.query(ShiftType.duration_hours)
        .join(RosterAssignment, RosterAssignment.shift_type_id == ShiftType.id)
        .filter(
            RosterAssignment.employee_id == employee_id,
            RosterAssignment.work_date >= start,
            RosterAssignment.work_date <= end,
        )
        .all()
    )
    return round(sum(r.duration_hours for r in rows), 2)


def employee_hours_summary(
    db: Session, employee: Employee, year: int, month: int
) -> dict:
    worked = worked_hours(db, employee.id, year, month)
    limit = employee.monthly_hour_limit or 0.0
    overtime = round(max(0.0, worked - limit), 2)
    remaining = round(max(0.0, limit - worked), 2)
    utilisation = round((worked / limit * 100) if limit else 0.0, 1)
    return {
        "employee_id": employee.id,
        "name": f"{employee.first_name} {employee.last_name}",
        "job_title": employee.job_title,
        "department": employee.department.name if employee.department else "",
        "contract_type": employee.contract_type.value,
        "monthly_hour_limit": limit,
        "worked_hours": worked,
        "overtime_hours": overtime,
        "remaining_hours": remaining,
        "utilisation_pct": utilisation,
        "approaching_limit": limit > 0 and worked >= limit * APPROACHING_THRESHOLD
        and worked <= limit,
        "over_limit": worked > limit,
    }
