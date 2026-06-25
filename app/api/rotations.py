"""Rotation library endpoints (v2) — define the per-category shift cycle."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import require_edit
from app.core.database import get_db
from app.models.rotation import CoverageRequirement, RotationPattern, RotationStep
from app.models.shift_type import ShiftType
from app.models.user import User
from app.schemas.rotation import (
    CoverageItem,
    RotationPatternCreate,
    RotationPatternRead,
    RotationPatternUpdate,
)

router = APIRouter(prefix="/rotations", tags=["Rotation Library"])


def _serialize(p: RotationPattern) -> RotationPatternRead:
    return RotationPatternRead(
        id=p.id,
        name=p.name,
        job_title=p.job_title,
        site_id=p.site_id,
        site_name=p.site.name if p.site else None,
        is_active=p.is_active,
        shift_type_ids=[s.shift_type_id for s in p.steps],
        min_rest_hours=p.min_rest_hours,
        coverage=[
            CoverageItem(shift_type_id=c.shift_type_id, required_count=c.required_count)
            for c in p.coverage
        ],
    )


def _set_coverage(pattern: RotationPattern, items: list[CoverageItem]) -> None:
    pattern.coverage = [
        CoverageRequirement(
            shift_type_id=i.shift_type_id, required_count=i.required_count
        )
        for i in items
    ]


def _validate_shift_types(db: Session, ids: list[int]) -> None:
    if not ids:
        raise HTTPException(status_code=400, detail="Cycle must have at least one step")
    found = {s.id for s in db.query(ShiftType).filter(ShiftType.id.in_(ids)).all()}
    missing = [i for i in ids if i not in found]
    if missing:
        raise HTTPException(
            status_code=404, detail=f"Unknown shift type id(s): {missing}"
        )


def _set_steps(pattern: RotationPattern, ids: list[int]) -> None:
    pattern.steps = [
        RotationStep(position=i, shift_type_id=sid) for i, sid in enumerate(ids)
    ]


@router.get("", response_model=list[RotationPatternRead])
def list_rotations(
    job_title: str | None = Query(None),
    site_id: int | None = Query(None),
    is_active: bool | None = Query(None),
    db: Session = Depends(get_db),
    _u: User = Depends(require_edit),
):
    q = db.query(RotationPattern)
    if job_title:
        q = q.filter(RotationPattern.job_title == job_title)
    if site_id is not None:
        q = q.filter(RotationPattern.site_id == site_id)
    if is_active is not None:
        q = q.filter(RotationPattern.is_active == is_active)
    return [_serialize(p) for p in q.order_by(RotationPattern.name).all()]


@router.post("", response_model=RotationPatternRead, status_code=201)
def create_rotation(
    body: RotationPatternCreate,
    db: Session = Depends(get_db),
    _u: User = Depends(require_edit),
):
    _validate_shift_types(db, body.shift_type_ids)
    if body.coverage:
        _validate_shift_types(db, [c.shift_type_id for c in body.coverage])
    pattern = RotationPattern(
        name=body.name,
        job_title=body.job_title,
        site_id=body.site_id,
        min_rest_hours=body.min_rest_hours,
    )
    _set_steps(pattern, body.shift_type_ids)
    _set_coverage(pattern, body.coverage)
    db.add(pattern)
    db.commit()
    db.refresh(pattern)
    return _serialize(pattern)


@router.put("/{pattern_id}", response_model=RotationPatternRead)
def update_rotation(
    pattern_id: int,
    body: RotationPatternUpdate,
    db: Session = Depends(get_db),
    _u: User = Depends(require_edit),
):
    pattern = (
        db.query(RotationPattern).filter(RotationPattern.id == pattern_id).first()
    )
    if not pattern:
        raise HTTPException(status_code=404, detail="Rotation pattern not found")

    if body.name is not None:
        pattern.name = body.name
    if body.job_title is not None:
        pattern.job_title = body.job_title
    if "site_id" in body.model_fields_set:  # allow setting to null (category-wide)
        pattern.site_id = body.site_id
    if body.is_active is not None:
        pattern.is_active = body.is_active
    if body.min_rest_hours is not None:
        pattern.min_rest_hours = body.min_rest_hours
    if body.shift_type_ids is not None:
        _validate_shift_types(db, body.shift_type_ids)
    if body.coverage is not None and body.coverage:
        _validate_shift_types(db, [c.shift_type_id for c in body.coverage])

    # Clear children first so the unique constraints don't clash with the
    # replacement rows during flush.
    if body.shift_type_ids is not None:
        pattern.steps.clear()
    if body.coverage is not None:
        pattern.coverage.clear()
    if body.shift_type_ids is not None or body.coverage is not None:
        db.flush()
    if body.shift_type_ids is not None:
        _set_steps(pattern, body.shift_type_ids)
    if body.coverage is not None:
        _set_coverage(pattern, body.coverage)

    db.commit()
    db.refresh(pattern)
    return _serialize(pattern)


@router.delete("/{pattern_id}", status_code=204)
def delete_rotation(
    pattern_id: int,
    db: Session = Depends(get_db),
    _u: User = Depends(require_edit),
):
    pattern = (
        db.query(RotationPattern).filter(RotationPattern.id == pattern_id).first()
    )
    if pattern:
        db.delete(pattern)
        db.commit()
