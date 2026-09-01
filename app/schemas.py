from calendar import monthrange
from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator


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
    days_in_month: int = 0
    shifts: list[ShiftOut]
    summary: ScheduleSummaryOut = Field(default_factory=ScheduleSummaryOut)
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

    @model_validator(mode="after")
    def normalize_month(self):
        days_count = monthrange(self.year, self.month)[1]
        self.days_in_month = days_count

        if not self.is_estimated and self.shifts:
            by_date = {shift.work_date: shift for shift in self.shifts}
            self.shifts = [
                by_date.get(
                    date(self.year, self.month, day_number),
                    ShiftOut(
                        work_date=date(self.year, self.month, day_number),
                        shift_type="missing",
                        raw_code="",
                        estimated=False,
                    ),
                )
                for day_number in range(1, days_count + 1)
            ]

        totals = {
            "day": 0,
            "night": 0,
            "leave": 0,
            "sick_leave": 0,
            "rest": 0,
            "unknown": 0,
            "predicted_work": 0,
            "predicted_rest": 0,
            "missing": 0,
        }
        for shift in self.shifts:
            key = shift.shift_type if shift.shift_type in totals else "unknown"
            totals[key] += 1
        self.summary = ScheduleSummaryOut(**totals)
        self.missing_days = totals["missing"]

        if self.is_estimated:
            self.schedule_status = "estimated"
            self.is_partial = False
        else:
            self.is_partial = self.missing_days > 0
            self.schedule_status = "partial" if self.is_partial else "official"
            if self.is_partial and not self.warning:
                self.warning = (
                    "Официалният график за този месец е наличен само частично. "
                    "Дните без запис са отбелязани като „Няма данни“ и не се приемат за почивка."
                )
        return self


class AdminEmployeeUpdate(BaseModel):
    full_name: str | None = None
    team: str | None = None


class AdminShiftUpdate(BaseModel):
    raw_code: str = ""
