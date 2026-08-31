import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session

from app.db import Base
from app.models import Employee


EXPECTED_TABLES = {
    "employees",
    "shift_entries",
    "import_history",
    "manual_edit_history",
    "admin_users",
    "alembic_version",
}


class MigrationTests(unittest.TestCase):
    def _alembic(self, database_url: str, target: str = "head") -> None:
        env = os.environ.copy()
        env["DATABASE_URL"] = database_url
        env["JWT_SECRET"] = "migration-test-secret"
        env["ADMIN_EMAIL"] = "owner@example.com"
        env["ADMIN_USERNAME"] = "test-admin"
        env["ADMIN_PASSWORD"] = "test-admin-password"
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", target],
            check=True,
            env=env,
            capture_output=True,
            text=True,
        )

    def test_upgrade_creates_current_schema_on_empty_database(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "fresh.db"
            url = "sqlite:///" + db_path.as_posix()
            self._alembic(url)

            engine = create_engine(url)
            inspector = inspect(engine)
            self.assertTrue(EXPECTED_TABLES.issubset(set(inspector.get_table_names())))
            audit_columns = {item["name"]: item for item in inspector.get_columns("manual_edit_history")}
            self.assertIn("changed_by", audit_columns)
            self.assertEqual(getattr(audit_columns["changed_by"]["type"], "length", None), 255)
            admin_columns = {item["name"] for item in inspector.get_columns("admin_users")}
            self.assertTrue({"email", "password_hash", "role", "is_active", "last_login_at"}.issubset(admin_columns))

    def test_upgrade_adopts_existing_metadata_database_without_data_loss(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "existing.db"
            url = "sqlite:///" + db_path.as_posix()
            engine = create_engine(url)
            Base.metadata.create_all(engine)

            with Session(engine) as db:
                db.add(Employee(work_number="1234", full_name="Тест Служител", team="А"))
                db.commit()

            self._alembic(url)

            inspector = inspect(engine)
            self.assertIn("alembic_version", inspector.get_table_names())
            self.assertIn("admin_users", inspector.get_table_names())
            with Session(engine) as db:
                employee = db.scalar(select(Employee).where(Employee.work_number == "1234"))
                self.assertIsNotNone(employee)
                self.assertEqual(employee.full_name, "Тест Служител")

    def test_upgrade_from_baseline_adds_audit_actor(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "baseline.db"
            url = "sqlite:///" + db_path.as_posix()
            self._alembic(url, "20260831_0001")
            engine = create_engine(url)
            columns_before = {item["name"] for item in inspect(engine).get_columns("manual_edit_history")}
            self.assertNotIn("changed_by", columns_before)

            self._alembic(url, "20260831_0002")
            columns_after = {item["name"] for item in inspect(engine).get_columns("manual_edit_history")}
            self.assertIn("changed_by", columns_after)

    def test_upgrade_from_audit_revision_adds_admin_users(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "audit.db"
            url = "sqlite:///" + db_path.as_posix()
            self._alembic(url, "20260831_0002")
            engine = create_engine(url)
            self.assertNotIn("admin_users", inspect(engine).get_table_names())

            self._alembic(url)
            inspector = inspect(engine)
            self.assertIn("admin_users", inspector.get_table_names())
            audit_columns = {item["name"]: item for item in inspector.get_columns("manual_edit_history")}
            self.assertEqual(getattr(audit_columns["changed_by"]["type"], "length", None), 255)


if __name__ == "__main__":
    unittest.main()
