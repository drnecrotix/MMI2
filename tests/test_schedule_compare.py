from datetime import date
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.models import Employee, ShiftEntry
from app.services.excel_preview import PreviewResult
from app.services.schedule_compare import compare_preview_to_database


class ScheduleCompareTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)

    def test_detects_changed_new_and_unchanged_days(self):
        with Session(self.engine) as db:
            employee = Employee(work_number="1234", full_name="Тест Служител", team="А")
            db.add(employee)
            db.flush()
            db.add_all([
                ShiftEntry(employee_id=employee.id, work_date=date(2026, 7, 1), shift_type="day", raw_code="1"),
                ShiftEntry(employee_id=employee.id, work_date=date(2026, 7, 2), shift_type="night", raw_code="2"),
            ])
            db.commit()

            preview = PreviewResult(
                employees=[{
                    "work_number": "1234", "full_name": "Тест Служител", "team": "Б",
                    "day": 0, "night": 1, "leave": 1, "sick_leave": 0, "rest": 1, "unknown": 0,
                }],
                day_entries=[
                    {"work_number": "1234", "full_name": "Тест Служител", "team": "Б", "work_date": date(2026, 7, 1), "shift_type": "leave", "raw_code": "О"},
                    {"work_number": "1234", "full_name": "Тест Служител", "team": "Б", "work_date": date(2026, 7, 2), "shift_type": "night", "raw_code": "2"},
                    {"work_number": "1234", "full_name": "Тест Служител", "team": "Б", "work_date": date(2026, 7, 3), "shift_type": "rest", "raw_code": ""},
                ],
                schedule_blocks=1,
                duplicate_employee_rows=0,
                conflicting_days=0,
                unknown_codes={},
                totals={"leave": 1, "night": 1, "rest": 1},
            )

            result = compare_preview_to_database(db, preview, 2026, 7)
            self.assertTrue(result["database_has_period"])
            self.assertEqual(result["changed_days"], 1)
            self.assertEqual(result["new_days"], 1)
            self.assertEqual(result["unchanged_days"], 1)
            self.assertEqual(len(result["team_changes"]), 1)
            self.assertEqual(result["team_changes"][0]["old_team"], "А")
            self.assertEqual(result["team_changes"][0]["new_team"], "Б")
            changed = next(row for row in result["details"] if row["kind"] == "changed")
            self.assertEqual(changed["old_type"], "day")
            self.assertEqual(changed["new_type"], "leave")

    def test_first_import_marks_all_days_as_new(self):
        preview = PreviewResult(
            employees=[{
                "work_number": "9999", "full_name": "Нов Служител", "team": "В",
                "day": 1, "night": 0, "leave": 0, "sick_leave": 0, "rest": 0, "unknown": 0,
            }],
            day_entries=[{
                "work_number": "9999", "full_name": "Нов Служител", "team": "В",
                "work_date": date(2026, 8, 1), "shift_type": "day", "raw_code": "1",
            }],
            schedule_blocks=1,
            duplicate_employee_rows=0,
            conflicting_days=0,
            unknown_codes={},
            totals={"day": 1},
        )
        with Session(self.engine) as db:
            result = compare_preview_to_database(db, preview, 2026, 8)
            self.assertFalse(result["database_has_period"])
            self.assertEqual(result["new_employees"], 1)
            self.assertEqual(result["new_days"], 1)
            self.assertEqual(result["changed_days"], 0)


if __name__ == "__main__":
    unittest.main()
