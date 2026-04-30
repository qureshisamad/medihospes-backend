"""Time clock endpoints — clock in / clock out."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.booking import BookingStatus, ShiftBooking
from app.models.time_entry import TimeEntry
from app.models.user import User
from app.schemas.time_entry import ClockInRequest, ClockOutRequest, TimeEntryRead

router = APIRouter(prefix="/time", tags=["Time Clock"])


@router.post("/clock-in", response_model=TimeEntryRead, status_code=201)
def clock_in(
    body: ClockInRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Clock in for a booked shift."""
    booking = (
        db.query(ShiftBooking)
        .filter(
            ShiftBooking.id == body.shift_booking_id,
            ShiftBooking.user_id == user.id,
            ShiftBooking.status == BookingStatus.CONFIRMED,
        )
        .first()
    )
    if not booking:
        raise HTTPException(status_code=404, detail="Confirmed booking not found")

    # Prevent double clock-in
    existing = (
        db.query(TimeEntry)
        .filter(
            TimeEntry.shift_booking_id == booking.id,
            TimeEntry.clock_out.is_(None),
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Already clocked in")

    entry = TimeEntry(
        user_id=user.id,
        shift_booking_id=booking.id,
        clock_in=datetime.now(timezone.utc),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.post("/clock-out", response_model=TimeEntryRead)
def clock_out(
    body: ClockOutRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Clock out from an active time entry."""
    entry = (
        db.query(TimeEntry)
        .filter(
            TimeEntry.id == body.time_entry_id,
            TimeEntry.user_id == user.id,
            TimeEntry.clock_out.is_(None),
        )
        .first()
    )
    if not entry:
        raise HTTPException(
            status_code=404, detail="Active time entry not found"
        )
    entry.clock_out = datetime.now(timezone.utc)
    db.commit()
    db.refresh(entry)
    return entry


@router.get("/my-entries", response_model=list[TimeEntryRead])
def my_time_entries(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List the current user's time entries."""
    return (
        db.query(TimeEntry)
        .filter(TimeEntry.user_id == user.id)
        .order_by(TimeEntry.clock_in.desc())
        .all()
    )
