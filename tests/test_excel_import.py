from io import BytesIO
import unittest

from openpyxl import Workbook
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db import Base
from app.models import Employee, ShiftEntry
from app.services.excel_import import import_schedule_xlsx


class ExcelImportTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)

    def _workbook_bytes(self) -> bytes:
        wb = Workbook()
        ws = wb.active
        ws.title = "ГРАФИК"

        ws["B1"] = "№ ред"
        ws["C1"] = "Раб. №"
        ws["D1"] = "Име, фамилия"
        ws["E1"] = "длъжност"
        for day, col in enumerate(range(7, 38), start=1):
            ws.cell(2, col).value = day

        ws["B5"] = 1
        ws["C5"] = 1234
        ws["D5"] = "Тест Служител"
        ws["E5"] = "маш. лок."
        ws["F5"] = "В"
        ws["G5"] = 1
        ws["H5"] = 2
        ws["I5"] = "О"
        ws["J5"] = 0
        ws["K5"] = "Б"
        ws["L5"] = "П"  # not part of the confirmed legend - preserve as unknown
        # Remaining empty cells are scheduled rest days.

        stream = BytesIO()
        wb.save(stream)
        return stream.getvalue()

    def test_confirmed_mmi2_legend_and_employee_team(self):
        with Session(self.engine) as db:
            result = import_schedule_xlsx(db, self._workbook_bytes(), "test.xlsx", 2026, 7)
            self.assertEqual(result.schedule_blocks, 1)
            self.assertEqual(result.employees, 1)
            self.assertEqual(result.shifts, 31)

            employee = db.scalar(select(Employee).where(Employee.work_number == "1234"))
            self.assertEqual(employee.full_name, "Тест Служител")
            self.assertEqual(employee.team, "В")

            entries = db.scalars(
                select(ShiftEntry)
                .where(ShiftEntry.employee_id == employee.id)
                .order_by(ShiftEntry.work_date)
            ).all()
            by_day = {entry.work_date.day: entry for entry in entries}

            self.assertEqual(by_day[1].shift_type, "day")
            self.assertEqual(by_day[2].shift_type, "night")
            self.assertEqual(by_day[3].shift_type, "leave")
            self.assertEqual(by_day[4].shift_type, "leave")
            self.assertEqual(by_day[5].shift_type, "sick_leave")
            self.assertEqual(by_day[6].shift_type, "unknown")
            self.assertEqual(by_day[6].raw_code, "П")
            self.assertEqual(by_day[7].shift_type, "rest")
            self.assertEqual(by_day[7].raw_code, "")


if __name__ == "__main__":
    unittest.main()
