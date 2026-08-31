from datetime import datetime, timedelta, timezone
from hmac import compare_digest

from jose import JWTError, jwt

from app.config import settings

ALGORITHM = "HS256"


def _encode(subject: str, token_type: str, minutes: int) -> str:
    expires = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    payload = {"sub": subject, "type": token_type, "exp": expires}
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def _decode(token: str, expected_type: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
        if payload.get("type") != expected_type:
            return None
        return payload.get("sub")
    except JWTError:
        return None


def create_access_token(work_number: str) -> str:
    return _encode(work_number, "employee", settings.access_token_minutes)


def decode_access_token(token: str) -> str | None:
    return _decode(token, "employee")


def create_admin_token(username: str) -> str:
    return _encode(username, "admin", settings.admin_token_minutes)


def decode_admin_token(token: str) -> str | None:
    return _decode(token, "admin")


def verify_admin_credentials(username: str, password: str) -> bool:
    return compare_digest(username, settings.admin_username) and compare_digest(password, settings.admin_password)
