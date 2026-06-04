"""ShiftType schemas (v2)."""

from datetime import time

from pydantic import BaseModel


class ShiftTypeCreate(BaseModel):
    code: str
    name: str
    start_time: time
    end_time: time
    duration_hours: float
    crosses_midnight: bool = False
    notes: str | None = None


class ShiftTypeUpdate(BaseModel):
    code: str | None = None
    name: str | None = None
    start_time: time | None = None
    end_time: time | None = None
    duration_hours: float | None = None
    crosses_midnight: bool | None = None
    notes: str | None = None
    is_active: bool | None = None


class ShiftTypeRead(BaseModel):
    id: int
    code: str
    name: str
    start_time: time
    end_time: time
    duration_hours: float
    crosses_midnight: bool
    notes: str | None
    is_active: bool

    model_config = {"from_attributes": True}
