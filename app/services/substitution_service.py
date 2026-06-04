"""Substitution suggestion engine (v2).

When an absence opens a gap, the manager needs a list of *valid, available*
substitutes to choose from. This module produces that list — it NEVER assigns
anyone (req v2.0 §4 Human-in-the-Loop, §2.4).

Eligibility (req v2.0 §1.4, §2.3):
  * Role-matched by default: same job_title as the role being covered.
  * Cross-role exceptions: employees with an explicit EmployeeCoverage row for
    that role (e.g. HR covering a Manager) are included and flagged.
  * Roles with no matching/coverage employee are effectively non-interchangeable
    and simply yield no candidates.

Availability: the candidate has no existing roster cell on that date.
Overtime awareness (req v2.0 §2.3): if taking the shift would push the
substitute past their monthly contractual limit, that is flagged so the manager
can weigh it.
"""

from datetime import date

from sqlalchemy.orm import Session

from app.models.coverage import EmployeeCoverage
from app.models.employee import Employee
from app.models.roster import RosterAssignment
from app.models.shift_type import ShiftType
from app.services.hours_service import worked_hours


def suggest_substitutes(
    db: Session,
    role: str,
    work_date: date,
    exclude_employee_id: int | None = None,
    shift_type_id: int | None = None,
) -> list[dict]:
    """Return eligible, available substitutes for `role` on `work_date`."""
    # Roles this candidate could cover via cross-role exception
    cross_role_ids = {
        r.employee_id
        for r in db.query(EmployeeCoverage.employee_id)
        .filter(EmployeeCoverage.coverable_role == role)
        .all()
    }

    candidates = (
        db.query(Employee)
        .filter(Employee.is_active.is_(True))
        .all()
    )

    # Hours the prospective shift would add (for overtime projection)
    added_hours = 0.0
    if shift_type_id:
        st = db.query(ShiftType).filter(ShiftType.id == shift_type_id).first()
        if st:
            added_hours = st.duration_hours

    out: list[dict] = []
    for emp in candidates:
        if exclude_employee_id and emp.id == exclude_employee_id:
            continue

        is_cross_role = False
        if emp.job_title != role:
            if emp.id in cross_role_ids:
                is_cross_role = True
            else:
                continue  # role not interchangeable for this employee

        # Availability: no existing cell that day
        busy = (
            db.query(RosterAssignment)
            .filter(
                RosterAssignment.employee_id == emp.id,
                RosterAssignment.work_date == work_date,
            )
            .first()
        )
        if busy:
            continue

        booked = worked_hours(db, emp.id, work_date.year, work_date.month)
        limit = emp.monthly_hour_limit or 0.0
        remaining = round(max(0.0, limit - booked), 2)
        would_overtime = (booked + added_hours) > limit if limit else False

        out.append(
            {
                "employee_id": emp.id,
                "name": f"{emp.first_name} {emp.last_name}",
                "job_title": emp.job_title,
                "is_cross_role": is_cross_role,
                "booked_hours": booked,
                "monthly_hour_limit": limit,
                "remaining_hours": remaining,
                "would_cause_overtime": would_overtime,
            }
        )

    # Same-role first, then by most remaining capacity
    out.sort(key=lambda c: (c["is_cross_role"], -c["remaining_hours"]))
    return out
