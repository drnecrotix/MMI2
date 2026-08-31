import unittest

from app.config import settings
from app.security import (
    bootstrap_admin_email,
    create_access_token,
    create_admin_token,
    decode_access_token,
    decode_admin_token,
    hash_password,
    verify_bootstrap_admin_credentials,
    verify_password,
)


class AdminAuthTests(unittest.TestCase):
    def test_employee_and_admin_tokens_are_not_interchangeable(self):
        email = "owner@example.com"
        employee_token = create_access_token("1234")
        admin_token = create_admin_token(email)

        self.assertEqual(decode_access_token(employee_token), "1234")
        self.assertIsNone(decode_admin_token(employee_token))
        self.assertEqual(decode_admin_token(admin_token), email)
        self.assertIsNone(decode_access_token(admin_token))

    def test_scrypt_password_hash_round_trip(self):
        encoded = hash_password("very-strong-password")
        self.assertTrue(encoded.startswith("scrypt$"))
        self.assertTrue(verify_password("very-strong-password", encoded))
        self.assertFalse(verify_password("wrong-password", encoded))

    def test_bootstrap_credentials_remain_compatible_with_env_settings(self):
        identity = bootstrap_admin_email()
        self.assertTrue(verify_bootstrap_admin_credentials(identity, settings.admin_password))
        self.assertFalse(verify_bootstrap_admin_credentials(identity, settings.admin_password + "x"))
        self.assertFalse(verify_bootstrap_admin_credentials(identity + "x", settings.admin_password))


if __name__ == "__main__":
    unittest.main()
