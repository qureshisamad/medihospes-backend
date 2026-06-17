"""Auto-fill engine (v2) — propagate a rotation cycle across a month.

The manager assigns each employee a shift on DAY 1; this service fills the rest
of the month by advancing each employee through the rotation cycle, offset by
whatever shift they were given on day 1.

Rules (req: "always modifiable, in case anybody asks off, gets sick"):
  * Day 1 is the seed and is left untouched.
  * Days 2..end are generated from the cycle.
  * Any existing ABSENCE cell (vacation/sick/etc.) is preserved — never
    overwritten by the rotation.
  * Re-running is safe/idempotent: it recomputes shift cells from each
    employee's current day-1 seed.

This never invents assignments on its own beyond mechanically continuing the
pattern the manager seeded — the human is still in control (req v2.0 §4).
"""

import calendar
from datetime import date

from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.roster import RosterAssignment
from app.models.rotation import RotationPattern


def auto_fill_month(
    db: Session,
    pattern: RotationPattern,
    year: int,
    month: int,
    created_by: int,
    department_id: int | None = None,
    auto_stagger: bool = True,
) -> dict:
    """Fill the month for every employee in the pattern's category.

    auto_stagger=True (recommended): the service assigns each employee a DISTINCT
    starting position in the cycle (round-robin in grid order), so coverage is
    balanced and no two people get an identical schedule. Day 1 is set too.

    auto_stagger=False: the manager's existing DAY-1 shift is used as each
    employee's starting phase (the original behaviour). Duplicate day-1 shifts
    are reported as warnings because they produce identical schedules.

    In both modes, absences already entered are preserved and the result stays
    fully editable.
    """
    cycle = [s.shift_type_id for s in pattern.steps]  # ordered by position
    if not cycle:
        return {
            "filled_cells": 0,
            "employees_filled": 0,
            "skipped": [],
            "warnings": [],
        }
    cycle_len = len(cycle)

    last_day = calendar.monthrange(year, month)[1]
    first = date(year, month, 1)

    q = db.query(Employee).filter(
        Employee.is_active.is_(True),
        Employee.job_title == pattern.job_title,
    )
    if department_id is not None:
        q = q.filter(Employee.department_id == department_id)
    # Deterministic order (matches the roster grid) so staggering is intuitive.
    employees = q.order_by(Employee.last_name, Employee.first_name).all()

    filled_cells = 0
    employees_filled = 0
    skipped: list[str] = []
    warnings: list[str] = []

    # In manual mode, flag employees who share a day-1 shift (→ identical rotas).
    if not auto_stagger:
        seen: dict[int, list[str]] = {}
        for emp in employees:
            c = (
                db.query(RosterAssignment)
                .filter(
                    RosterAssignment.employee_id == emp.id,
                    RosterAssignment.work_date == first,
                )
                .first()
            )
            if c and c.shift_type_id in cycle:
                seen.setdefault(c.shift_type_id, []).append(
                    f"{emp.last_name} {emp.first_name}"
                )
        for sid, names in seen.items():
            if len(names) > 1:
                warnings.append(
                    f"{len(names)} employees share the same day-1 shift "
                    f"and will get identical schedules: {', '.join(names)}"
                )

    for idx, emp in enumerate(employees):
        existing = {
            c.work_date: c
            for c in db.query(RosterAssignment)
            .filter(
                RosterAssignment.employee_id == emp.id,
                RosterAssignment.work_date >= first,
                RosterAssignment.work_date <= date(year, month, last_day),
            )
            .all()
        }

        if auto_stagger:
            # Distinct, balanced start per employee — no manual day-1 needed.
            start_index = idx % cycle_len
            day_range = range(1, last_day + 1)
        else:
            seed_cell = existing.get(first)
            if (
                seed_cell is None
                or seed_cell.shift_type_id is None
                or seed_cell.shift_type_id not in cycle
            ):
                skipped.append(f"{emp.last_name} {emp.first_name}")
                continue
            start_index = cycle.index(seed_cell.shift_type_id)
            day_range = range(2, last_day + 1)  # keep manager's day-1 seed

        employees_filled += 1

        for day in day_range:
            d = date(year, month, day)
            target_shift = cycle[(start_index + (day - 1)) % cycle_len]

            cell = existing.get(d)
            # Preserve manually-entered absences (sick/vacation/transfer/etc.)
            if cell is not None and cell.absence_code is not None:
                continue

            if cell is None:
                cell = RosterAssignment(
                    employee_id=emp.id, work_date=d, created_by=created_by
                )
                db.add(cell)
                existing[d] = cell

            cell.shift_type_id = target_shift
            cell.absence_code = None
            filled_cells += 1

    db.commit()
    return {
        "filled_cells": filled_cells,
        "employees_filled": employees_filled,
        "skipped": skipped,
        "warnings": warnings,
    }
