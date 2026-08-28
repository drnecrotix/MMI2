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
    "работен номер", "работен №", "работен no", "табелен номер", "таб. номер",
    "employee number", "work number", "id",
}
NAME_HEADERS = {"име", "име на служителя", "служител", "трите имена", "name", "employee"}

SHIFT_ALIASES = {
    "Д": "day",
    "ДН": "day",
    "DAY": "day",
    "ДНЕВНА": "day",
    "Н": "night",
    "НОЩ": "night",
    "NIGHT": "night",
    "НОЩНА": "night",
    "П": "rest",
    "ПОЧ": "rest",
    "ПОЧИВКА": "rest",
    "REST": "rest",
    "OFF": "rest",
    "К": "compensation",
    "КОМП": "compensation",
    "КОМПЕНСАЦИЯ": "compensation",
    "COMP": "compensation",
    "О": "leave",
    "ОТП": "leave",
    "ОТПУСК": "leave",
    "LEAVE": "leave",
    "VACATION": "leave",
}


@dataclass
class ImportResult:
    employees: int = 0
    shifts: int = 0
    skipped_rows: int = 0


def _norm(value: object) -> str:
    text = "" if value is None else str(value)
    text = unicodedata.normalize("NFKC", text).strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def _shift_type(value: object) -> tuple[str, str]:
    raw = "" if value is None else str(value).strip()
    key = raw.upper().replace(".", "").strip()
    if not raw:
        return "unknown", ""
    return SHIFT_ALIASES.get(key, "unknown"), raw


def _day_from_header(value: object, year: int, month: int) -> int | None:
    if isinstance(value, datetime):
        return value.day if value.year == year and value.month == month else None
    if isinstance(value, date):
        return value.day if value.year == year and value.month == month else None
    if isinstance(value, int) and 1 <= value <= 31:
        return value
    text = _norm(value)
    if text.isdigit() and 1 <= int(text) <= 31:
        return int(text)
    match = re.search(r"\b([0-2]?\d|3[01])\b", text)
    return int(match.group(1)) if match and 1 <= int(match.group(1)) <= 31 else None


def _find_header_row(ws) -> tuple[int, dict[int, str]]:
    for row_idx in range(1, min(ws.max_row, 20) + 1):
        cells = {_norm(ws.cell(row_idx, col).value): col for col in range(1, ws.max_column + 1)}
        work_col = next((cells[h] for h in WORK_NUMBER_HEADERS if h in cells), None)
        name_col = next((cells[h] for h in NAME_HEADERS if h in cells), None)
        if work_col and name_col:
            return row_idx, {work_col: "work_number", name_col: "name"}
    raise ValueError("Не са открити колони за работен номер и име на служител.")


def import_schedule_xlsx(db: Session, content: bytes, filename: str, year: int, month: int) -> ImportResult:
    if Path(filename).suffix.lower() != ".xlsx":
        raise ValueError("Поддържат се само .xlsx файлове.")

    workbook = load_workbook(BytesIO(content), data_only=True)
    result = ImportResult()
    seen_employees: set[int] = set()

    for ws in workbook.worksheets:
        try:
            header_row, columns = _find_header_row(ws)
        except ValueError:
            continue

        work_col = next(col for col, kind in columns.items() if kind == "work_number")
        name_col = next(col for col, kind in columns.items() if kind == "name")
        day_columns: dict[int, int] = {}
        for col in range(1, ws.max_column + 1):
            if col in (work_col, name_col):
                continue
            day = _day_from_header(ws.cell(header_row, col).value, year, month)
            if day:
                day_columns[col] = day

        for row in range(header_row + 1, ws.max_row + 1):
            work_number = str(ws.cell(row, work_col).value or "").strip()
            full_name = str(ws.cell(row, name_col).value or "").strip()
            if not work_number or not full_name:
                result.skipped_rows += 1
                continue

            employee = db.scalar(select(Employee).where(Employee.work_number == work_number))
            if employee is None:
                employee = Employee(work_number=work_number, full_name=full_name)
                db.add(employee)
                db.flush()
            elif employee.full_name != full_name:
                employee.full_name = full_name

            seen_employees.add(employee.id)

            for col, day in day_columns.items():
                try:
                    work_date = date(year, month, day)
                except ValueError:
                    continue
                shift_type, raw_code = _shift_type(ws.cell(row, col).value)
                if not raw_code:
                    continue

                existing = db.scalar(
                    select(ShiftEntry).where(
                        ShiftEntry.employee_id == employee.id,
                        ShiftEntry.work_date == work_date,
                    )
                )
                if existing:
                    existing.shift_type = shift_type
                    existing.raw_code = raw_code
                    existing.source_file = filename
                else:
                    db.add(
                        ShiftEntry(
                            employee_id=employee.id,
                            work_date=work_date,
                            shift_type=shift_type,
                            raw_code=raw_code,
                            source_file=filename,
                        )
                    )
                result.shifts += 1

    db.commit()
    result.employees = len(seen_employees)
    if result.employees == 0:
        raise ValueError("Не беше открит използваем лист с данни за служители.")
    return result
