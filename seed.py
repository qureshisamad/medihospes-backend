"""Seed script — creates initial admin, staff users, clinics, and job titles."""

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.clinic import Clinic
from app.models.job_title import JobTitleRecord
from app.models.user import ContractType, User, UserRole

# Import all models so SQLAlchemy can resolve relationships
from app.models.shift import Shift  # noqa: F401
from app.models.booking import ShiftBooking  # noqa: F401
from app.models.time_entry import TimeEntry  # noqa: F401


def seed():
    db = SessionLocal()

    # Check if already seeded
    if db.query(User).first():
        print("Database already has users — skipping seed.")
        db.close()
        return

    # Default job titles
    job_titles = [
        JobTitleRecord(name="administrative", label="Administrative"),
        JobTitleRecord(name="nurse", label="Nurse"),
        JobTitleRecord(name="doctor", label="Doctor"),
        JobTitleRecord(name="technician", label="Technician"),
        JobTitleRecord(name="support", label="Support"),
    ]
    db.add_all(job_titles)

    # Admin user
    admin = User(
        email="admin@medihospes.it",
        hashed_password=hash_password("admin123"),
        first_name="Admin",
        last_name="Manager",
        role=UserRole.ADMIN,
        job_title="administrative",
        contract_type=ContractType.FULL_TIME,
        weekly_hour_limit=36.0,
    )

    # Staff users
    nurse = User(
        email="nurse@medihospes.it",
        hashed_password=hash_password("staff123"),
        first_name="Maria",
        last_name="Rossi",
        role=UserRole.STAFF,
        job_title="nurse",
        contract_type=ContractType.FULL_TIME,
        weekly_hour_limit=36.0,
    )

    part_time = User(
        email="tech@medihospes.it",
        hashed_password=hash_password("staff123"),
        first_name="Luca",
        last_name="Bianchi",
        role=UserRole.STAFF,
        job_title="technician",
        contract_type=ContractType.PART_TIME,
        weekly_hour_limit=20.0,
    )

    # Clinics
    clinic1 = Clinic(name="Messina I", code="ME-I", address="Via Roma 1, Messina")
    clinic2 = Clinic(name="Messina II", code="ME-II", address="Via Garibaldi 45, Messina")
    clinic3 = Clinic(name="Catania Centro", code="CT-I", address="Corso Italia 12, Catania")

    db.add_all([admin, nurse, part_time, clinic1, clinic2, clinic3])
    db.commit()
    db.close()

    print("Seed complete!")
    print()
    print("  Admin login:  admin@medihospes.it / admin123")
    print("  Nurse login:  nurse@medihospes.it / staff123")
    print("  Tech login:   tech@medihospes.it  / staff123")
    print()
    print("  Clinics: Messina I (ME-I), Messina II (ME-II), Catania Centro (CT-I)")
    print("  Job Titles: Administrative, Nurse, Doctor, Technician, Support")


if __name__ == "__main__":
    seed()
