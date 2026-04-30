"""Clinic CRUD endpoints with Nominatim geocoding."""

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.database import get_db
from app.models.clinic import Clinic
from app.models.user import User
from app.schemas.clinic import ClinicCreate, ClinicRead, ClinicUpdate

router = APIRouter(prefix="/clinics", tags=["Clinics"])

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


def _geocode(address: str) -> tuple[float | None, float | None]:
    """Geocode an address using Nominatim (OpenStreetMap). Returns (lat, lng) or (None, None)."""
    try:
        resp = httpx.get(
            NOMINATIM_URL,
            params={"q": address, "format": "json", "limit": 1},
            headers={"User-Agent": "Medihospes-Scheduling/1.0"},
            timeout=5.0,
        )
        resp.raise_for_status()
        results = resp.json()
        if results:
            return float(results[0]["lat"]), float(results[0]["lon"])
    except Exception:
        pass
    return None, None


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

    lat, lng = None, None
    if body.address:
        lat, lng = _geocode(body.address)

    clinic = Clinic(**body.model_dump(), latitude=lat, longitude=lng)
    db.add(clinic)
    db.commit()
    db.refresh(clinic)
    return clinic


@router.patch("/{clinic_id}", response_model=ClinicRead)
def update_clinic(
    clinic_id: int,
    body: ClinicUpdate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    clinic = db.query(Clinic).filter(Clinic.id == clinic_id).first()
    if not clinic:
        raise HTTPException(status_code=404, detail="Clinic not found")

    update_data = body.model_dump(exclude_unset=True)

    # If address changed, re-geocode
    if "address" in update_data and update_data["address"]:
        lat, lng = _geocode(update_data["address"])
        update_data["latitude"] = lat
        update_data["longitude"] = lng

    for field, value in update_data.items():
        setattr(clinic, field, value)

    db.commit()
    db.refresh(clinic)
    return clinic


@router.post("/{clinic_id}/geocode", response_model=ClinicRead)
def geocode_clinic(
    clinic_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Re-geocode a clinic's address (useful if coordinates are missing)."""
    clinic = db.query(Clinic).filter(Clinic.id == clinic_id).first()
    if not clinic:
        raise HTTPException(status_code=404, detail="Clinic not found")
    if not clinic.address:
        raise HTTPException(status_code=400, detail="Clinic has no address to geocode")

    lat, lng = _geocode(clinic.address)
    if lat is None:
        raise HTTPException(status_code=422, detail="Could not geocode address")

    clinic.latitude = lat
    clinic.longitude = lng
    db.commit()
    db.refresh(clinic)
    return clinic
