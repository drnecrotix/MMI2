import asyncio
import unittest
from dataclasses import dataclass
from unittest.mock import patch

from starlette.requests import Request
from starlette.responses import Response

from app.main import installation_gate


@dataclass(frozen=True)
class FakeState:
    installed: bool
    restart_required: bool
    adopted_existing: bool = False


def make_request(path: str) -> Request:
    return Request(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "https",
            "path": path,
            "raw_path": path.encode("utf-8"),
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 1234),
            "server": ("testserver", 443),
        }
    )


async def passed_response(_request: Request) -> Response:
    return Response("passed", status_code=200)


class InstallNamespaceLockTests(unittest.TestCase):
    def test_install_namespace_returns_404_after_completed_restart(self):
        state = FakeState(installed=True, restart_required=False)
        with patch("app.main.get_installation_state", return_value=state):
            for path in ("/install", "/install/", "/install/restart", "/install/api/status"):
                response = asyncio.run(installation_gate(make_request(path), passed_response))
                self.assertEqual(response.status_code, 404, path)

    def test_only_restart_endpoint_is_temporarily_allowed_before_restart(self):
        state = FakeState(installed=True, restart_required=True)
        with patch("app.main.get_installation_state", return_value=state):
            restart_response = asyncio.run(
                installation_gate(make_request("/install/restart"), passed_response)
            )
            install_response = asyncio.run(
                installation_gate(make_request("/install"), passed_response)
            )

        self.assertEqual(restart_response.status_code, 200)
        self.assertEqual(install_response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
