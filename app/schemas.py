from datetime import date
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    work_number: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    employee_name: str
    work_number: str
    team: str | None = None


class AdminLoginRequest(BaseModel):
    username: str
    password: str


class AdminTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role: str


class AdminAccountCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=10, max_length=200)
    role: str = "admin"


class AdminAccountUpdate(BaseModel):
    role: str | None = None
    is_active: bool | None = None


class AdminPasswordUpdate(BaseModel):
    password: str = Field(min_length=10, max_length=200)


class ShiftOut(BaseModel):
    work_date: date
    shift_type: str
    raw_code: str
    estimated: bool = False


class MonthlyScheduleOut(BaseModel):
    employee_name: str
    work_number: str
    team: str | None = None
    year: int
    month: int
    shifts: list[ShiftOut]
    schedule_source: str = "imported"
    is_estimated: bool = False
    warning: str | None = None
    fallback_confidence: str | None = None
    fallback_basis: str | None = None
    fallback_reference_date: date | None = None


class AdminEmployeeUpdate(BaseModel):
    full_name: str | None = None
    team: str | None = None


class AdminShiftUpdate(BaseModel):
    raw_code: str = ""
