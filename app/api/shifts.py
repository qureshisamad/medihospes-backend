"""Shift management endpoints — publish, list, claim, cancel, calendar."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.core.database import get_db
from app.models.booking import BookingStatus, ShiftBooking
from app.models.clinic import Clinic
from app.models.shift import Shift, ShiftType
from app.models.time_entry import TimeEntry
from app.models.user import User, UserRole
from app.schemas.shift import (
    AttendanceStatus,
    BookingDetailRead,
    BookingRead,
    ShiftCreate,
    ShiftDetailRead,
    ShiftRead,
    WeeklyHoursRead,
)
from app.services.notification_service import NotificationService
from app.services.shift_service import claim_shift, get_weekly_booked_hours, _get_iso_week_bounds

router = APIRouter(prefix="/shifts", tags=["Shifts"])


def _enrich_shift(shift: Shift, db: Session) -> ShiftRead:
    """Add computed fields to a shift response."""
    count = (
        db.query(func.count(ShiftBooking.id))
        .filter(
            ShiftBooking.shift_id == shift.id,
            ShiftBooking.status == BookingStatus.CONFIRMED,
        )
        .scalar()
    )
    clinic_name = None
    if shift.clinic:
        clinic_name = shift.clinic.name
    return ShiftRead(
        id=shift.id,
        clinic_id=shift.clinic_id,
        clinic_name=clinic_name,
        required_role=shift.required_role,
        shift_type=shift.shift_type,
        start_time=shift.start_time,
        end_time=shift.end_time,
        max_capacity=shift.max_capacity,
        current_bookings=count or 0,
        notes=shift.notes,
        created_by=shift.created_by,
        created_at=shift.created_at,
    )


@router.get("/", response_model=list[ShiftRead])
def list_shifts(
    clinic_id: int | None = Query(None),
    role: str | None = Query(None),
    shift_type: ShiftType | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """List open shifts with optional filters."""
    q = db.query(Shift)
    if clinic_id:
        q = q.filter(Shift.clinic_id == clinic_id)
    if role:
        q = q.filter(Shift.required_role == role)
    if shift_type:
        q = q.filter(Shift.shift_type == shift_type)
    if date_from:
        q = q.filter(Shift.start_time >= date_from)
    if date_to:
        q = q.filter(Shift.end_time <= date_to)
    shifts = q.order_by(Shift.start_time).all()
    return [_enrich_shift(s, db) for s in shifts]


@router.get("/calendar", response_model=list[ShiftRead])
def calendar_shifts(
    date_from: datetime = Query(...),
    date_to: datetime = Query(...),
    clinic_id: int | None = Query(None),
    role: str | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return shifts within a date range, optimised for calendar rendering.

    Staff users see shifts matching their job_title by default (overridable
    via the ``role`` param).  Admin users see all shifts, optionally filtered.
    """
    q = db.query(Shift).filter(
        Shift.start_time >= date_from,
        Shift.start_time <= date_to,
    )

    if clinic_id is not None:
        q = q.filter(Shift.clinic_id == clinic_id)

    if user.role == UserRole.ADMIN:
        if role is not None:
            q = q.filter(Shift.required_role == role)
    else:
        # Staff: default to own job_title unless role param overrides
        effective_role = role if role is not None else user.job_title
        q = q.filter(Shift.required_role == effective_role)

    shifts = q.order_by(Shift.start_time).all()
    return [_enrich_shift(s, db) for s in shifts]


