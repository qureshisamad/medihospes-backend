"""Shift request/response schemas."""

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, model_validator

from app.models.shift import ShiftType
from app.models.user import JobTitle


class ShiftCreate(BaseModel):
    clinic_id: int
    required_role: JobTitle
    shift_type: ShiftType
    start_time: datetime
    end_time: datetime
    max_capacity: int = 1
    notes: str | None = None

    @model_validator(mode="after")
    def validate_shift(self) -> "ShiftCreate":
        errors: list[str] = []

        if self.end_time <= self.start_time:
            errors.append(
                "end_time must be after start_time"
            )

        if self.start_time <= datetime.now(timezone.utc):
            errors.append(
                "start_time must be in the future"
            )

        if self.max_capacity < 1:
            errors.append(
                "max_capacity must be at least 1"
            )

        if errors:
            raise ValueError("; ".join(errors))

        return self


class ShiftRead(BaseModel):
    id: int
    clinic_id: int
    clinic_name: str | None = None
    required_role: JobTitle
    shift_type: ShiftType
    start_time: datetime
    end_time: datetime
    max_capacity: int
    current_bookings: int = 0
    notes: str | None
    created_by: int
    created_at: datetime

    model_config = {"from_attributes": True}


class BookingRead(BaseModel):
    id: int
    shift_id: int
    user_id: int
    status: str
    booked_at: datetime
    shift: ShiftRead | None = None

    model_config = {"from_attributes": True}


# --- New schemas for calendar shift management ---


class AttendanceStatus(str, Enum):
    NOT_STARTED = "not_started"
    MISSING_CLOCK_IN = "missing_clock_in"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class BookingDetailRead(BaseModel):
    id: int
    user_id: int
    first_name: str
    last_name: str
    job_title: JobTitle
    status: str
    booked_at: datetime
    attendance_status: AttendanceStatus
    actual_hours: float | None = None

    model_config = {"from_attributes": True}


class ShiftDetailRead(ShiftRead):
    creator_name: str
    bookings: list[BookingDetailRead]


class WeeklyHoursRead(BaseModel):
    week_start: datetime
    week_end: datetime
    booked_hours: float
    weekly_hour_limit: float
    remaining_hours: float
