from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
import re
import unicodedata

from openpyxl import load_workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Employee, ShiftEntry


WORK_NUMBER_HEADERS = {
    "раб. №", "раб №", "работен номер", "работен №", "работен no",
    "табелен номер", "таб. номер", "employee number", "work number", "id",
}
NAME_HEADERS = {
    "име, фамилия", "име фамилия", "име", "име на служителя", "служител",
    "трите имена", "name", "employee",
}
TEAM_CODES = {"А", "Б", "В", "Г"}


@dataclass
class ImportResult:
    employees: int = 0
    shifts: int = 0
    skipped_rows: int = 0
    schedule_blocks: int = 0
    duplicate_employee_rows: int = 0
    conflicting_days: int = 0


@dataclass
class ScheduleBlock:
    header_row: int
    days_row: int
    first_employee_row: int
    last_employee_row: int
    work_col: int
    name_col: int
    team_col: int
    day_columns: dict[int, int]


def _norm(value: object) -> str:
    text = "" if value is None else str(value)
    text = unicodedata.normalize("NFKC", text).strip().lower()
    return re.sub(r"\s+", " ", text)


def _raw(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _code(value: object) -> str:
    return _raw(value).upper().replace(".", "").strip()


def _day_from_header(value: object, year: int, month: int) -> int | None:
    if isinstance(value, datetime):
        return value.day if value.year == year and value.month == month else None
    if isinstance(value, date):
        return value.day if value.year == year and value.month == month else None
    if isinstance(value, int) and 1 <= value <= 31:
        return value
    if isinstance(value, float) and value.is_integer() and 1 <= int(value) <= 31:
        return int(value)
    text = _norm(value)
    if text.isdigit() and 1 <= int(text) <= 31:
        return int(text)
    return None


def _find_header_columns(ws, row_idx: int) -> tuple[int, int] | None:
    normalized = {
        _norm(ws.cell(row_idx, col).value): col
        for col in range(1, ws.max_column + 1)
        if ws.cell(row_idx, col).value is not None
    }
    work_col = next((normalized[h] for h in WORK_NUMBER_HEADERS if h in normalized), None)
    name_col = next((normalized[h] for h in NAME_HEADERS if h in normalized), None)
    return (work_col, name_col) if work_col and name_col else None


def _find_days_row(ws, header_row: int, year: int, month: int) -> tuple[int, dict[int, int]] | None:
    for row_idx in range(header_row, min(header_row + 5, ws.max_row) + 1):
        day_columns: dict[int, int] = {}
        for col in range(1, ws.max_column + 1):
            day = _day_from_header(ws.cell(row_idx, col).value, year, month)
            if day is not None:
                day_columns[col] = day
        if len(day_columns) >= 20:
            return row_idx, day_columns
    return None


def _is_employee_row(ws, row: int, work_col: int, name_col: int, team_col: int) -> bool:
    work_number = _raw(ws.cell(row, work_col).value)
    full_name = _raw(ws.cell(row, name_col).value)
    team = _code(ws.cell(row, team_col).value)
    return bool(
        work_number
        and full_name
        and any(ch.isdigit() for ch in work_number)
        and len(full_name) >= 3
        and team in TEAM_CODES
    )


def _find_employee_bounds(ws, start_row: int, work_col: int, name_col: int, team_col: int) -> tuple[int, int] | None:
    first: int | None = None
    last: int | None = None
    empty_run = 0
    for row in range(start_row, ws.max_row + 1):
        if _find_header_columns(ws, row) and first is not None:
            break
        if _is_employee_row(ws, row, work_col, name_col, team_col):
            first = row if first is None else first
            last = row
            empty_run = 0
            continue
        if first is not None:
            empty_run += 1
            if empty_run >= 4:
                break
    return (first, last) if first is not None and last is not None else None


def _discover_blocks(ws, year: int, month: int) -> list[ScheduleBlock]:
    blocks: list[ScheduleBlock] = []
    row = 1
    while row <= ws.max_row:
        columns = _find_header_columns(ws, row)
        if not columns:
            row += 1
            continue
        work_col, name_col = columns
        days_info = _find_days_row(ws, row, year, month)
        if not days_info:
            row += 1
            continue
        days_row, day_columns = days_info

        # In the provided MMI2 workbook the employee shift (А/Б/В/Г) is stored
        # in the column immediately before the first date column. We use the
        # employee's own value rather than the block heading, because a block can
        # contain employees assigned to another permanent shift.
        first_day_col = min(day_columns)
        team_col = first_day_col - 1

        bounds = _find_employee_bounds(ws, days_row + 1, work_col, name_col, team_col)
        if not bounds:
            row += 1
            continue
        first_employee_row, last_employee_row = bounds
        blocks.append(ScheduleBlock(
            header_row=row,
            days_row=days_row,
            first_employee_row=first_employee_row,
            last_employee_row=last_employee_row,
            work_col=work_col,
            name_col=name_col,
            team_col=team_col,
            day_columns=day_columns,
        ))
        row = last_employee_row + 1
    return blocks


def _shift_type(value: object) -> tuple[str, str]:
    """Map only the confirmed MMI2 legend supplied by the user.

    О or 0 = leave
    Б = sick leave
    1 = day shift
    2 = night shift
    empty = scheduled rest

    Any other value is preserved as unknown instead of being guessed.
    """
    raw_code = _raw(value)
    code = _code(value)

    if not code:
        return "rest", ""
    if code in {"О", "0"}:
        return "leave", raw_code
    if code == "Б":
        return "sick_leave", raw_code
    if code == "1":
        return "day", raw_code
    if code == "2":
        return "night", raw_code
    return "unknown", raw_code


def import_schedule_xlsx(db: Session, content: bytes, filename: str, year: int, month: int) -> ImportResult:
    if Path(filename).suffix.lower() != ".xlsx":
        raise ValueError("Поддържат се само .xlsx файлове.")

    workbook = load_workbook(BytesIO(content), data_only=True)
    result = ImportResult()
    seen_employee_ids: set[int] = set()
    seen_work_numbers: set[str] = set()
    touched_shift_keys: set[tuple[int, date]] = set()

    for ws in workbook.worksheets:
        blocks = _discover_blocks(ws, year, month)
        result.schedule_blocks += len(blocks)

        for block in blocks:
            for row in range(block.first_employee_row, block.last_employee_row + 1):
                if not _is_employee_row(ws, row, block.work_col, block.name_col, block.team_col):
                    result.skipped_rows += 1
                    continue

                work_number = _raw(ws.cell(row, block.work_col).value)
                full_name = _raw(ws.cell(row, block.name_col).value)
                team = _code(ws.cell(row, block.team_col).value)

                if work_number in seen_work_numbers:
                    result.duplicate_employee_rows += 1
                seen_work_numbers.add(work_number)

                employee = db.scalar(select(Employee).where(Employee.work_number == work_number))
                if employee is None:
                    employee = Employee(work_number=work_number, full_name=full_name, team=team)
                    db.add(employee)
                    db.flush()
                else:
                    if employee.full_name != full_name:
                        employee.full_name = full_name
                    employee.team = team
                seen_employee_ids.add(employee.id)

                for col, day in block.day_columns.items():
                    try:
                        work_date = date(year, month, day)
                    except ValueError:
                        continue

                    shift_type, raw_code = _shift_type(ws.cell(row, col).value)
                    key = (employee.id, work_date)
                    existing = db.scalar(select(ShiftEntry).where(
                        ShiftEntry.employee_id == employee.id,
                        ShiftEntry.work_date == work_date,
                    ))
                    if existing:
                        if key in touched_shift_keys and (
                            existing.shift_type != shift_type or existing.raw_code != raw_code
                        ):
                            result.conflicting_days += 1
                        existing.shift_type = shift_type
                        existing.raw_code = raw_code
                        existing.source_file = filename
                    else:
                        db.add(ShiftEntry(
                            employee_id=employee.id,
                            work_date=work_date,
                            shift_type=shift_type,
                            raw_code=raw_code,
                            source_file=filename,
                        ))
                    touched_shift_keys.add(key)

    db.commit()
    result.employees = len(seen_employee_ids)
    result.shifts = len(touched_shift_keys)
    if result.employees == 0:
        raise ValueError("Не беше открит използваем MMI2 график с данни за служители.")
    return result
