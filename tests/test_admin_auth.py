import unittest

from app.config import settings
from app.security import (
    create_access_token,
    create_admin_token,
    decode_access_token,
    decode_admin_token,
    verify_admin_credentials,
)


class AdminAuthTests(unittest.TestCase):
    def test_employee_and_admin_tokens_are_not_interchangeable(self):
        employee_token = create_access_token("1234")
        admin_token = create_admin_token(settings.admin_username)

        self.assertEqual(decode_access_token(employee_token), "1234")
        self.assertIsNone(decode_admin_token(employee_token))

        self.assertEqual(decode_admin_token(admin_token), settings.admin_username)
        self.assertIsNone(decode_access_token(admin_token))

    def test_admin_credentials_require_exact_username_and_password(self):
        self.assertTrue(verify_admin_credentials(settings.admin_username, settings.admin_password))
        self.assertFalse(verify_admin_credentials(settings.admin_username, settings.admin_password + "x"))
        self.assertFalse(verify_admin_credentials(settings.admin_username + "x", settings.admin_password))


if __name__ == "__main__":
    unittest.main()
