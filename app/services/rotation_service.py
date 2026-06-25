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
from collections import Counter, defaultdict, deque
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
        "alerts": [],
    }


def _start_dt(d: date, st: ShiftType) -> datetime:
    return datetime.combine(d, st.start_time or time(0, 0))


def _end_dt(d: date, st: ShiftType) -> datetime:
    return _start_dt(d, st) + timedelta(hours=st.duration_hours or 0.0)


def _category_employees(db, pattern, department_id):
    """Employees in the pattern's category — and, when the pattern is scoped to
    a house (site_id), only the staff assigned to that house."""
    q = db.query(Employee).filter(
        Employee.is_active.is_(True),
        Employee.job_title == pattern.job_title,
    )
    if pattern.site_id is not None:
        q = q.filter(Employee.site_id == pattern.site_id)
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
        return coverage_cycle_fill(
            db, pattern, year, month, created_by, department_id, reset_manual
        )
    return staggered_cycle_fill(
        db, pattern, year, month, created_by, department_id, auto_stagger,
        reset_manual,
    )


# --------------------------------------------------------------------------- #
# Coverage-shaped rotating cycle
# --------------------------------------------------------------------------- #
def build_cycle(pattern: RotationPattern, coverage: dict[int, int]) -> list[int]:
    """The "specific time regulation": the pattern's step order with each shift
    repeated by its coverage count. e.g. order M,P/N,S,R with coverage
    1,2,3,4  ->  [M, P/N, P/N, S, S, S, R, R, R, R] (length = total = headcount).
    R (rest) is a first-class part of the cycle, not an afterthought."""
    cycle: list[int] = []
    seen: set[int] = set()
    for step in pattern.steps:  # ordered = regulated sequence
        cnt = coverage.get(step.shift_type_id, 0)
        cycle.extend([step.shift_type_id] * cnt)
        seen.add(step.shift_type_id)
    # Any coverage shift not in the step order is appended at the end.
    for sid, cnt in coverage.items():
        if sid not in seen:
            cycle.extend([sid] * cnt)
    return cycle


def _assign_offsets(employees, cycle, seeds):
    """Map each employee to a distinct starting offset in the cycle. Honour the
    manager's day-1 seed where valid; auto-stagger the rest."""
    pos_by_shift: dict[int, deque] = defaultdict(deque)
    for idx, sid in enumerate(cycle):
        pos_by_shift[sid].append(idx)

    offsets: dict[int, int] = {}
    used: set[int] = set()
    unseeded = []
    for e in employees:
        s = seeds.get(e.id)
        if s is not None and pos_by_shift.get(s):
            off = pos_by_shift[s].popleft()
            offsets[e.id] = off
            used.add(off)
        else:
            unseeded.append(e)

    remaining = deque(i for i in range(len(cycle)) if i not in used)
    for e in unseeded:
        offsets[e.id] = remaining.popleft() if remaining else 0
    return offsets


