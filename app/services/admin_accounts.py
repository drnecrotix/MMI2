from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AdminUser
from app.security import hash_password, verify_bootstrap_admin_credentials, verify_password

ADMIN_ROLES = {"owner", "admin", "moderator"}
ASSIGNABLE_ROLES = {"admin", "moderator"}


def normalize_email(value: str) -> str:
    return value.strip().lower()


def validate_account_email(value: str) -> str:
    email = normalize_email(value)
    if len(email) < 5 or "@" not in email or "." not in email.rsplit("@", 1)[-1]:
        raise HTTPException(status_code=400, detail="Въведи валиден имейл адрес.")
    return email


def authenticate_admin(db: Session, email: str, password: str) -> AdminUser | None:
    email = normalize_email(email)
    account = db.scalar(select(AdminUser).where(AdminUser.email == email))

    if account is None:
        count = db.scalar(select(func.count(AdminUser.id))) or 0
        if count == 0 and verify_bootstrap_admin_credentials(email, password):
            account = AdminUser(
                email=email,
                password_hash=hash_password(password),
                role="owner",
                is_active=True,
            )
            db.add(account)
            db.commit()
            db.refresh(account)
        else:
            return None

    if not account.is_active or not verify_password(password, account.password_hash):
        return None

    account.last_login_at = datetime.utcnow()
    db.commit()
    return account


def require_owner(account: AdminUser) -> None:
    if account.role != "owner":
        raise HTTPException(status_code=403, detail="Само owner може да управлява администраторски профили.")


def require_admin_or_owner(account: AdminUser) -> None:
    if account.role not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="Нямаш права за тази административна операция.")


def validate_assignable_role(role: str) -> str:
    normalized = role.strip().lower()
    if normalized not in ASSIGNABLE_ROLES:
        raise HTTPException(status_code=400, detail="Нов акаунт може да бъде само admin или moderator.")
    return normalized
