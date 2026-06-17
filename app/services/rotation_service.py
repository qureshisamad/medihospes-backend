"""Auto-fill engine (v2).

Two modes, both manager-triggered and fully editable afterwards (req v2.0 §4):

1. COVERAGE-DRIVEN (used when the pattern has coverage requirements) — fills
   each day to meet the required headcount per shift while respecting:
     * contractual monthly hours (part-time vs full-time — never exceeds the cap)
     * a minimum rest gap between consecutive shifts (so e.g. a 00:00-ending
       P/N is never followed by an 08:00 morning the next day)
     * one shift per person per day, role/category match
   It balances load (least-utilised staff first) and reports any shift it could
   NOT staff within the rules, rather than silently breaking a constraint.

2. STAGGERED CYCLE (fallback when no coverage is defined) — advances each
   employee through the pattern's cycle from a distinct, auto-staggered start.

Absences already entered (sick/vacation/etc.) are always preserved.
"""

import calendar
from datetime import date, datetime, time, timedelta

from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.roster import RosterAssignment
from app.models.rotation import RotationPattern
from app.models.shift_type import ShiftType

DEFAULT_MIN_REST_HOURS = 11.0


def _empty_result():
    return {
        "filled_cells": 0,
        "employees_filled": 0,
        "skipped": [],
        "warnings": [],
        "unmet": [],
    }


def _start_dt(d: date, st: ShiftType) -> datetime:
    return datetime.combine(d, st.start_time or time(0, 0))


def _end_dt(d: date, st: ShiftType) -> datetime:
    """End = start + paid duration. Uses duration (authoritative) so midnight
    crossing is handled without relying on the crosses_midnight flag."""
    return _start_dt(d, st) + timedelta(hours=st.duration_hours or 0.0)


def _category_employees(db, pattern, department_id):
    q = db.query(Employee).filter(
        Employee.is_active.is_(True),
        Employee.job_title == pattern.job_title,
    )
    if department_id is not None:
        q = q.filter(Employee.department_id == department_id)
    return q.order_by(Employee.last_name, Employee.first_name).all()


def auto_fill_month(
    db: Session,
    pattern: RotationPattern,
    year: int,
    month: int,
    created_by: int,
    department_id: int | None = None,
    auto_stagger: bool = True,
) -> dict:
    """Dispatch: coverage-driven if the pattern defines coverage, else cycle."""
    if pattern.coverage:
        return coverage_driven_fill(
            db, pattern, year, month, created_by, department_id
        )
    return staggered_cycle_fill(
        db, pattern, year, month, created_by, department_id, auto_stagger
    )


