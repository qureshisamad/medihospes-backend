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

Location (house): substitutes from the SAME house are preferred. Staff flagged
flexible_location can also cover other houses and are marked is_cross_site.
Employees at a different house who are not flexible are excluded.

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
    site_id: int | None = None,
) -> list[dict]:
    """Return eligible, available substitutes for `role` on `work_date`.

    `site_id` is the house of the gap being filled — same-house staff are
    preferred and cross-house staff are only offered if flexible_location."""
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
    all_shift_types = {s.id: s for s in db.query(ShiftType).all()}

    # Hours the prospective shift would add (for overtime projection)
    added_hours = 0.0
    if shift_type_id and shift_type_id in all_shift_types:
        added_hours = all_shift_types[shift_type_id].duration_hours or 0.0

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

        # Location: same house preferred; other houses only if flexible.
        is_cross_site = False
        if site_id is not None and emp.site_id != site_id:
            if emp.flexible_location:
                is_cross_site = True
            else:
                continue  # belongs to a different house and can't cross

        # Availability: free if they have no cell, or only a REST cell that day.
        # (A rest-day person is the natural cover; a working shift or an absence
        # means they can't take it.)
        cell = (
            db.query(RosterAssignment)
            .filter(
                RosterAssignment.employee_id == emp.id,
                RosterAssignment.work_date == work_date,
            )
            .first()
        )
        on_rest = False
        if cell is not None:
            if cell.absence_code is not None:
                continue  # away (vacation/sick) — can't cover
            st = all_shift_types.get(cell.shift_type_id)
            if st and (st.duration_hours or 0) > 0:
                continue  # already working a real shift
            on_rest = True  # rest day → available to cover

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
                "is_cross_site": is_cross_site,
                "on_rest": on_rest,
                "booked_hours": booked,
                "monthly_hour_limit": limit,
                "remaining_hours": remaining,
                "would_cause_overtime": would_overtime,
            }
        )

    # Same-house & same-role first, then by most remaining capacity
    out.sort(
        key=lambda c: (c["is_cross_site"], c["is_cross_role"], -c["remaining_hours"])
    )
    return out
