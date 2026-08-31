from datetime import date
import unittest

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db import Base
from app.main import admin_update_shift
from app.models import AdminUser, Employee, ManualEditHistory, ShiftEntry
from app.schemas import AdminShiftUpdate


class ManualAdminEditTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)

    def test_manual_shift_edit_updates_schedule_and_creates_audit_row(self):
        with Session(self.engine) as db:
            employee = Employee(work_number="1234", full_name="Тест Служител", team="А")
            actor = AdminUser(
                email="moderator@example.com",
                password_hash="test-hash",
                role="moderator",
                is_active=True,
            )
            db.add_all([employee, actor])
            db.flush()
            db.add(ShiftEntry(
                employee_id=employee.id,
                work_date=date(2026, 9, 5),
                shift_type="rest",
                raw_code="",
                source_file="schedule.xlsx",
            ))
            db.commit()

            result = admin_update_shift(
                employee_id=employee.id,
                work_date=date(2026, 9, 5),
                payload=AdminShiftUpdate(raw_code="1"),
                account=actor,
                db=db,
            )

            self.assertEqual(result["status"], "updated")
            entry = db.scalar(select(ShiftEntry).where(ShiftEntry.employee_id == employee.id))
            self.assertEqual(entry.shift_type, "day")
            self.assertEqual(entry.raw_code, "1")
            self.assertEqual(entry.source_file, "manual-admin")

            audit = db.scalar(select(ManualEditHistory).where(ManualEditHistory.employee_id == employee.id))
            self.assertEqual(audit.work_date, date(2026, 9, 5))
            self.assertEqual(audit.field_name, "shift")
            self.assertEqual(audit.old_value, "rest|")
            self.assertEqual(audit.new_value, "day|1")
            self.assertEqual(audit.changed_by, "moderator@example.com")


if __name__ == "__main__":
    unittest.main()
