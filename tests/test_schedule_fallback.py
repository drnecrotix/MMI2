from datetime import date, timedelta
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.main import my_schedule
from app.models import Employee, ShiftEntry
from app.services.schedule_fallback import generate_2x2_fallback


class ScheduleFallbackTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)

    def test_infers_2x2_phase_from_recent_imported_history(self):
        with Session(self.engine) as db:
            employee = Employee(work_number="7001", full_name="Тест Служител", team="Г")
            db.add(employee)
            db.flush()

            phase = 2
            current = date(2026, 8, 1)
            for _ in range(24):
                is_work = ((current.toordinal() + phase) % 4) < 2
                db.add(ShiftEntry(
                    employee_id=employee.id,
                    work_date=current,
                    shift_type="day" if is_work else "rest",
                    raw_code="1" if is_work else "",
                    source_file="august.xlsx",
                ))
                current += timedelta(days=1)
            db.commit()

            result = generate_2x2_fallback(db, employee, 2026, 9)

            self.assertEqual(result.basis, "history")
            self.assertEqual(result.confidence, "high")
            self.assertEqual(len(result.shifts), 30)
            for shift in result.shifts[:8]:
                expected_work = ((shift.work_date.toordinal() + phase) % 4) < 2
                self.assertEqual(shift.shift_type, "predicted_work" if expected_work else "predicted_rest")

    def test_team_phase_is_used_when_no_history_exists(self):
        with Session(self.engine) as db:
            employee = Employee(work_number="7002", full_name="Нов Служител", team="Б")
            db.add(employee)
            db.commit()

            result = generate_2x2_fallback(db, employee, 2026, 9)

            self.assertEqual(result.basis, "team")
            self.assertEqual(result.confidence, "low")
            self.assertEqual(len(result.shifts), 30)
            self.assertTrue(all(s.shift_type in {"predicted_work", "predicted_rest"} for s in result.shifts))

    def test_employee_schedule_api_marks_fallback_as_estimated(self):
        with Session(self.engine) as db:
            employee = Employee(work_number="7003", full_name="Без График", team="А")
            db.add(employee)
            db.commit()

            response = my_schedule(year=2026, month=9, employee=employee, db=db)

            self.assertTrue(response.is_estimated)
            self.assertEqual(response.schedule_source, "automatic_2x2")
            self.assertEqual(response.schedule_status, "estimated")
            self.assertIn("2 на 2", response.warning)
            self.assertEqual(response.days_in_month, 30)
            self.assertEqual(len(response.shifts), 30)
            self.assertEqual(
                response.summary.predicted_work + response.summary.predicted_rest,
                30,
            )
            self.assertTrue(all(s.estimated for s in response.shifts))

    def test_partial_imported_month_returns_explicit_missing_days(self):
        with Session(self.engine) as db:
            employee = Employee(work_number="7004", full_name="С График", team="В")
            db.add(employee)
            db.flush()
            db.add(ShiftEntry(
                employee_id=employee.id,
                work_date=date(2026, 9, 1),
                shift_type="night",
                raw_code="2",
                source_file="september.xlsx",
            ))
            db.commit()

            response = my_schedule(year=2026, month=9, employee=employee, db=db)

            self.assertFalse(response.is_estimated)
            self.assertTrue(response.is_partial)
            self.assertEqual(response.schedule_source, "imported")
            self.assertEqual(response.schedule_status, "partial")
            self.assertEqual(response.days_in_month, 30)
            self.assertEqual(len(response.shifts), 30)
            self.assertEqual(response.shifts[0].shift_type, "night")
            self.assertEqual(response.summary.night, 1)
            self.assertEqual(response.summary.missing, 29)
            self.assertEqual(response.missing_days, 29)
            self.assertEqual(response.shifts[1].shift_type, "missing")
            self.assertIn("частично", response.warning.lower())


if __name__ == "__main__":
    unittest.main()