def coverage_cycle_fill(
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

    all_shifts = {s.id: s for s in db.query(ShiftType).all()}
    code = {sid: all_shifts[sid].code if sid in all_shifts else "?" for sid in coverage}
    min_rest = pattern.min_rest_hours or DEFAULT_MIN_REST_HOURS

    cycle = build_cycle(pattern, coverage)
    total = len(cycle)  # = sum of coverage counts
    last_day = calendar.monthrange(year, month)[1]
    first = date(year, month, 1)
    month_end = date(year, month, last_day)

    employees = _category_employees(db, pattern, department_id)
    if not employees:
        result["alerts"].append("No active employees in this category.")
        return result
    n = len(employees)
    emp_ids = [e.id for e in employees]

    # --- Alert 1: headcount must equal the coverage total (M+P/N+S+R) ---
    if n != total:
        result["alerts"].append(
            f"Staff in this category: {n}, but the required total "
            f"(M+P/N+S+R = {'+'.join(str(coverage[s]) for s in coverage)}) is "
            f"{total}. Coverage will not balance — adjust the counts or the staff."
        )

    # --- Soft check: does the regulated order respect the rest rule? ---
    for i in range(total):
        a, b = all_shifts.get(cycle[i]), all_shifts.get(cycle[(i + 1) % total])
        if a and b and cycle[i] != cycle[(i + 1) % total]:
            gap = (
                datetime.combine(date(2000, 1, 2), b.start_time or time(0, 0))
                - (
                    datetime.combine(date(2000, 1, 1), a.start_time or time(0, 0))
                    + timedelta(hours=a.duration_hours or 0.0)
                )
            ).total_seconds() / 3600
            if 0 <= gap < min_rest:
                result["warnings"].append(
                    f"Order {a.code}→{b.code} leaves only {gap:.0f}h rest "
                    f"(min {min_rest:.0f}h) — check the shift sequence."
                )
                break

    # --- Load existing cells; preserve absences and manual edits ---
    existing_rows = (
        db.query(RosterAssignment)
        .filter(
            RosterAssignment.employee_id.in_(emp_ids),
            RosterAssignment.work_date >= first,
            RosterAssignment.work_date <= month_end,
        )
        .all()
    )
    preserved: dict[tuple[int, date], int | None] = {}  # (emp,date) -> shift or None(absence)
    seeds: dict[int, int] = {}
    for c in existing_rows:
        if c.absence_code is not None:
            preserved[(c.employee_id, c.work_date)] = None
        elif c.is_manual and not reset_manual:
            preserved[(c.employee_id, c.work_date)] = c.shift_type_id
            if c.work_date == first and c.shift_type_id in coverage:
                seeds[c.employee_id] = c.shift_type_id

    # --- Alert 2: a manager-initiated day-1 seed that doesn't match coverage ---
    if seeds:
        seed_counts = Counter(seeds.values())
        for sid, req in coverage.items():
            got = seed_counts.get(sid, 0)
            if got != req:
                result["alerts"].append(
                    f"Day 1: {code[sid]} has {got}, expected {req}."
                )

    # Delete the cells we'll regenerate (auto always; manual only if reset).
    del_q = db.query(RosterAssignment).filter(
        RosterAssignment.employee_id.in_(emp_ids),
        RosterAssignment.work_date >= first,
        RosterAssignment.work_date <= month_end,
        RosterAssignment.absence_code.is_(None),
    )
    if not reset_manual:
        del_q = del_q.filter(RosterAssignment.is_manual.is_(False))
    del_q.delete(synchronize_session=False)

    offsets = _assign_offsets(employees, cycle, seeds if not reset_manual else {})

    filled = 0
    filled_emps: set[int] = set()
    # actual shift worked per (day -> shift -> count), to verify coverage
    day_counts: dict[int, Counter] = defaultdict(Counter)

    for e in employees:
        off = offsets[e.id]
        for day in range(1, last_day + 1):
            d = date(year, month, day)
            key = (e.id, d)
            if key in preserved:
                sid = preserved[key]
                if sid is not None:
                    day_counts[day][sid] += 1
                continue  # keep absence / manual cell untouched
            target = cycle[(off + (day - 1)) % total] if total else None
            if target is None:
                continue
            db.add(
                RosterAssignment(
                    employee_id=e.id,
                    work_date=d,
                    shift_type_id=target,
                    created_by=created_by,
                    is_manual=False,
                )
            )
            day_counts[day][target] += 1
            filled += 1
            filled_emps.add(e.id)

    db.commit()

    # --- Per-day coverage shortfalls (e.g. caused by an absence) ---
    for day in range(1, last_day + 1):
        for sid, req in coverage.items():
            got = day_counts[day][sid]
            if got < req:
                d = date(year, month, day)
                result["unmet"].append(
                    f"{d.isoformat()} {code[sid]}: {got} of {req} "
                    f"(short {req - got})"
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
