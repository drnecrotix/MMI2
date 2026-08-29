from __future__ import annotations

from calendar import monthrange
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Employee, ShiftEntry
from app.services.excel_preview import PreviewResult


MAX_CHANGE_DETAILS = 500


def compare_preview_to_database(db: Session, preview: PreviewResult, year: int, month: int) -> dict:
    work_numbers = [row["work_number"] for row in preview.employees]
    employees = db.scalars(select(Employee).where(Employee.work_number.in_(work_numbers))).all() if work_numbers else []
    existing_employees = {employee.work_number: employee for employee in employees}

    first = date(year, month, 1)
    last = date(year, month, monthrange(year, month)[1])
    employee_ids = [employee.id for employee in employees]
    shifts = db.scalars(
        select(ShiftEntry).where(
            ShiftEntry.employee_id.in_(employee_ids),
            ShiftEntry.work_date >= first,
            ShiftEntry.work_date <= last,
        )
    ).all() if employee_ids else []
    existing_shifts = {(shift.employee_id, shift.work_date): shift for shift in shifts}

    employee_rows = {row["work_number"]: row for row in preview.employees}
    new_employee_numbers = {number for number in work_numbers if number not in existing_employees}
    team_changes = []
    for number, employee in existing_employees.items():
        new_team = employee_rows[number]["team"]
        if (employee.team or "") != (new_team or ""):
            team_changes.append({
                "work_number": number,
                "full_name": employee_rows[number]["full_name"],
                "old_team": employee.team,
                "new_team": new_team,
            })

    new_days = 0
    changed_days = 0
    unchanged_days = 0
    details = []

    for row in preview.day_entries:
        employee = existing_employees.get(row["work_number"])
        existing = existing_shifts.get((employee.id, row["work_date"])) if employee else None
        if existing is None:
            new_days += 1
            kind = "new_employee_day" if row["work_number"] in new_employee_numbers else "new_day"
            if len(details) < MAX_CHANGE_DETAILS:
                details.append({
                    "kind": kind,
                    "work_number": row["work_number"],
                    "full_name": row["full_name"],
                    "work_date": row["work_date"].isoformat(),
                    "old_type": None,
                    "old_code": None,
                    "new_type": row["shift_type"],
                    "new_code": row["raw_code"],
                })
            continue

        if existing.shift_type != row["shift_type"] or existing.raw_code != row["raw_code"]:
            changed_days += 1
            if len(details) < MAX_CHANGE_DETAILS:
                details.append({
                    "kind": "changed",
                    "work_number": row["work_number"],
                    "full_name": row["full_name"],
                    "work_date": row["work_date"].isoformat(),
                    "old_type": existing.shift_type,
                    "old_code": existing.raw_code,
                    "new_type": row["shift_type"],
                    "new_code": row["raw_code"],
                })
        else:
            unchanged_days += 1

    total_changes = new_days + changed_days + len(team_changes)
    return {
        "database_has_period": bool(shifts),
        "new_employees": len(new_employee_numbers),
        "new_employee_work_numbers": sorted(new_employee_numbers),
        "team_changes": team_changes,
        "new_days": new_days,
        "changed_days": changed_days,
        "unchanged_days": unchanged_days,
        "total_changes": total_changes,
        "details": details,
        "details_truncated": (new_days + changed_days) > len(details),
        "detail_limit": MAX_CHANGE_DETAILS,
    }
