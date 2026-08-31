from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import datetime, timedelta, timezone
from hashlib import scrypt
from hmac import compare_digest
from secrets import token_bytes

from jose import JWTError, jwt

from app.config import settings

ALGORITHM = "HS256"
SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 32


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


def create_admin_token(email: str) -> str:
    return _encode(email, "admin", settings.admin_token_minutes)


def decode_admin_token(token: str) -> str | None:
    return _decode(token, "admin")


def hash_password(password: str) -> str:
    salt = token_bytes(16)
    digest = scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=SCRYPT_DKLEN,
    )
    salt_text = urlsafe_b64encode(salt).decode("ascii")
    digest_text = urlsafe_b64encode(digest).decode("ascii")
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${salt_text}${digest_text}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, n, r, p, salt_text, digest_text = encoded.split("$", 5)
        if algorithm != "scrypt":
            return False
        expected = urlsafe_b64decode(digest_text.encode("ascii"))
        actual = scrypt(
            password.encode("utf-8"),
            salt=urlsafe_b64decode(salt_text.encode("ascii")),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected),
        )
        return compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def bootstrap_admin_email() -> str:
    return (settings.admin_email.strip() or settings.admin_username.strip()).lower()


def verify_bootstrap_admin_credentials(email: str, password: str) -> bool:
    return compare_digest(email.strip().lower(), bootstrap_admin_email()) and compare_digest(password, settings.admin_password)
