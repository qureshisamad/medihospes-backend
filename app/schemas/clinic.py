"""Clinic request/response schemas."""

from pydantic import BaseModel


class ClinicCreate(BaseModel):
    name: str
    code: str
    address: str | None = None


class ClinicRead(BaseModel):
    id: int
    name: str
    code: str
    address: str | None

    model_config = {"from_attributes": True}
