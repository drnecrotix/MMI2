import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.models import AdminUser, Employee
from app.services import system_diagnostics


class SystemDiagnosticsTests(unittest.TestCase):
    def test_diagnostics_are_safe_and_detect_schema_mismatch(self):
        with tempfile.TemporaryDirectory() as temporary:
            db_path = Path(temporary) / "diagnostics.db"
            engine = create_engine(f"sqlite:///{db_path}")
            Base.metadata.create_all(engine)

            with Session(engine) as db:
                db.add(Employee(work_number="1001", full_name="Тест Служител", team="А"))
                db.add(AdminUser(email="owner@example.test", password_hash="not-a-real-secret", role="owner", is_active=True))
                db.commit()
                result = system_diagnostics.collect_system_diagnostics(db)

            self.assertEqual(result["database"]["driver"], "sqlite")
            self.assertTrue(result["database"]["connected"])
            self.assertEqual(result["database"]["employees"], 1)
            self.assertEqual(result["database"]["admin_accounts"], 1)
            self.assertFalse(result["database"]["schema_current"])
            self.assertEqual(result["status"], "error")
            self.assertTrue(result["backup"]["ready"])

            serialized = json.dumps(result, ensure_ascii=False).lower()
            self.assertNotIn("database_url", serialized)
            self.assertNotIn("jwt_secret", serialized)
            self.assertNotIn("password_hash", serialized)
            self.assertNotIn("not-a-real-secret", serialized)
            self.assertNotIn("sqlite:///", serialized)

    def test_current_schema_can_report_healthy_without_secret_data(self):
        with tempfile.TemporaryDirectory() as temporary:
            db_path = Path(temporary) / "healthy.db"
            lock_path = Path(temporary) / "install.lock"
            lock_path.write_text("installed", encoding="utf-8")
            engine = create_engine(f"sqlite:///{db_path}")
            Base.metadata.create_all(engine)

            with (
                Session(engine) as db,
                patch.object(system_diagnostics, "INSTALL_LOCK", lock_path),
                patch.object(system_diagnostics, "_migration_state", return_value=("head", "head", True)),
                patch.object(system_diagnostics, "get_update_runtime_state", return_value={"status": "ready"}),
            ):
                result = system_diagnostics.collect_system_diagnostics(db)

            self.assertNotEqual(result["status"], "error")
            self.assertTrue(result["database"]["schema_current"])
            self.assertTrue(result["installer"]["lock_present"])


if __name__ == "__main__":
    unittest.main()
