"""ShiftType endpoints (v2) — manager-configurable shift definitions."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import require_edit
from app.core.database import get_db
from app.models.shift_type import ShiftType
from app.models.user import User
from app.schemas.shift_type import (
    ShiftTypeCreate,
    ShiftTypeRead,
    ShiftTypeUpdate,
)

router = APIRouter(prefix="/shift-types", tags=["Shift Types"])


@router.get("", response_model=list[ShiftTypeRead])
def list_shift_types(
    is_active: bool | None = Query(None),
    db: Session = Depends(get_db),
    _u: User = Depends(require_edit),
):
    q = db.query(ShiftType)
    if is_active is not None:
        q = q.filter(ShiftType.is_active == is_active)
    return q.order_by(ShiftType.code).all()


@router.post("", response_model=ShiftTypeRead, status_code=201)
def create_shift_type(
    body: ShiftTypeCreate,
    db: Session = Depends(get_db),
    _u: User = Depends(require_edit),
):
    if db.query(ShiftType).filter(ShiftType.code == body.code).first():
        raise HTTPException(status_code=400, detail="Shift code already exists")
    st = ShiftType(**body.model_dump())
    db.add(st)
    db.commit()
    db.refresh(st)
    return st


@router.patch("/{shift_type_id}", response_model=ShiftTypeRead)
def update_shift_type(
    shift_type_id: int,
    body: ShiftTypeUpdate,
    db: Session = Depends(get_db),
    _u: User = Depends(require_edit),
):
    st = db.query(ShiftType).filter(ShiftType.id == shift_type_id).first()
    if not st:
        raise HTTPException(status_code=404, detail="Shift type not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(st, field, value)
    db.commit()
    db.refresh(st)
    return st


@router.delete("/{shift_type_id}", status_code=204)
def delete_shift_type(
    shift_type_id: int,
    db: Session = Depends(get_db),
    _u: User = Depends(require_edit),
):
    """Soft-delete by deactivating (keeps historical roster cells valid)."""
    st = db.query(ShiftType).filter(ShiftType.id == shift_type_id).first()
    if not st:
        raise HTTPException(status_code=404, detail="Shift type not found")
    st.is_active = False
    db.commit()
