"""One-time script to seed default job titles into an existing database."""

from app.core.database import SessionLocal
from app.models.job_title import JobTitleRecord

# Import all models so SQLAlchemy can resolve relationships
from app.models.user import User  # noqa: F401
from app.models.clinic import Clinic  # noqa: F401
from app.models.shift import Shift  # noqa: F401
from app.models.booking import ShiftBooking  # noqa: F401
from app.models.time_entry import TimeEntry  # noqa: F401
from app.models.notification import Notification  # noqa: F401


def seed_job_titles():
    db = SessionLocal()

    existing = db.query(JobTitleRecord).count()
    if existing > 0:
        print(f"Job titles table already has {existing} records — skipping.")
        db.close()
        return

    defaults = [
        JobTitleRecord(name="administrative", label="Administrative"),
        JobTitleRecord(name="nurse", label="Nurse"),
        JobTitleRecord(name="doctor", label="Doctor"),
        JobTitleRecord(name="technician", label="Technician"),
        JobTitleRecord(name="support", label="Support"),
    ]
    labels = [(jt.name, jt.label) for jt in defaults]
    db.add_all(defaults)
    db.commit()
    db.close()

    print("Seeded 5 default job titles:")
    for name, label in labels:
        print(f"  - {label} ({name})")


if __name__ == "__main__":
    seed_job_titles()
