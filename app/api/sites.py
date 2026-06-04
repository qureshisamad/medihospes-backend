"""Site endpoints (v2 — reshaped from Clinics, no geocoding)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import require_edit
from app.core.database import get_db
from app.models.site import Site
from app.models.user import User
from app.schemas.site import SiteCreate, SiteRead, SiteUpdate

router = APIRouter(prefix="/sites", tags=["Sites"])


@router.get("", response_model=list[SiteRead])
def list_sites(db: Session = Depends(get_db), _u: User = Depends(require_edit)):
    return db.query(Site).order_by(Site.name).all()


@router.post("", response_model=SiteRead, status_code=201)
def create_site(
    body: SiteCreate,
    db: Session = Depends(get_db),
    _u: User = Depends(require_edit),
):
    if db.query(Site).filter(Site.code == body.code).first():
        raise HTTPException(status_code=400, detail="Site code already exists")
    site = Site(**body.model_dump())
    db.add(site)
    db.commit()
    db.refresh(site)
    return site


@router.patch("/{site_id}", response_model=SiteRead)
def update_site(
    site_id: int,
    body: SiteUpdate,
    db: Session = Depends(get_db),
    _u: User = Depends(require_edit),
):
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(site, field, value)
    db.commit()
    db.refresh(site)
    return site


@router.delete("/{site_id}", status_code=204)
def delete_site(
    site_id: int,
    db: Session = Depends(get_db),
    _u: User = Depends(require_edit),
):
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    db.delete(site)
    db.commit()
