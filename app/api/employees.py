"""Employee endpoints (v2) — manage scheduled people + their contracts.

Employees never log in; these endpoints let Manager/HR maintain the registry
of people who appear on the roster (req v2.0 §1.2, §1.4).
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import require_edit
from app.core.database import get_db
from app.models.coverage import EmployeeCoverage
from app.models.employee import Employee
from app.models.roster import RosterAssignment
from app.models.user import User
from app.schemas.employee import EmployeeCreate, EmployeeRead, EmployeeUpdate
from app.services.hours_service import month_bounds

router = APIRouter(prefix="/employees", tags=["Employees"])


def _serialize(emp: Employee) -> EmployeeRead:
    return EmployeeRead(
        id=emp.id,
        first_name=emp.first_name,
        last_name=emp.last_name,
        codice_fiscale=emp.codice_fiscale,
        department_id=emp.department_id,
        site_id=emp.site_id,
        job_title=emp.job_title,
        location=emp.location,
        contract_type=emp.contract_type,
        monthly_hour_limit=emp.monthly_hour_limit,
        flexible_shift=emp.flexible_shift,
        flexible_location=emp.flexible_location,
        is_active=emp.is_active,
        created_at=emp.created_at,
        coverable_roles=[c.coverable_role for c in emp.coverable_roles],
    )


@router.get("", response_model=list[EmployeeRead])
def list_employees(
    department_id: int | None = Query(None),
    job_title: str | None = Query(None),
    site_id: int | None = Query(None),
    is_active: bool | None = Query(None),
    year: int | None = Query(None),
    month: int | None = Query(None, ge=1, le=12),
    db: Session = Depends(get_db),
    _u: User = Depends(require_edit),
):
    """List employees. When ``site_id`` is combined with ``year``+``month``, the
    result also includes operators on loan INTO that house that month (a cell
    with a per-cell ``site_id`` override to this house) so they appear as rows
    in the receiving house's roster grid (objective 3, part 2)."""
    q = db.query(Employee)
    if department_id is not None:
        q = q.filter(Employee.department_id == department_id)
    if job_title is not None:
        q = q.filter(Employee.job_title == job_title)
    if is_active is not None:
        q = q.filter(Employee.is_active == is_active)
    if site_id is not None:
        if year is not None and month is not None:
            start, end = month_bounds(year, month)
            onloan_ids = db.query(RosterAssignment.employee_id).filter(
                RosterAssignment.site_id == site_id,
                RosterAssignment.work_date >= start,
                RosterAssignment.work_date <= end,
            )
            q = q.filter(
                or_(Employee.site_id == site_id, Employee.id.in_(onloan_ids))
            )
        else:
            q = q.filter(Employee.site_id == site_id)
    employees = q.order_by(Employee.last_name, Employee.first_name).all()
    return [_serialize(e) for e in employees]


@router.post("", response_model=EmployeeRead, status_code=201)
def create_employee(
    body: EmployeeCreate,
    db: Session = Depends(get_db),
    _u: User = Depends(require_edit),
):
    data = body.model_dump()
    coverable = data.pop("coverable_roles", [])
    emp = Employee(**data)
    emp.coverable_roles = [
        EmployeeCoverage(coverable_role=r) for r in coverable
    ]
    db.add(emp)
    db.commit()
    db.refresh(emp)
    return _serialize(emp)


@router.get("/{employee_id}", response_model=EmployeeRead)
def get_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    _u: User = Depends(require_edit),
):
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    return _serialize(emp)


@router.patch("/{employee_id}", response_model=EmployeeRead)
def update_employee(
    employee_id: int,
    body: EmployeeUpdate,
    db: Session = Depends(get_db),
    _u: User = Depends(require_edit),
):
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    data = body.model_dump(exclude_unset=True)
    coverable = data.pop("coverable_roles", None)
    for field, value in data.items():
        setattr(emp, field, value)

    if coverable is not None:
        emp.coverable_roles = [
            EmployeeCoverage(coverable_role=r) for r in coverable
        ]

    db.commit()
    db.refresh(emp)
    return _serialize(emp)
