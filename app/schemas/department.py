"""Department schemas (v2)."""

from pydantic import BaseModel


class DepartmentCreate(BaseModel):
    name: str
    code: str


class DepartmentUpdate(BaseModel):
    name: str | None = None
    code: str | None = None


class DepartmentRead(BaseModel):
    id: int
    name: str
    code: str

    model_config = {"from_attributes": True}
