"""Employee schemas (v2) — the scheduled person + their contract."""

from datetime import datetime

from pydantic import BaseModel

from app.models.employee import ContractType


class EmployeeBase(BaseModel):
    first_name: str
    last_name: str
    codice_fiscale: str | None = None
    department_id: int
    site_id: int | None = None
    job_title: str
    location: str | None = None
    contract_type: ContractType
    monthly_hour_limit: float
    flexible_shift: bool = False
    flexible_location: bool = False


class EmployeeCreate(EmployeeBase):
    coverable_roles: list[str] = []


class EmployeeUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    codice_fiscale: str | None = None
    department_id: int | None = None
    site_id: int | None = None
    job_title: str | None = None
    location: str | None = None
    contract_type: ContractType | None = None
    monthly_hour_limit: float | None = None
    flexible_shift: bool | None = None
    flexible_location: bool | None = None
    is_active: bool | None = None
    coverable_roles: list[str] | None = None


class EmployeeRead(EmployeeBase):
    id: int
    is_active: bool
    created_at: datetime
    coverable_roles: list[str] = []

    model_config = {"from_attributes": True}
