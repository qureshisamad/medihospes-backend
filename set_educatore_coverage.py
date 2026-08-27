"""Set each house's Educatori rotation coverage to match its real headcount.

Default split: 1 person each on the working shifts (M/Ed, P/N/Ed, S/Ed) and the
remainder on Rest (R), so coverage total == number of educatori in the house.
The working-shift split is a starting point the manager can adjust per house.
"""

from app.core.database import SessionLocal
from app.models.employee import Employee
from app.models.rotation import (
    CoverageRequirement,
    RotationPattern,
    RotationStep,
)
from app.models.shift_type import ShiftType
from app.models.site import Site

HOUSES = ["Casa Touré", "Casa Airone", "Casa Aylan", "Casa Michelle"]
CYCLE_CODES = ["M/Ed", "P/N/Ed", "S/Ed", "R"]  # regulated order
WORKING = ["M/Ed", "P/N/Ed", "S/Ed"]  # 1 each; R gets the remainder
ROLE = "educatore"
MIN_REST = 11.0


def main():
    db = SessionLocal()
    try:
        codes = {s.code: s.id for s in db.query(ShiftType).all()}
        missing = [c for c in CYCLE_CODES if c not in codes]
        if missing:
            raise SystemExit(f"Missing shift types {missing}")
        cycle_ids = [codes[c] for c in CYCLE_CODES]

        for house in HOUSES:
            site = db.query(Site).filter_by(name=house).first()
            if not site:
                print(f"  ! site not found: {house}")
                continue
            headcount = (
                db.query(Employee)
                .filter_by(job_title=ROLE, site_id=site.id, is_active=True)
                .count()
            )
            rest = max(0, headcount - len(WORKING))
            coverage = {c: 1 for c in WORKING}
            coverage["R"] = rest

            pattern = (
                db.query(RotationPattern)
                .filter_by(job_title=ROLE, site_id=site.id)
                .first()
            )
            if not pattern:
                pattern = RotationPattern(
                    name=f"Educatori — {house}", job_title=ROLE, site_id=site.id
                )
                db.add(pattern)
                db.flush()
            pattern.min_rest_hours = MIN_REST
            pattern.steps.clear()
            pattern.coverage.clear()
            db.flush()
            pattern.steps = [
                RotationStep(position=i, shift_type_id=sid)
                for i, sid in enumerate(cycle_ids)
            ]
            pattern.coverage = [
                CoverageRequirement(shift_type_id=codes[c], required_count=n)
                for c, n in coverage.items()
            ]
            db.flush()
            total = sum(coverage.values())
            print(
                f"  {house}: headcount={headcount} -> coverage "
                f"M/Ed=1 P/N/Ed=1 S/Ed=1 R={rest} (total {total}) "
                f"{'OK' if total == headcount else 'MISMATCH'}"
            )

        db.commit()
        print("Done.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
