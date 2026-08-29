from datetime import date
from pydantic import BaseModel


class LoginRequest(BaseModel):
    work_number: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    employee_name: str
    work_number: str
    team: str | None = None


class ShiftOut(BaseModel):
    work_date: date
    shift_type: str
    raw_code: str


class MonthlyScheduleOut(BaseModel):
    employee_name: str
    work_number: str
    team: str | None = None
    year: int
    month: int
    shifts: list[ShiftOut]


class AdminEmployeeUpdate(BaseModel):
    full_name: str | None = None
    team: str | None = None


class AdminShiftUpdate(BaseModel):
    raw_code: str = ""
