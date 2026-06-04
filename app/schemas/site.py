"""Site schemas (v2 — reshaped from Clinic, no geolocation)."""

from pydantic import BaseModel


class SiteCreate(BaseModel):
    name: str
    code: str
    address: str | None = None


class SiteUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    address: str | None = None


class SiteRead(BaseModel):
    id: int
    name: str
    code: str
    address: str | None

    model_config = {"from_attributes": True}
