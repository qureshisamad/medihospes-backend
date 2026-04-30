"""Admin reporting endpoints — attendance discrepancies."""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.database import get_db
from app.models.booking import BookingStatus, ShiftBooking
from app.models.shift import Shift
from app.models.time_entry import TimeEntry
from app.models.user import User

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/attendance")
def attendance_report(
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """
    Return attendance data with discrepancy flags:
    - missing_clock_in: booked but never clocked in
    - missing_clock_out: clocked in but never clocked out
    - late_clock_in: clocked in > 15 min after shift start
    - overtime: actual hours exceed scheduled hours
    """
    q = (
        db.query(ShiftBooking, Shift, TimeEntry, User)
        .join(Shift, Shift.id == ShiftBooking.shift_id)
        .join(User, User.id == ShiftBooking.user_id)
        .outerjoin(
            TimeEntry, TimeEntry.shift_booking_id == ShiftBooking.id
        )
        .filter(ShiftBooking.status == BookingStatus.CONFIRMED)
    )
    if date_from:
        q = q.filter(Shift.start_time >= date_from)
    if date_to:
        q = q.filter(Shift.end_time <= date_to)

    results = []
    for booking, shift, entry, user in q.all():
        scheduled_h = (shift.end_time - shift.start_time).total_seconds() / 3600
        actual_h = None
        flags = []

        if not entry:
            flags.append("missing_clock_in")
        else:
            if not entry.clock_out:
                flags.append("missing_clock_out")
            else:
                actual_h = (
                    entry.clock_out - entry.clock_in
                ).total_seconds() / 3600
                if actual_h > scheduled_h + 0.25:
                    flags.append("overtime")

            # Late check-in: > 15 minutes after shift start
            diff = (entry.clock_in - shift.start_time).total_seconds() / 60
            if diff > 15:
                flags.append("late_clock_in")

        results.append(
            {
                "employee": f"{user.first_name} {user.last_name}",
                "employee_id": user.id,
                "shift_date": shift.start_time.isoformat(),
                "shift_start": shift.start_time.isoformat(),
                "shift_end": shift.end_time.isoformat(),
                "scheduled_hours": round(scheduled_h, 2),
                "actual_hours": round(actual_h, 2) if actual_h else None,
                "clock_in": entry.clock_in.isoformat() if entry else None,
                "clock_out": (
                    entry.clock_out.isoformat()
                    if entry and entry.clock_out
                    else None
                ),
                "flags": flags,
            }
        )
    return results
