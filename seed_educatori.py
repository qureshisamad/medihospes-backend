"""Seed the Educatori category across HOUSES (sites), with per-house staff and
a per-house rotation. Demonstrates that a category can hold more than one
house's worth of staff — each house schedules independently.

Idempotent: safe to run repeatedly.
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
from app.models.site import Site

EDU_ROLE = "educatore"
CYCLE_CODES = ["M/Ed", "P/N/Ed", "S/Ed", "R"]  # regulated order
COVERAGE = {"M/Ed": 1, "P/N/Ed": 1, "S/Ed": 1, "R": 1}  # per house, sum = 4 staff
MIN_REST_HOURS = 11.0

# Each house gets its own staff (4 = the coverage total) and its own rotation.
HOUSES = [
    ("Casa Touré", "CASA-TO", [
        ("Cina", "Antonella"), ("De Luca", "Marco"),
        ("Greco", "Sara"), ("Conti", "Davide"),
    ]),
    ("Casa Airone", "CASA-AI", [
        ("Russo", "Elena"), ("Marino", "Paolo"),
        ("Costa", "Anna"), ("Gallo", "Luca"),
    ]),
]


def main():
    db = SessionLocal()
    try:
        # Job title + department
        if not db.query(JobTitleRecord).filter_by(name=EDU_ROLE).first():
            db.add(JobTitleRecord(name=EDU_ROLE, label="Educatore"))
        dept = db.query(Department).filter_by(name="Educatori").first()
        if not dept:
            dept = Department(name="Educatori", code="EDU")
            db.add(dept)
        db.flush()

        codes = {s.code: s.id for s in db.query(ShiftType).all()}
        missing = [c for c in CYCLE_CODES if c not in codes]
        if missing:
            raise SystemExit(f"Missing shift types {missing} (have {sorted(codes)}).")
        cycle_ids = [codes[c] for c in CYCLE_CODES]

        # Replace any existing educatore rotations with fresh per-house ones.
        for p in db.query(RotationPattern).filter_by(job_title=EDU_ROLE).all():
            db.delete(p)
        db.flush()

        for house_name, house_code, staff in HOUSES:
            site = db.query(Site).filter_by(name=house_name).first()
            if not site:
                site = Site(name=house_name, code=house_code)
                db.add(site)
                db.flush()

            for last, first in staff:
                emp = (
                    db.query(Employee)
                    .filter_by(last_name=last, first_name=first, job_title=EDU_ROLE)
                    .first()
                )
                if not emp:
                    emp = Employee(
                        first_name=first, last_name=last, job_title=EDU_ROLE,
                        department_id=dept.id,
                        contract_type=ContractType.FULL_TIME,
                        monthly_hour_limit=130.35, is_active=True,
                    )
                    db.add(emp)
                emp.site_id = site.id  # assign to this house

            pattern = RotationPattern(
                name=f"Educatori — {house_name}",
                job_title=EDU_ROLE,
                site_id=site.id,
                min_rest_hours=MIN_REST_HOURS,
            )
            pattern.steps = [
                RotationStep(position=i, shift_type_id=sid)
                for i, sid in enumerate(cycle_ids)
            ]
            pattern.coverage = [
                CoverageRequirement(shift_type_id=codes[c], required_count=n)
                for c, n in COVERAGE.items()
            ]
            db.add(pattern)

        db.commit()

        print("Educatori (per-house) seed complete!")
        for house_name, _, staff in HOUSES:
            print(f"  {house_name}: {len(staff)} educatori · rotation "
                  f"{' -> '.join(CYCLE_CODES)} · coverage {COVERAGE}")
        print(f"  Total educatori across houses: "
              f"{sum(len(s) for _, _, s in HOUSES)}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
