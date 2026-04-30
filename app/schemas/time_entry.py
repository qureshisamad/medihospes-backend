"""Time entry request/response schemas."""

from datetime import datetime

from pydantic import BaseModel


class ClockInRequest(BaseModel):
    shift_booking_id: int


class ClockOutRequest(BaseModel):
    time_entry_id: int


class TimeEntryRead(BaseModel):
    id: int
    user_id: int
    shift_booking_id: int
    clock_in: datetime
    clock_out: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
