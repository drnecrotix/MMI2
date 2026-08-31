import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.models import ImportHistory


class ImportHistoryActorTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)

    def test_session_actor_is_written_to_new_import_history(self):
        with Session(self.engine) as db:
            db.info["admin_actor"] = "moderator@example.com"
            row = ImportHistory(
                filename="schedule.xlsx",
                content_hash="a" * 64,
                year=2026,
                month=9,
                employees=10,
                shifts=300,
                schedule_blocks=1,
                duplicate_employee_rows=0,
                conflicting_days=0,
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            self.assertEqual(row.imported_by, "moderator@example.com")

    def test_existing_explicit_actor_is_not_overwritten(self):
        with Session(self.engine) as db:
            db.info["admin_actor"] = "owner@example.com"
            row = ImportHistory(
                filename="legacy-import.xlsx",
                content_hash="b" * 64,
                year=2026,
                month=8,
                imported_by="admin@example.com",
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            self.assertEqual(row.imported_by, "admin@example.com")

    def test_history_without_actor_remains_valid(self):
        with Session(self.engine) as db:
            row = ImportHistory(
                filename="old.xlsx",
                content_hash="c" * 64,
                year=2026,
                month=7,
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            self.assertIsNone(row.imported_by)


if __name__ == "__main__":
    unittest.main()
