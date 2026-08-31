import unittest
from dataclasses import dataclass
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


@dataclass(frozen=True)
class FakeState:
    installed: bool
    restart_required: bool
    adopted_existing: bool = False


class InstallNamespaceLockTests(unittest.TestCase):
    def test_install_namespace_returns_404_after_completed_restart(self):
        state = FakeState(installed=True, restart_required=False)
        with patch("app.main.get_installation_state", return_value=state):
            client = TestClient(app)
            self.assertEqual(client.get("/install").status_code, 404)
            self.assertEqual(client.get("/install/").status_code, 404)
            self.assertEqual(client.get("/install/restart").status_code, 404)
            self.assertEqual(client.get("/install/api/status").status_code, 404)

    def test_restart_page_is_temporarily_available_before_restart(self):
        state = FakeState(installed=True, restart_required=True)
        with (
            patch("app.main.get_installation_state", return_value=state),
            patch("install.router.get_installation_state", return_value=state),
        ):
            client = TestClient(app)
            response = client.get("/install/restart")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(client.get("/install").status_code, 404)


if __name__ == "__main__":
    unittest.main()
