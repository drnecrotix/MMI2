import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

from app.config import settings
from app.services import self_update
from app.services.self_update import SelfUpdateError


class SelfUpdateTests(unittest.TestCase):
    def test_safe_archive_extracts_single_github_root(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive_path = root / "update.zip"
            with ZipFile(archive_path, "w") as archive:
                archive.writestr("MMI2-abc/app/version.py", 'APP_VERSION = "9.0.0"\nCURRENT_PR = 99\n')
                archive.writestr("MMI2-abc/requirements.txt", "fastapi==1\n")

            extracted = self_update._safe_extract_archive(archive_path, root / "out")
            self.assertEqual(extracted.name, "MMI2-abc")
            self.assertTrue((extracted / "app" / "version.py").is_file())

    def test_archive_path_traversal_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive_path = root / "bad.zip"
            with ZipFile(archive_path, "w") as archive:
                archive.writestr("MMI2-abc/../../outside.txt", "no")

            with self.assertRaises(SelfUpdateError):
                self_update._safe_extract_archive(archive_path, root / "out")

    def test_staged_build_must_cover_target_pr(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "app").mkdir()
            (root / "app" / "version.py").write_text(
                'APP_VERSION = "0.15.0"\nCURRENT_PR = 20\n', encoding="utf-8"
            )
            version, pr_number = self_update._read_staged_version(root, 19)
            self.assertEqual(version, "0.15.0")
            self.assertEqual(pr_number, 20)

            with self.assertRaises(SelfUpdateError):
                self_update._read_staged_version(root, 21)

    def test_sqlite_backup_capability_is_supported(self):
        previous = settings.database_url
        try:
            settings.database_url = "sqlite:///./mmi2.db"
            ok, mode, reason = self_update._database_backup_capability()
        finally:
            settings.database_url = previous
        self.assertTrue(ok)
        self.assertEqual(mode, "sqlite")
        self.assertIsNone(reason)

    def test_postgres_requires_dump_and_restore_tools(self):
        previous = settings.database_url
        try:
            settings.database_url = "postgresql+psycopg://user:pass@localhost/mmi2"
            with patch("app.services.self_update.shutil.which", return_value=None):
                ok, mode, reason = self_update._database_backup_capability()
        finally:
            settings.database_url = previous
        self.assertFalse(ok)
        self.assertEqual(mode, "postgresql")
        self.assertIn("pg_dump", reason or "")

    def test_worker_environment_marks_update_subprocess(self):
        env = self_update._worker_env()
        self.assertEqual(env["MMI2_UPDATE_WORKER"], "1")


if __name__ == "__main__":
    unittest.main()
