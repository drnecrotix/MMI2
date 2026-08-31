from datetime import date, datetime
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
    email: str
    password: str


class AdminTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    email: str
    role: str


class AdminAccountCreate(BaseModel):
    email: str = Field(min_length=5, max_length=255)
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


class ScheduleSummaryOut(BaseModel):
    day: int = 0
    night: int = 0
    leave: int = 0
    sick_leave: int = 0
    rest: int = 0
    unknown: int = 0
    predicted_work: int = 0
    predicted_rest: int = 0
    missing: int = 0


class MonthlyScheduleOut(BaseModel):
    employee_name: str
    work_number: str
    team: str | None = None
    year: int
    month: int
    days_in_month: int
    shifts: list[ShiftOut]
    summary: ScheduleSummaryOut
    schedule_source: str = "imported"
    schedule_status: str = "official"
    is_estimated: bool = False
    is_partial: bool = False
    missing_days: int = 0
    warning: str | None = None
    last_updated_at: datetime | None = None
    fallback_confidence: str | None = None
    fallback_basis: str | None = None
    fallback_reference_date: date | None = None


class AdminEmployeeUpdate(BaseModel):
    full_name: str | None = None
    team: str | None = None


class AdminShiftUpdate(BaseModel):
    raw_code: str = ""
