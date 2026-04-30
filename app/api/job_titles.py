"""Job title management endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.core.database import get_db
from app.models.job_title import JobTitleRecord
from app.models.user import User
from app.schemas.job_title import JobTitleCreate, JobTitleRead, JobTitleUpdate

router = APIRouter(prefix="/job-titles", tags=["Job Titles"])


@router.get("", response_model=list[JobTitleRead])
def list_job_titles(
    is_active: bool | None = Query(None),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """List all job titles. Any authenticated user can read these."""
    q = db.query(JobTitleRecord)
    if is_active is not None:
        q = q.filter(JobTitleRecord.is_active == is_active)
    return q.order_by(JobTitleRecord.label).all()


@router.post("", response_model=JobTitleRead, status_code=201)
def create_job_title(
    body: JobTitleCreate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Create a new job title (admin only)."""
    existing = (
        db.query(JobTitleRecord)
        .filter(JobTitleRecord.name == body.name)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Job title name already exists")

    record = JobTitleRecord(name=body.name, label=body.label)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.patch("/{job_title_id}", response_model=JobTitleRead)
def update_job_title(
    job_title_id: int,
    body: JobTitleUpdate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Update a job title (admin only)."""
    record = db.query(JobTitleRecord).filter(JobTitleRecord.id == job_title_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Job title not found")

    update_data = body.model_dump(exclude_unset=True)

    if "name" in update_data:
        existing = (
            db.query(JobTitleRecord)
            .filter(
                JobTitleRecord.name == update_data["name"],
                JobTitleRecord.id != job_title_id,
            )
            .first()
        )
        if existing:
            raise HTTPException(status_code=400, detail="Job title name already in use")

    for field, value in update_data.items():
        setattr(record, field, value)

    db.commit()
    db.refresh(record)
    return record


@router.delete("/{job_title_id}", status_code=204)
def delete_job_title(
    job_title_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Delete a job title (admin only). Soft-deletes by deactivating."""
    record = db.query(JobTitleRecord).filter(JobTitleRecord.id == job_title_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Job title not found")

    record.is_active = False
    db.commit()
