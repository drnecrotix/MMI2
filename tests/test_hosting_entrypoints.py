import unittest

from a2wsgi import ASGIMiddleware

import run
import passenger_wsgi


class HostingEntrypointTests(unittest.TestCase):
    def test_n0c_exposes_run_app_wsgi_callable(self):
        self.assertIsInstance(run.app, ASGIMiddleware)
        self.assertTrue(callable(run.app))

    def test_cpanel_exposes_passenger_application(self):
        self.assertIs(passenger_wsgi.application, run.app)
        self.assertTrue(callable(passenger_wsgi.application))

    def test_compatibility_alias_is_available(self):
        self.assertIs(run.application, run.app)


if __name__ == "__main__":
    unittest.main()
