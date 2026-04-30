"""Clinic request/response schemas."""

from pydantic import BaseModel


class ClinicCreate(BaseModel):
    name: str
    code: str
    address: str | None = None


class ClinicUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class ClinicRead(BaseModel):
    id: int
    name: str
    code: str
    address: str | None
    latitude: float | None
    longitude: float | None

    model_config = {"from_attributes": True}
