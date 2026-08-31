import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class AppStartupSchemaTests(unittest.TestCase):
    def test_importing_app_does_not_create_database_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            database_path = Path(tmp) / "startup.db"
            env = os.environ.copy()
            env.update(
                {
                    "DATABASE_URL": f"sqlite:///{database_path}",
                    "JWT_SECRET": "test-secret",
                    "ADMIN_USERNAME": "test-admin",
                    "ADMIN_PASSWORD": "test-admin-password",
                }
            )

            completed = subprocess.run(
                [sys.executable, "-c", "import app.main"],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertFalse(
                database_path.exists(),
                "Importing app.main must not create a SQLite database. Run Alembic migrations explicitly.",
            )


if __name__ == "__main__":
    unittest.main()
