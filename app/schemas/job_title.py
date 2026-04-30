"""Job title request/response schemas."""

from datetime import datetime

from pydantic import BaseModel


class JobTitleCreate(BaseModel):
    name: str
    label: str


class JobTitleUpdate(BaseModel):
    name: str | None = None
    label: str | None = None
    is_active: bool | None = None


class JobTitleRead(BaseModel):
    id: int
    name: str
    label: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