@router.get("/weekly-hours", response_model=WeeklyHoursRead)
def weekly_hours(
    week_of: datetime | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return the authenticated user's booked hours for an ISO week."""
    ref = week_of if week_of is not None else datetime.now(timezone.utc)
    booked = get_weekly_booked_hours(db, user.id, ref)
    week_start, week_end = _get_iso_week_bounds(ref)
    remaining = max(user.weekly_hour_limit - booked, 0.0)
    return WeeklyHoursRead(
        week_start=week_start,
        week_end=week_end,
        booked_hours=round(booked, 2),
        weekly_hour_limit=user.weekly_hour_limit,
        remaining_hours=round(remaining, 2),
    )


@router.get("/{shift_id}/details", response_model=ShiftDetailRead)
def shift_details(
    shift_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Return full shift details with bookings and attendance (admin only)."""
    shift = db.query(Shift).filter(Shift.id == shift_id).first()
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")

    # Creator name
    creator = db.query(User).filter(User.id == shift.created_by).first()
    creator_name = (
        f"{creator.first_name} {creator.last_name}" if creator else "Unknown"
    )

    # Build enriched base shift
    base = _enrich_shift(shift, db)

    now = datetime.now(timezone.utc)

    bookings_out: list[BookingDetailRead] = []
    for booking in shift.bookings:
        if booking.status != BookingStatus.CONFIRMED:
            continue

        booked_user = booking.user

        # Compute attendance status
        time_entry = (
            db.query(TimeEntry)
            .filter(TimeEntry.shift_booking_id == booking.id)
            .first()
        )

        if shift.start_time > now:
            att_status = AttendanceStatus.NOT_STARTED
        elif time_entry is None:
            att_status = AttendanceStatus.MISSING_CLOCK_IN
        elif time_entry.clock_out is None:
            att_status = AttendanceStatus.IN_PROGRESS
        else:
            att_status = AttendanceStatus.COMPLETED

        actual_hours: float | None = None
        if att_status == AttendanceStatus.COMPLETED and time_entry is not None:
            actual_hours = round(
                (time_entry.clock_out - time_entry.clock_in).total_seconds()
                / 3600,
                2,
            )

        bookings_out.append(
            BookingDetailRead(
                id=booking.id,
                user_id=booked_user.id,
                first_name=booked_user.first_name,
                last_name=booked_user.last_name,
                job_title=booked_user.job_title,
                status=booking.status.value,
                booked_at=booking.booked_at,
                attendance_status=att_status,
                actual_hours=actual_hours,
            )
        )

    return ShiftDetailRead(
        **base.model_dump(),
        creator_name=creator_name,
        bookings=bookings_out,
    )


@router.post("/", response_model=ShiftRead, status_code=201)
def publish_shift(
    body: ShiftCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Admin publishes a new open shift."""
    clinic = db.query(Clinic).filter(Clinic.id == body.clinic_id).first()
    if not clinic:
        raise HTTPException(status_code=404, detail="Clinic not found")
    shift = Shift(**body.model_dump(), created_by=admin.id)
    db.add(shift)
    db.commit()
    db.refresh(shift)
    NotificationService.notify_new_shift(db, shift)
    return _enrich_shift(shift, db)


@router.post("/{shift_id}/claim", response_model=BookingRead, status_code=201)
def claim_open_shift(
    shift_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Employee claims an available shift (algorithmic blocking applied)."""
    booking = claim_shift(db, user, shift_id)
    shift = db.query(Shift).filter(Shift.id == shift_id).first()
    NotificationService.notify_booking_confirmed(db, booking, shift)
    return BookingRead(
        id=booking.id,
        shift_id=booking.shift_id,
        user_id=booking.user_id,
        status=booking.status.value,
        booked_at=booking.booked_at,
    )


@router.get("/my-bookings", response_model=list[BookingRead])
def my_bookings(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List the current user's shift bookings."""
    bookings = (
        db.query(ShiftBooking)
        .filter(ShiftBooking.user_id == user.id)
        .order_by(ShiftBooking.booked_at.desc())
        .all()
    )
    results = []
    for b in bookings:
        shift_data = _enrich_shift(b.shift, db) if b.shift else None
        results.append(
            BookingRead(
                id=b.id,
                shift_id=b.shift_id,
                user_id=b.user_id,
                status=b.status.value,
                booked_at=b.booked_at,
                shift=shift_data,
            )
        )
    return results


@router.delete("/{booking_id}/cancel", status_code=204)
def cancel_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Cancel a shift booking."""
    booking = db.query(ShiftBooking).filter(ShiftBooking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    if booking.user_id != user.id and user.role.value != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    booking.status = BookingStatus.CANCELLED
    db.commit()
