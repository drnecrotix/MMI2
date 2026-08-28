from datetime import date
from pydantic import BaseModel


class LoginRequest(BaseModel):
    work_number: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    employee_name: str
    work_number: str


class ShiftOut(BaseModel):
    work_date: date
    shift_type: str
    raw_code: str


class MonthlyScheduleOut(BaseModel):
    employee_name: str
    work_number: str
    year: int
    month: int
    shifts: list[ShiftOut]
