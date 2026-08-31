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
    "alembic_version",
}


class MigrationTests(unittest.TestCase):
    def _upgrade(self, database_url: str) -> None:
        env = os.environ.copy()
        env["DATABASE_URL"] = database_url
        env["JWT_SECRET"] = "migration-test-secret"
        env["ADMIN_USERNAME"] = "test-admin"
        env["ADMIN_PASSWORD"] = "test-admin-password"
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            check=True,
            env=env,
            capture_output=True,
            text=True,
        )

    def test_upgrade_creates_current_schema_on_empty_database(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "fresh.db"
            url = "sqlite:///" + db_path.as_posix()
            self._upgrade(url)

            engine = create_engine(url)
            self.assertTrue(EXPECTED_TABLES.issubset(set(inspect(engine).get_table_names())))

    def test_upgrade_adopts_existing_metadata_database_without_data_loss(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "existing.db"
            url = "sqlite:///" + db_path.as_posix()
            engine = create_engine(url)
            Base.metadata.create_all(engine)

            with Session(engine) as db:
                db.add(Employee(work_number="1234", full_name="Тест Служител", team="А"))
                db.commit()

            self._upgrade(url)

            self.assertIn("alembic_version", inspect(engine).get_table_names())
            with Session(engine) as db:
                employee = db.scalar(select(Employee).where(Employee.work_number == "1234"))
                self.assertIsNotNone(employee)
                self.assertEqual(employee.full_name, "Тест Служител")


if __name__ == "__main__":
    unittest.main()
