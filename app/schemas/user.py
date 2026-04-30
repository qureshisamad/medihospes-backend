"""User request/response schemas."""

from datetime import datetime

from pydantic import BaseModel, EmailStr

from app.models.user import ContractType, JobTitle, UserRole


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    first_name: str
    last_name: str
    codice_fiscale: str | None = None
    job_title: JobTitle
    contract_type: ContractType
    weekly_hour_limit: float = 36.0
    role: UserRole = UserRole.STAFF


class UserRead(BaseModel):
    id: int
    email: str
    first_name: str
    last_name: str
    codice_fiscale: str | None
    role: UserRole
    job_title: JobTitle
    contract_type: ContractType
    weekly_hour_limit: float
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserLogin(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead
