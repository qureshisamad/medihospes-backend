"""Seed script (v2) — Manager/HR accounts, departments, sites, shift types,
job titles, and a few sample employees with contracts.

Reflects the confirmed v2.0 requirements: 4 departments, the 4 documented
shift types (+ a placeholder 5th, TBD), and role-matched employees.
"""

from datetime import time

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.department import Department
from app.models.employee import ContractType, Employee
from app.models.job_title import JobTitleRecord
from app.models.shift_type import ShiftType
from app.models.site import Site
from app.models.user import User, UserRole


def seed():
    db = SessionLocal()

    if db.query(User).first():
        print("Database already has users — skipping seed.")
        db.close()
        return

    # --- Login accounts: Manager + HR (the only two access levels) ---
    manager = User(
        email="manager@medihospes.it",
        hashed_password=hash_password("manager123"),
        first_name="Anna",
        last_name="Conti",
        role=UserRole.MANAGER,
    )
    hr = User(
        email="hr@medihospes.it",
        hashed_password=hash_password("hr123"),
        first_name="Marco",
        last_name="Greco",
        role=UserRole.HR,
    )

    # --- Departments (req v2.0 §1.1) ---
    administrative = Department(name="Administrative", code="ADM")
    oss = Department(name="OSS", code="OSS")
    auxiliaries = Department(name="Auxiliaries", code="AUX")
    coc = Department(name="COC", code="COC")

    # --- Sites ---
    site1 = Site(name="Messina I", code="ME-I", address="Via Roma 1, Messina")
    site2 = Site(name="Messina II", code="ME-II", address="Via Garibaldi 45, Messina")

    # --- Job titles / roles (drive substitution matching) ---
    job_titles = [
        JobTitleRecord(name="doctor", label="Doctor"),
        JobTitleRecord(name="administrative", label="Administrative"),
        JobTitleRecord(name="oss", label="OSS"),
        JobTitleRecord(name="auxiliary", label="Auxiliary"),
        JobTitleRecord(name="coc", label="COC"),
    ]

    # --- Shift types (req v2.0 §1.3) ---
    shift_types = [
        ShiftType(code="A", name="Morning", start_time=time(8, 0),
                  end_time=time(14, 0), duration_hours=6.0, crosses_midnight=False),
        ShiftType(code="B", name="Afternoon", start_time=time(9, 0),
                  end_time=time(16, 30), duration_hours=7.0, crosses_midnight=False),
        ShiftType(code="C", name="Night", start_time=time(21, 0),
                  end_time=time(0, 30), duration_hours=8.0, crosses_midnight=True),
        ShiftType(code="P/N", name="Afternoon/Night", start_time=time(15, 0),
                  end_time=time(0, 0), duration_hours=9.0, crosses_midnight=True),
        ShiftType(code="TBD", name="5th type (to confirm)", start_time=time(0, 0),
                  end_time=time(0, 0), duration_hours=0.0, crosses_midnight=False,
                  notes="Placeholder — definition pending meeting", is_active=False),
    ]

    db.add_all(
        [manager, hr, administrative, oss, auxiliaries, coc, site1, site2]
        + job_titles
        + shift_types
    )
    db.flush()  # assign IDs for FK references below

    # --- Sample employees with contracts (no login) ---
    employees = [
        Employee(
            first_name="Maria", last_name="Rossi", department_id=oss.id,
            site_id=site1.id, job_title="oss", contract_type=ContractType.FULL_TIME,
            monthly_hour_limit=130.35,
        ),
        Employee(
            first_name="Luca", last_name="Bianchi", department_id=administrative.id,
            site_id=site1.id, job_title="administrative",
            contract_type=ContractType.PART_TIME, monthly_hour_limit=104.28,
            flexible_shift=True,
        ),
        Employee(
            first_name="Giulia", last_name="Ferrari", department_id=oss.id,
            site_id=site2.id, job_title="oss", contract_type=ContractType.FULL_TIME,
            monthly_hour_limit=130.35, flexible_location=True,
        ),
        Employee(
            first_name="Paolo", last_name="Esposito", department_id=coc.id,
            site_id=site1.id, job_title="doctor", contract_type=ContractType.FULL_TIME,
            monthly_hour_limit=130.35,
        ),
    ]
    db.add_all(employees)
    db.commit()
    db.close()

    print("Seed complete!")
    print()
    print("  Manager login:  manager@medihospes.it / manager123")
    print("  HR login:       hr@medihospes.it / hr123")
    print()
    print("  Departments: Administrative, OSS, Auxiliaries, COC")
    print("  Sites: Messina I (ME-I), Messina II (ME-II)")
    print("  Shift types: A, B, C, P/N (+ TBD placeholder)")
    print("  4 sample employees with contracts seeded.")


if __name__ == "__main__":
    seed()