# --------------------------------------------------------------------------- #
# Coverage-driven, constraint-aware fill
# --------------------------------------------------------------------------- #
def coverage_driven_fill(
    db: Session,
    pattern: RotationPattern,
    year: int,
    month: int,
    created_by: int,
    department_id: int | None = None,
) -> dict:
    result = _empty_result()

    coverage = {c.shift_type_id: c.required_count for c in pattern.coverage}
    if not coverage:
        return result
    shift_types = {
        s.id: s
        for s in db.query(ShiftType).filter(ShiftType.id.in_(coverage)).all()
    }
    min_rest = pattern.min_rest_hours or DEFAULT_MIN_REST_HOURS
    last_day = calendar.monthrange(year, month)[1]
    first = date(year, month, 1)
    month_end = date(year, month, last_day)

    employees = _category_employees(db, pattern, department_id)
    if not employees:
        return result

    # Preserve absences; clear existing WORKED cells so the fill is deterministic.
    emp_ids = [e.id for e in employees]
    absences: dict[tuple[int, date], None] = {}
    for c in (
        db.query(RosterAssignment)
        .filter(
            RosterAssignment.employee_id.in_(emp_ids),
            RosterAssignment.work_date >= first,
            RosterAssignment.work_date <= month_end,
        )
        .all()
    ):
        if c.absence_code is not None:
            absences[(c.employee_id, c.work_date)] = None
    db.query(RosterAssignment).filter(
        RosterAssignment.employee_id.in_(emp_ids),
        RosterAssignment.work_date >= first,
        RosterAssignment.work_date <= month_end,
        RosterAssignment.absence_code.is_(None),
    ).delete(synchronize_session=False)

    # Per-employee running state
    projected = {e.id: 0.0 for e in employees}
    last_end = {e.id: None for e in employees}  # datetime of last worked shift end

    # Order shifts hardest-first (latest start) so tightly-constrained shifts
    # claim staff before the easy ones.
    shift_order = sorted(
        coverage.keys(),
        key=lambda sid: shift_types[sid].start_time or time(0, 0),
        reverse=True,
    )

    filled = 0
    filled_emps: set[int] = set()

    for day in range(1, last_day + 1):
        d = date(year, month, day)
        assigned_today: set[int] = set()

        for sid in shift_order:
            st = shift_types[sid]
            need = coverage[sid]
            placed = 0
            start = _start_dt(d, st)

            # Build eligible candidate pool
            pool = []
            for e in employees:
                if (e.id, d) in absences:
                    continue
                if e.id in assigned_today:
                    continue
                # rest rule vs their last worked shift
                le = last_end[e.id]
                if le is not None and (start - le) < timedelta(hours=min_rest):
                    continue
                # contractual monthly hours
                if projected[e.id] + (st.duration_hours or 0.0) > (
                    e.monthly_hour_limit or 0.0
                ) + 1e-6:
                    continue
                pool.append(e)

            # least-utilised first, then fewest hours, stable by name
            pool.sort(key=lambda e: (projected[e.id], e.last_name, e.first_name))

            for e in pool:
                if placed >= need:
                    break
                cell = RosterAssignment(
                    employee_id=e.id,
                    work_date=d,
                    shift_type_id=sid,
                    created_by=created_by,
                )
                db.add(cell)
                projected[e.id] += st.duration_hours or 0.0
                last_end[e.id] = _end_dt(d, st)
                assigned_today.add(e.id)
                filled_emps.add(e.id)
                filled += 1
                placed += 1

            if placed < need:
                result["unmet"].append(
                    f"{d.isoformat()} {st.code}: {need - placed} of {need} "
                    f"unfilled (no staff within rest/hours limits)"
                )

        # Anyone not working today and not absent: rest day clears their rest gap
        for e in employees:
            if e.id not in assigned_today and (e.id, d) not in absences:
                last_end[e.id] = None

    db.commit()

    # Flag under-utilised staff (well below contract) for the manager
    for e in employees:
        limit = e.monthly_hour_limit or 0.0
        if limit and projected[e.id] < limit * 0.5:
            result["warnings"].append(
                f"{e.last_name} {e.first_name}: only {projected[e.id]:.1f}h "
                f"scheduled of {limit:.0f}h contract"
            )

    result["filled_cells"] = filled
    result["employees_filled"] = len(filled_emps)
    return result


# --------------------------------------------------------------------------- #
# Staggered cycle fill (fallback)
# --------------------------------------------------------------------------- #
def staggered_cycle_fill(
    db: Session,
    pattern: RotationPattern,
    year: int,
    month: int,
    created_by: int,
    department_id: int | None = None,
    auto_stagger: bool = True,
) -> dict:
    result = _empty_result()
    cycle = [s.shift_type_id for s in pattern.steps]
    if not cycle:
        return result
    cycle_len = len(cycle)
    last_day = calendar.monthrange(year, month)[1]
    first = date(year, month, 1)

    employees = _category_employees(db, pattern, department_id)

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
        for names in seen.values():
            if len(names) > 1:
                result["warnings"].append(
                    f"{len(names)} employees share the same day-1 shift and "
                    f"will get identical schedules: {', '.join(names)}"
                )

    filled = 0
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
            start_index = idx % cycle_len
            day_range = range(1, last_day + 1)
        else:
            seed = existing.get(first)
            if seed is None or seed.shift_type_id not in cycle:
                result["skipped"].append(f"{emp.last_name} {emp.first_name}")
                continue
            start_index = cycle.index(seed.shift_type_id)
            day_range = range(2, last_day + 1)
        result["employees_filled"] += 1

        for day in day_range:
            d = date(year, month, day)
            target = cycle[(start_index + (day - 1)) % cycle_len]
            cell = existing.get(d)
            if cell is not None and cell.absence_code is not None:
                continue
            if cell is None:
                cell = RosterAssignment(
                    employee_id=emp.id, work_date=d, created_by=created_by
                )
                db.add(cell)
                existing[d] = cell
            cell.shift_type_id = target
            cell.absence_code = None
            filled += 1

    db.commit()
    result["filled_cells"] = filled
    return result
