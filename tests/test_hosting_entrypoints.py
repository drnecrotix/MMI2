import os
import unittest
from unittest.mock import patch

from a2wsgi import ASGIMiddleware

import run
import passenger_wsgi
from install.hosting import detect_hosting_runtime


class HostingEntrypointTests(unittest.TestCase):
    def test_n0c_exposes_run_app_wsgi_callable(self):
        self.assertIsInstance(run.app, ASGIMiddleware)
        self.assertTrue(callable(run.app))

    def test_cpanel_exposes_passenger_application(self):
        self.assertIs(passenger_wsgi.application, run.app)
        self.assertTrue(callable(passenger_wsgi.application))

    def test_compatibility_alias_is_available(self):
        self.assertIs(run.application, run.app)

    def test_installer_detects_n0c_marker(self):
        with patch.dict(os.environ, {"MMI2_HOSTING_PLATFORM": "n0c"}, clear=False):
            runtime = detect_hosting_runtime()
        self.assertEqual(runtime.platform, "n0c")
        self.assertIn("N0C", runtime.label)
        self.assertEqual(runtime.entrypoint, "run.py → app")

    def test_installer_detects_cpanel_marker(self):
        with patch.dict(os.environ, {"MMI2_HOSTING_PLATFORM": "cpanel"}, clear=False):
            runtime = detect_hosting_runtime()
        self.assertEqual(runtime.platform, "cpanel")
        self.assertIn("cPanel", runtime.label)
        self.assertEqual(runtime.entrypoint, "passenger_wsgi.py → application")

    def test_generic_runtime_is_fallback(self):
        with patch.dict(os.environ, {}, clear=True):
            runtime = detect_hosting_runtime()
        self.assertEqual(runtime.platform, "generic")
        self.assertEqual(runtime.entrypoint, "app.main:app")


if __name__ == "__main__":
    unittest.main()
