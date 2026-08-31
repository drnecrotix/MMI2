from __future__ import annotations

from calendar import monthrange
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Employee, ShiftEntry
from app.schemas import MonthlyScheduleOut, ScheduleSummaryOut, ShiftOut
from app.services.schedule_fallback import generate_2x2_fallback


FALLBACK_WARNING = (
    "Графикът за този месец още не е обновен. Показан е автоматично изчислен режим 2 на 2 "
    "(2 работни / 2 почивни дни). Той е ориентировъчен и може да се различава от официалния график."
)
PARTIAL_WARNING = (
    "Официалният график за този месец е наличен само частично. Дните без запис са отбелязани като "
    "„Няма данни“ и не се заместват автоматично с почивка или прогнозен график."
)


def _empty_summary() -> dict[str, int]:
    return {
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


def _summary_for(shifts: list[ShiftOut]) -> ScheduleSummaryOut:
    totals = _empty_summary()
    for shift in shifts:
        if shift.shift_type not in totals:
            totals["unknown"] += 1
        else:
            totals[shift.shift_type] += 1
    return ScheduleSummaryOut(**totals)


def build_monthly_schedule(db: Session, employee: Employee, year: int, month: int) -> MonthlyScheduleOut:
    days_count = monthrange(year, month)[1]
    first = date(year, month, 1)
    last = date(year, month, days_count)
    entries = db.scalars(
        select(ShiftEntry)
        .where(
            ShiftEntry.employee_id == employee.id,
            ShiftEntry.work_date >= first,
            ShiftEntry.work_date <= last,
        )
        .order_by(ShiftEntry.work_date)
    ).all()

    if entries:
        by_date = {entry.work_date: entry for entry in entries}
        shifts: list[ShiftOut] = []
        for day_number in range(1, days_count + 1):
            work_date = date(year, month, day_number)
            entry = by_date.get(work_date)
            if entry is None:
                shifts.append(
                    ShiftOut(
                        work_date=work_date,
                        shift_type="missing",
                        raw_code="",
                        estimated=False,
                    )
                )
            else:
                shifts.append(
                    ShiftOut(
                        work_date=entry.work_date,
                        shift_type=entry.shift_type,
                        raw_code=entry.raw_code,
                        estimated=False,
                    )
                )

        missing_days = sum(1 for shift in shifts if shift.shift_type == "missing")
        is_partial = missing_days > 0
        last_updated_at = max((entry.imported_at for entry in entries), default=None)
        return MonthlyScheduleOut(
            employee_name=employee.full_name,
            work_number=employee.work_number,
            team=employee.team,
            year=year,
            month=month,
            days_in_month=days_count,
            shifts=shifts,
            summary=_summary_for(shifts),
            schedule_source="imported",
            schedule_status="partial" if is_partial else "official",
            is_estimated=False,
            is_partial=is_partial,
            missing_days=missing_days,
            warning=PARTIAL_WARNING if is_partial else None,
            last_updated_at=last_updated_at,
        )

    fallback = generate_2x2_fallback(db, employee, year, month)
    shifts = [
        ShiftOut(
            work_date=entry.work_date,
            shift_type=entry.shift_type,
            raw_code=entry.raw_code,
            estimated=True,
        )
        for entry in fallback.shifts
    ]
    return MonthlyScheduleOut(
        employee_name=employee.full_name,
        work_number=employee.work_number,
        team=employee.team,
        year=year,
        month=month,
        days_in_month=days_count,
        shifts=shifts,
        summary=_summary_for(shifts),
        schedule_source="automatic_2x2",
        schedule_status="estimated",
        is_estimated=True,
        is_partial=False,
        missing_days=0,
        warning=FALLBACK_WARNING,
        last_updated_at=None,
        fallback_confidence=fallback.confidence,
        fallback_basis=fallback.basis,
        fallback_reference_date=fallback.reference_date,
    )
