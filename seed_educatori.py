"""Seed the Educatori category, sample staff and their rotation library.

Idempotent: safe to run repeatedly. Demonstrates the rotation auto-fill feature
on one category (Educatori) per the June 2026 client request.
"""

from app.core.database import SessionLocal
from app.models.department import Department
from app.models.employee import ContractType, Employee
from app.models.job_title import JobTitleRecord
from app.models.rotation import (
    CoverageRequirement,
    RotationPattern,
    RotationStep,
)
from app.models.shift_type import ShiftType

EDU_ROLE = "educatore"
# The Educatori cycle, in order (note: ① M, ② P/N, ③ S, ④ R)
CYCLE_CODES = ["M/Ed", "P/N/Ed", "S", "R"]
# Daily coverage requirement: how many people on each working shift per day.
COVERAGE = {"M/Ed": 1, "P/N/Ed": 1, "S": 1}
MIN_REST_HOURS = 11.0

SAMPLE = [
    ("Cina", "Antonella"),
    ("De Luca", "Marco"),
    ("Greco", "Sara"),
    ("Conti", "Davide"),
]


def get_or_create(db, model, defaults=None, **filters):
    obj = db.query(model).filter_by(**filters).first()
    if obj:
        return obj, False
    obj = model(**filters, **(defaults or {}))
    db.add(obj)
    db.flush()
    return obj, True


def main():
    db = SessionLocal()
    try:
        # 1. Job title
        get_or_create(
            db, JobTitleRecord, {"label": "Educatore"}, name=EDU_ROLE
        )

        # 2. Department — reuse the existing "Educatori" dept if present
        dept = db.query(Department).filter_by(name="Educatori").first()
        if not dept:
            dept = Department(name="Educatori", code="EDU")
            db.add(dept)
            db.flush()

        # 3. Sample employees
        for last, first in SAMPLE:
            emp = (
                db.query(Employee)
                .filter_by(last_name=last, first_name=first, job_title=EDU_ROLE)
                .first()
            )
            if not emp:
                db.add(
                    Employee(
                        first_name=first,
                        last_name=last,
                        job_title=EDU_ROLE,
                        department_id=dept.id,
                        contract_type=ContractType.FULL_TIME,
                        monthly_hour_limit=130.35,
                        is_active=True,
                    )
                )
        db.flush()

        # 4. Rotation pattern
        codes = {s.code: s.id for s in db.query(ShiftType).all()}
        missing = [c for c in CYCLE_CODES if c not in codes]
        if missing:
            raise SystemExit(
                f"Missing shift types {missing}. Create them first "
                f"(have: {sorted(codes)})."
            )
        cycle_ids = [codes[c] for c in CYCLE_CODES]

        pattern = (
            db.query(RotationPattern).filter_by(job_title=EDU_ROLE).first()
        )
        if not pattern:
            pattern = RotationPattern(
                name="Educatori standard rotation", job_title=EDU_ROLE
            )
            db.add(pattern)
            db.flush()
        pattern.min_rest_hours = MIN_REST_HOURS
        # Clear existing children first so the unique (pattern, position) /
        # (pattern, shift) constraints don't clash on re-seed.
        pattern.steps.clear()
        pattern.coverage.clear()
        db.flush()
        pattern.steps = [
            RotationStep(position=i, shift_type_id=sid)
            for i, sid in enumerate(cycle_ids)
        ]
        pattern.coverage = [
            CoverageRequirement(shift_type_id=codes[c], required_count=n)
            for c, n in COVERAGE.items()
        ]

        db.commit()

        print("Educatori seed complete!")
        print(f"  Department: Educatori (id={dept.id})")
        print(f"  Job title:  {EDU_ROLE}")
        print(f"  Employees:  {len(SAMPLE)} educatori")
        print(f"  Rotation:   {' -> '.join(CYCLE_CODES)}  (pattern id={pattern.id})")
        print(f"  Coverage:   {COVERAGE}  · min rest {MIN_REST_HOURS}h")
    finally:
        db.close()


if __name__ == "__main__":
    main()
