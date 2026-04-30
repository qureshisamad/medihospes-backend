"""
Shift booking service — contains the algorithmic blocking logic.

Validates:
1. Role match between user and shift
2. No time overlap with existing bookings
3. Weekly hour limit not exceeded
4. Shift capacity not reached (with row-level locking)
"""

from datetime import timedelta

from fastapi import HTTPException, status
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.models.booking import BookingStatus, ShiftBooking
from app.models.shift import Shift
from app.models.user import User


def _get_iso_week_bounds(dt):
    """Return (Monday 00:00, Sunday 23:59:59) for the ISO week containing dt."""
    monday = dt - timedelta(days=dt.weekday())
    monday = monday.replace(hour=0, minute=0, second=0, microsecond=0)
    sunday = monday + timedelta(days=6, hours=23, minutes=59, seconds=59)
    return monday, sunday


def get_weekly_booked_hours(db: Session, user_id: int, ref_date) -> float:
    """Sum hours the user has booked in the ISO week of ref_date."""
    week_start, week_end = _get_iso_week_bounds(ref_date)

    rows = (
        db.query(Shift.start_time, Shift.end_time)
        .join(ShiftBooking, ShiftBooking.shift_id == Shift.id)
        .filter(
            ShiftBooking.user_id == user_id,
            ShiftBooking.status == BookingStatus.CONFIRMED,
            Shift.start_time >= week_start,
            Shift.start_time <= week_end,
        )
        .all()
    )
    total = sum(
        (row.end_time - row.start_time).total_seconds() / 3600 for row in rows
    )
    return total


def has_time_overlap(db: Session, user_id: int, shift: Shift) -> bool:
    """Check if the user already has a confirmed booking that overlaps."""
    overlap = (
        db.query(ShiftBooking)
        .join(Shift, Shift.id == ShiftBooking.shift_id)
        .filter(
            ShiftBooking.user_id == user_id,
            ShiftBooking.status == BookingStatus.CONFIRMED,
            Shift.start_time < shift.end_time,
            Shift.end_time > shift.start_time,
        )
        .first()
    )
    return overlap is not None


def claim_shift(db: Session, user: User, shift_id: int) -> ShiftBooking:
    """
    Attempt to book a shift for the user.
    Raises HTTPException on any validation failure.
    """
    # Lock the shift row to prevent race conditions
    shift = (
        db.query(Shift)
        .filter(Shift.id == shift_id)
        .with_for_update()
        .first()
    )
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")

    # 1. Role check
    if user.job_title != shift.required_role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Your role ({user.job_title.value}) does not match "
                   f"the required role ({shift.required_role.value})",
        )

    # 2. Capacity check
    confirmed_count = (
        db.query(func.count(ShiftBooking.id))
        .filter(
            ShiftBooking.shift_id == shift_id,
            ShiftBooking.status == BookingStatus.CONFIRMED,
        )
        .scalar()
    )
    if confirmed_count >= shift.max_capacity:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Shift is already at full capacity",
        )

    # 3. Overlap check
    if has_time_overlap(db, user.id, shift):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This shift overlaps with one you have already booked",
        )

    # 4. Weekly hour limit check
    shift_hours = (shift.end_time - shift.start_time).total_seconds() / 3600
    current_hours = get_weekly_booked_hours(db, user.id, shift.start_time)
    if current_hours + shift_hours > user.weekly_hour_limit:
        remaining = round(user.weekly_hour_limit - current_hours, 1)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Booking this {shift_hours:.1f}h shift would exceed your "
                   f"weekly limit of {user.weekly_hour_limit}h. "
                   f"You have {remaining}h remaining this week.",
        )

    # All checks passed — create booking
    booking = ShiftBooking(shift_id=shift_id, user_id=user.id)
    db.add(booking)
    db.commit()
    db.refresh(booking)
    return booking
