"""Seed script — creates initial admin, staff users, and clinics."""

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.clinic import Clinic
from app.models.user import ContractType, JobTitle, User, UserRole

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

    # Admin user
    admin = User(
        email="admin@medihospes.it",
        hashed_password=hash_password("admin123"),
        first_name="Admin",
        last_name="Manager",
        role=UserRole.ADMIN,
        job_title=JobTitle.ADMINISTRATIVE,
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
        job_title=JobTitle.NURSE,
        contract_type=ContractType.FULL_TIME,
        weekly_hour_limit=36.0,
    )

    part_time = User(
        email="tech@medihospes.it",
        hashed_password=hash_password("staff123"),
        first_name="Luca",
        last_name="Bianchi",
        role=UserRole.STAFF,
        job_title=JobTitle.TECHNICIAN,
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


if __name__ == "__main__":
    seed()
