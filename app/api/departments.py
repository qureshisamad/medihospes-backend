"""Department endpoints (v2)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import require_edit
from app.core.database import get_db
from app.models.department import Department
from app.models.user import User
from app.schemas.department import (
    DepartmentCreate,
    DepartmentRead,
    DepartmentUpdate,
)

router = APIRouter(prefix="/departments", tags=["Departments"])


@router.get("", response_model=list[DepartmentRead])
def list_departments(db: Session = Depends(get_db), _u: User = Depends(require_edit)):
    return db.query(Department).order_by(Department.name).all()


@router.post("", response_model=DepartmentRead, status_code=201)
def create_department(
    body: DepartmentCreate,
    db: Session = Depends(get_db),
    _u: User = Depends(require_edit),
):
    if db.query(Department).filter(Department.code == body.code).first():
        raise HTTPException(status_code=400, detail="Department code already exists")
    dept = Department(**body.model_dump())
    db.add(dept)
    db.commit()
    db.refresh(dept)
    return dept


@router.patch("/{dept_id}", response_model=DepartmentRead)
def update_department(
    dept_id: int,
    body: DepartmentUpdate,
    db: Session = Depends(get_db),
    _u: User = Depends(require_edit),
):
    dept = db.query(Department).filter(Department.id == dept_id).first()
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(dept, field, value)
    db.commit()
    db.refresh(dept)
    return dept


@router.delete("/{dept_id}", status_code=204)
def delete_department(
    dept_id: int,
    db: Session = Depends(get_db),
    _u: User = Depends(require_edit),
):
    dept = db.query(Department).filter(Department.id == dept_id).first()
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")
    if dept.employees:
        raise HTTPException(
            status_code=400, detail="Cannot delete a department with employees"
        )
    db.delete(dept)
    db.commit()
