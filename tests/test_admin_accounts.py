import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import settings
from app.db import Base
from app.main import create_admin_account, update_admin_account
from app.schemas import AdminAccountCreate, AdminAccountUpdate
from app.security import bootstrap_admin_email, verify_password
from app.services.admin_accounts import authenticate_admin, require_admin_or_owner


class AdminAccountTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)

    def test_first_bootstrap_login_creates_the_only_owner(self):
        with Session(self.engine) as db:
            owner = authenticate_admin(db, bootstrap_admin_email(), settings.admin_password)
            self.assertIsNotNone(owner)
            self.assertEqual(owner.role, "owner")
            self.assertTrue(owner.is_active)
            self.assertNotEqual(owner.password_hash, settings.admin_password)
            self.assertTrue(verify_password(settings.admin_password, owner.password_hash))

            again = authenticate_admin(db, bootstrap_admin_email(), settings.admin_password)
            self.assertEqual(again.id, owner.id)

    def test_owner_can_create_moderator_but_not_second_owner(self):
        with Session(self.engine) as db:
            owner = authenticate_admin(db, bootstrap_admin_email(), settings.admin_password)
            result = create_admin_account(
                payload=AdminAccountCreate(
                    email="moderator@example.com",
                    password="moderator-password",
                    role="moderator",
                ),
                account=owner,
                db=db,
            )
            self.assertEqual(result["account"]["role"], "moderator")

            with self.assertRaises(HTTPException) as ctx:
                create_admin_account(
                    payload=AdminAccountCreate(
                        email="second-owner@example.com",
                        password="second-owner-password",
                        role="owner",
                    ),
                    account=owner,
                    db=db,
                )
            self.assertEqual(ctx.exception.status_code, 400)

    def test_owner_cannot_be_demoted_or_disabled(self):
        with Session(self.engine) as db:
            owner = authenticate_admin(db, bootstrap_admin_email(), settings.admin_password)
            with self.assertRaises(HTTPException) as ctx:
                update_admin_account(
                    account_id=owner.id,
                    payload=AdminAccountUpdate(is_active=False),
                    actor=owner,
                    db=db,
                )
            self.assertEqual(ctx.exception.status_code, 400)

    def test_moderator_is_rejected_from_admin_only_operations(self):
        with Session(self.engine) as db:
            owner = authenticate_admin(db, bootstrap_admin_email(), settings.admin_password)
            result = create_admin_account(
                payload=AdminAccountCreate(
                    email="mod@example.com",
                    password="moderator-password",
                    role="moderator",
                ),
                account=owner,
                db=db,
            )
            moderator = db.get(type(owner), result["account"]["id"])
            with self.assertRaises(HTTPException) as ctx:
                require_admin_or_owner(moderator)
            self.assertEqual(ctx.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
