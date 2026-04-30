"""Clinic CRUD endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.database import get_db
from app.models.clinic import Clinic
from app.models.user import User
from app.schemas.clinic import ClinicCreate, ClinicRead

router = APIRouter(prefix="/clinics", tags=["Clinics"])


@router.get("/", response_model=list[ClinicRead])
def list_clinics(db: Session = Depends(get_db)):
    return db.query(Clinic).order_by(Clinic.name).all()


@router.post("/", response_model=ClinicRead, status_code=201)
def create_clinic(
    body: ClinicCreate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    if db.query(Clinic).filter(Clinic.code == body.code).first():
        raise HTTPException(status_code=400, detail="Clinic code already exists")
    clinic = Clinic(**body.model_dump())
    db.add(clinic)
    db.commit()
    db.refresh(clinic)
    return clinic
