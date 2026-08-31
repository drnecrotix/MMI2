import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import AdminUser
from app.security import verify_password
from install import service
from install.service import DatabaseSetup, InstallRequest, InstallerError


class InstallerTests(unittest.TestCase):
    def test_sqlite_install_creates_owner_env_lock_and_requires_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            database_path = root / "mmi2-installed.db"
            env_path = root / ".env"
            lock_path = root / "install.lock"
            restart_path = root / "restart.required"
            old_database_url = settings.database_url
            old_jwt_secret = settings.jwt_secret

            try:
                settings.database_url = "sqlite:///" + database_path.as_posix()
                settings.jwt_secret = "runtime-before-installer"
                payload = InstallRequest(
                    database=DatabaseSetup(driver="sqlite", sqlite_path=str(database_path)),
                    owner_email="owner@example.com",
                    owner_password="very-secure-owner-password",
                    owner_password_confirm="very-secure-owner-password",
                    app_name="MMI2 Test",
                )

                with (
                    patch.object(service, "ENV_FILE", env_path),
                    patch.object(service, "LOCK_FILE", lock_path),
                    patch.object(service, "RESTART_FILE", restart_path),
                ):
                    result = service.complete_installation(payload)
                    self.assertEqual(result["status"], "installed")
                    self.assertTrue(result["restart_required"])
                    self.assertTrue(lock_path.exists())
                    self.assertTrue(restart_path.exists())

                    env_text = env_path.read_text(encoding="utf-8")
                    self.assertIn('ADMIN_BOOTSTRAP_ENABLED="false"', env_text)
                    self.assertIn('ADMIN_EMAIL="owner@example.com"', env_text)
                    self.assertNotIn("ADMIN_PASSWORD=", env_text)
                    self.assertNotIn("very-secure-owner-password", env_text)

                    engine = create_engine("sqlite:///" + database_path.as_posix())
                    with Session(engine) as db:
                        owner = db.scalar(select(AdminUser).where(AdminUser.email == "owner@example.com"))
                        self.assertIsNotNone(owner)
                        self.assertEqual(owner.role, "owner")
                        self.assertTrue(owner.is_active)
                        self.assertTrue(verify_password("very-secure-owner-password", owner.password_hash))
                    engine.dispose()

                    state = service.get_installation_state()
                    self.assertTrue(state.installed)
                    self.assertTrue(state.restart_required)

                    values = {}
                    for line in env_text.splitlines():
                        if "=" in line and not line.lstrip().startswith("#"):
                            key, value = line.split("=", 1)
                            values[key] = value.strip().strip('"')
                    settings.jwt_secret = values["JWT_SECRET"]
                    settings.database_url = values["DATABASE_URL"]
                    state_after_restart = service.get_installation_state()
                    self.assertTrue(state_after_restart.installed)
                    self.assertFalse(state_after_restart.restart_required)
                    self.assertFalse(restart_path.exists())
            finally:
                settings.database_url = old_database_url
                settings.jwt_secret = old_jwt_secret

    def test_locked_installer_rejects_second_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock_path = Path(tmp) / "install.lock"
            lock_path.write_text(json.dumps({"installed": True}), encoding="utf-8")
            payload = InstallRequest(
                database=DatabaseSetup(driver="sqlite", sqlite_path=str(Path(tmp) / "db.sqlite")),
                owner_email="owner@example.com",
                owner_password="very-secure-owner-password",
                owner_password_confirm="very-secure-owner-password",
            )
            with patch.object(service, "LOCK_FILE", lock_path):
                with self.assertRaises(InstallerError):
                    service.complete_installation(payload)

    def test_password_must_not_be_short_or_mismatched(self):
        with self.assertRaises(InstallerError):
            service._validate_password("short", "short")
        with self.assertRaises(InstallerError):
            service._validate_password("long-enough-password", "different-password")


if __name__ == "__main__":
    unittest.main()
