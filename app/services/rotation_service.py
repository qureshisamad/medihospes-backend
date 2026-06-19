"""Auto-fill engine (v2).

Two modes, both manager-triggered and fully editable afterwards (req v2.0 §4):

1. COVERAGE-DRIVEN (when the pattern has coverage requirements) — fills each day
   to the required headcount per shift while respecting contractual monthly
   hours (part vs full-time), a minimum rest gap between consecutive shifts, and
   one shift per person per day. Balances load and reports shifts it could NOT
   staff within the rules.

2. STAGGERED CYCLE (fallback when no coverage is defined) — advances each
   employee through the pattern's cycle from a distinct, auto-staggered start.

Cells the manager has set BY HAND (is_manual) and any ABSENCE are treated as
fixed: they are preserved and counted as constraints (coverage already met,
hours used, rest imposed). Pass reset_manual=True to discard manual edits and
fill from scratch.
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
    reset_manual: bool = False,
) -> dict:
    if pattern.coverage:
        return coverage_driven_fill(
            db, pattern, year, month, created_by, department_id, reset_manual
        )
    return staggered_cycle_fill(
        db, pattern, year, month, created_by, department_id, auto_stagger,
        reset_manual,
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
    reset_manual: bool = False,
) -> dict:
    result = _empty_result()
    coverage = {c.shift_type_id: c.required_count for c in pattern.coverage}
    if not coverage:
        return result
    shift_types = {
        s.id: s for s in db.query(ShiftType).filter(ShiftType.id.in_(coverage)).all()
    }
    all_shifts = {s.id: s for s in db.query(ShiftType).all()}
    min_rest = pattern.min_rest_hours or DEFAULT_MIN_REST_HOURS
    last_day = calendar.monthrange(year, month)[1]
    first = date(year, month, 1)
    month_end = date(year, month, last_day)

    employees = _category_employees(db, pattern, department_id)
    if not employees:
        return result
    emp_ids = [e.id for e in employees]

    # Load existing cells; classify fixed (absence, or manual unless reset).
    existing = (
        db.query(RosterAssignment)
        .filter(
            RosterAssignment.employee_id.in_(emp_ids),
            RosterAssignment.work_date >= first,
            RosterAssignment.work_date <= month_end,
        )
        .all()
    )
    absent: dict[tuple[int, date], None] = {}
    fixed_work: dict[tuple[int, date], int] = {}  # manual worked cells kept
    for c in existing:
        if c.absence_code is not None:
            absent[(c.employee_id, c.work_date)] = None
        elif c.is_manual and not reset_manual:
            fixed_work[(c.employee_id, c.work_date)] = c.shift_type_id

    # Delete cells we are about to regenerate (auto always; manual if reset).
    del_q = db.query(RosterAssignment).filter(
        RosterAssignment.employee_id.in_(emp_ids),
        RosterAssignment.work_date >= first,
        RosterAssignment.work_date <= month_end,
        RosterAssignment.absence_code.is_(None),
    )
    if not reset_manual:
        del_q = del_q.filter(RosterAssignment.is_manual.is_(False))
    del_q.delete(synchronize_session=False)

    # Reserve hours for kept manual cells up front so auto stays within contract.
    projected = {e.id: 0.0 for e in employees}
    for (eid, d), sid in fixed_work.items():
        st = all_shifts.get(sid)
        if st:
            projected[eid] += st.duration_hours or 0.0

    last_end: dict[int, datetime | None] = {e.id: None for e in employees}

    shift_order = sorted(
        coverage.keys(),
        key=lambda sid: shift_types[sid].start_time or time(0, 0),
        reverse=True,
    )

    filled = 0
    filled_emps: set[int] = set()

    for day in range(1, last_day + 1):
        d = date(year, month, day)
        today_shift: dict[int, int] = {}  # emp -> shift worked today
        assigned_today: set[int] = set()

        # Apply kept manual cells for the day first.
        for e in employees:
            sid = fixed_work.get((e.id, d))
            if sid is not None:
                today_shift[e.id] = sid
                assigned_today.add(e.id)

        for sid in shift_order:
            st = shift_types[sid]
            already = sum(1 for e in employees if today_shift.get(e.id) == sid)
            need = coverage[sid] - already
            if need <= 0:
                continue
            start = _start_dt(d, st)
            end = _end_dt(d, st)

            pool = []
            for e in employees:
                if (e.id, d) in absent or e.id in assigned_today:
                    continue
                le = last_end[e.id]
                if le is not None and (start - le) < timedelta(hours=min_rest):
                    continue
                # forward: respect a fixed shift the employee already has tomorrow
                nxt = fixed_work.get((e.id, d + timedelta(days=1)))
                if nxt is not None:
                    nstart = _start_dt(d + timedelta(days=1), all_shifts[nxt])
                    if (nstart - end) < timedelta(hours=min_rest):
                        continue
                if projected[e.id] + (st.duration_hours or 0.0) > (
                    e.monthly_hour_limit or 0.0
                ) + 1e-6:
                    continue
                pool.append(e)

            pool.sort(key=lambda e: (projected[e.id], e.last_name, e.first_name))

            placed = 0
            for e in pool:
                if placed >= need:
                    break
                db.add(
                    RosterAssignment(
                        employee_id=e.id,
                        work_date=d,
                        shift_type_id=sid,
                        created_by=created_by,
                        is_manual=False,
                    )
                )
                projected[e.id] += st.duration_hours or 0.0
                today_shift[e.id] = sid
                assigned_today.add(e.id)
                filled_emps.add(e.id)
                filled += 1
                placed += 1

            if placed < need:
                result["unmet"].append(
                    f"{d.isoformat()} {st.code}: {need - placed} of "
                    f"{coverage[sid]} unfilled (no staff within rest/hours limits)"
                )

        # End of day: roll rest state forward.
        for e in employees:
            sid = today_shift.get(e.id)
            if sid is not None:
                last_end[e.id] = _end_dt(d, all_shifts[sid])
            else:
                last_end[e.id] = None  # off / absent clears the rest gap

    db.commit()

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
    reset_manual: bool = False,
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
            if cell is not None and cell.is_manual and not reset_manual:
                continue  # preserve hand-set cells
            if cell is None:
                cell = RosterAssignment(
                    employee_id=emp.id, work_date=d, created_by=created_by
                )
                db.add(cell)
                existing[d] = cell
            cell.shift_type_id = target
            cell.absence_code = None
            cell.is_manual = False
            filled += 1

    db.commit()
    result["filled_cells"] = filled
    return result


# --------------------------------------------------------------------------- #
# Per-employee cascade — re-derive ONE person's later days from a cell
# --------------------------------------------------------------------------- #
def cascade_employee(
    db: Session,
    pattern: RotationPattern,
    employee_id: int,
    from_date: date,
    created_by: int,
) -> dict:
    """Re-derive an employee's days AFTER from_date by advancing the cycle from
    the shift now on from_date. Other employees are untouched; absences kept."""
    cycle = [s.shift_type_id for s in pattern.steps]
    if not cycle:
        return {"updated": 0}
    cycle_len = len(cycle)
    last_day = calendar.monthrange(from_date.year, from_date.month)[1]

    seed = (
        db.query(RosterAssignment)
        .filter(
            RosterAssignment.employee_id == employee_id,
            RosterAssignment.work_date == from_date,
        )
        .first()
    )
    if not seed or seed.shift_type_id not in cycle:
        return {"updated": 0}
    phase = cycle.index(seed.shift_type_id)

    existing = {
        c.work_date: c
        for c in db.query(RosterAssignment)
        .filter(
            RosterAssignment.employee_id == employee_id,
            RosterAssignment.work_date > from_date,
            RosterAssignment.work_date <= date(
                from_date.year, from_date.month, last_day
            ),
        )
        .all()
    }

    updated = 0
    for day in range(from_date.day + 1, last_day + 1):
        d = date(from_date.year, from_date.month, day)
        target = cycle[(phase + (day - from_date.day)) % cycle_len]
        cell = existing.get(d)
        if cell is not None and cell.absence_code is not None:
            continue  # never overwrite an absence
        if cell is None:
            cell = RosterAssignment(
                employee_id=employee_id, work_date=d, created_by=created_by
            )
            db.add(cell)
        cell.shift_type_id = target
        cell.absence_code = None
        cell.is_manual = False
        updated += 1

    db.commit()
    return {"updated": updated}
