# Models package — import all so SQLAlchemy + Alembic register them.
from app.models.user import User, UserRole  # noqa: F401
from app.models.department import Department  # noqa: F401
from app.models.site import Site  # noqa: F401
from app.models.shift_type import ShiftType  # noqa: F401
from app.models.employee import Employee, ContractType  # noqa: F401
from app.models.coverage import EmployeeCoverage  # noqa: F401
from app.models.roster import (  # noqa: F401
    AbsenceCode,
    RosterAssignment,
    RosterChangeLog,
)
from app.models.rotation import (  # noqa: F401
    CoverageRequirement,
    RotationPattern,
    RotationStep,
)
from app.models.job_title import JobTitleRecord  # noqa: F401
