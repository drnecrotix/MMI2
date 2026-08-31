from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AdminUser
from app.security import hash_password, verify_bootstrap_admin_credentials, verify_password

ADMIN_ROLES = {"owner", "admin"}


def normalize_username(value: str) -> str:
    return value.strip().lower()


def authenticate_admin(db: Session, username: str, password: str) -> AdminUser | None:
    username = normalize_username(username)
    account = db.scalar(select(AdminUser).where(AdminUser.username == username))

    if account is None:
        count = db.scalar(select(func.count(AdminUser.id))) or 0
        if count == 0 and verify_bootstrap_admin_credentials(username, password):
            account = AdminUser(
                username=username,
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


def validate_role(role: str) -> str:
    normalized = role.strip().lower()
    if normalized not in ADMIN_ROLES:
        raise HTTPException(status_code=400, detail="Ролята трябва да е owner или admin.")
    return normalized


def active_owner_count(db: Session, *, excluding_id: int | None = None) -> int:
    statement = select(func.count(AdminUser.id)).where(AdminUser.role == "owner", AdminUser.is_active.is_(True))
    if excluding_id is not None:
        statement = statement.where(AdminUser.id != excluding_id)
    return int(db.scalar(statement) or 0)
