from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
from secrets import token_urlsafe
from threading import Lock
from typing import Literal

from alembic import command
from alembic.config import Config
from pydantic import BaseModel, Field
from sqlalchemy import URL, create_engine, func, inspect, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import settings
from app.models import AdminUser
from app.security import hash_password


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INSTALL_DIR = Path(__file__).resolve().parent
ENV_FILE = PROJECT_ROOT / ".env"
LOCK_FILE = INSTALL_DIR / "install.lock"
RESTART_FILE = INSTALL_DIR / "restart.required"
INSTALL_MUTEX = Lock()


class InstallerError(RuntimeError):
    pass


class DatabaseSetup(BaseModel):
    driver: Literal["sqlite", "postgresql"] = "sqlite"
    sqlite_path: str = "./mmi2.db"
    host: str = "localhost"
    port: int = Field(default=5432, ge=1, le=65535)
    database: str = "mmi2"
    username: str = ""
    password: str = ""
    sslmode: Literal["prefer", "require", "disable"] = "prefer"


class InstallRequest(BaseModel):
    database: DatabaseSetup
    owner_email: str
    owner_password: str
    owner_password_confirm: str
    app_name: str = "MMI2 Schedule System"


@dataclass(frozen=True)
class InstallationState:
    installed: bool
    restart_required: bool
    adopted_existing: bool = False


def _digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _legacy_database_has_admin() -> bool:
    engine = None
    try:
        connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
        engine = create_engine(settings.database_url, connect_args=connect_args)
        if not inspect(engine).has_table("admin_users"):
            return False
        with Session(engine) as db:
            return int(db.scalar(select(func.count(AdminUser.id))) or 0) > 0
    except Exception:
        return False
    finally:
        if engine is not None:
            engine.dispose()


def _adopt_existing_installation() -> bool:
    if not _legacy_database_has_admin():
        return False
    try:
        _write_json_atomic(
            LOCK_FILE,
            {
                "installed_at": datetime.now(timezone.utc).isoformat(),
                "mode": "adopted-existing",
            },
        )
    except OSError:
        # A read-only deployment can still run if a configured database already
        # contains admin accounts. The lock is an optimization/security marker,
        # not the only source of truth for legacy adoption.
        pass
    return True


def _runtime_matches_restart_marker() -> bool:
    if not RESTART_FILE.exists():
        return True
    try:
        marker = json.loads(RESTART_FILE.read_text(encoding="utf-8"))
        matches = (
            marker.get("database_url_sha256") == _digest(settings.database_url)
            and marker.get("jwt_secret_sha256") == _digest(settings.jwt_secret)
        )
        if matches:
            RESTART_FILE.unlink(missing_ok=True)
        return matches
    except (OSError, json.JSONDecodeError):
        return False


def get_installation_state() -> InstallationState:
    installed = LOCK_FILE.exists()
    adopted = False
    if not installed:
        adopted = _adopt_existing_installation()
        installed = adopted
    return InstallationState(
        installed=installed,
        restart_required=installed and not _runtime_matches_restart_marker(),
        adopted_existing=adopted,
    )


def system_checks() -> list[dict]:
    checks = [
        {
            "name": "Python 3.11+",
            "ok": os.sys.version_info >= (3, 11),
            "detail": os.sys.version.split()[0],
        },
        {
            "name": "Alembic configuration",
            "ok": (PROJECT_ROOT / "alembic.ini").is_file() and (PROJECT_ROOT / "migrations").is_dir(),
            "detail": "alembic.ini + migrations/",
        },
        {
            "name": "Запис на .env",
            "ok": os.access(ENV_FILE if ENV_FILE.exists() else PROJECT_ROOT, os.W_OK),
            "detail": str(ENV_FILE),
        },
        {
            "name": "Запис на install lock",
            "ok": os.access(INSTALL_DIR, os.W_OK),
            "detail": str(INSTALL_DIR),
        },
    ]
    return checks


def _validate_email(value: str) -> str:
    email = value.strip().lower()
    if len(email) < 5 or "@" not in email or "." not in email.rsplit("@", 1)[-1]:
        raise InstallerError("Въведи валиден имейл за owner акаунта.")
    if len(email) > 255:
        raise InstallerError("Owner имейлът е твърде дълъг.")
    return email


def _validate_password(password: str, confirmation: str) -> None:
    if password != confirmation:
        raise InstallerError("Двете owner пароли не съвпадат.")
    if len(password) < 12:
        raise InstallerError("Owner паролата трябва да е поне 12 символа.")


def build_database_url(setup: DatabaseSetup) -> URL:
    if setup.driver == "sqlite":
        raw_path = setup.sqlite_path.strip() or "./mmi2.db"
        path = Path(raw_path).expanduser()
        if not path.is_absolute():
            path = (PROJECT_ROOT / path).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        return URL.create("sqlite", database=str(path))

    host = setup.host.strip()
    database = setup.database.strip()
    username = setup.username.strip()
    if not host or not database or not username:
        raise InstallerError("За PostgreSQL са задължителни host, database и username.")
    return URL.create(
        "postgresql+psycopg",
        username=username,
        password=setup.password,
        host=host,
        port=setup.port,
        database=database,
        query={"sslmode": setup.sslmode},
    )


def test_database_connection(setup: DatabaseSetup) -> dict:
    url = build_database_url(setup)
    engine = None
    try:
        connect_args = {"check_same_thread": False} if setup.driver == "sqlite" else {}
        engine = create_engine(url, connect_args=connect_args, pool_pre_ping=True)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {
            "ok": True,
            "driver": setup.driver,
            "database": url.render_as_string(hide_password=True),
        }
    except (SQLAlchemyError, OSError) as exc:
        raise InstallerError(f"Неуспешна връзка с базата: {exc.__class__.__name__}.") from exc
    finally:
        if engine is not None:
            engine.dispose()


def _run_migrations(database_url: str) -> None:
    previous = settings.database_url
    try:
        settings.database_url = database_url
        config = Config(str(PROJECT_ROOT / "alembic.ini"))
        config.set_main_option("script_location", str(PROJECT_ROOT / "migrations"))
        command.upgrade(config, "head")
    except Exception as exc:
        raise InstallerError(f"Alembic migration не можа да завърши: {exc.__class__.__name__}.") from exc
    finally:
        settings.database_url = previous


def _dotenv_quote(value: str) -> str:
    safe = value.replace("\\", "\\\\").replace('"', '\\"').replace("\r", "").replace("\n", "\\n")
    return f'"{safe}"'


def _write_environment(values: dict[str, str], remove_keys: set[str]) -> None:
    existing_lines = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
    managed = set(values) | remove_keys
    output: list[str] = []
    seen: set[str] = set()

    for line in existing_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            output.append(line)
            continue
        key = line.split("=", 1)[0].strip()
        if key not in managed:
            output.append(line)
            continue
        if key in values and key not in seen:
            output.append(f"{key}={_dotenv_quote(values[key])}")
            seen.add(key)

    for key, value in values.items():
        if key not in seen:
            output.append(f"{key}={_dotenv_quote(value)}")

    temporary = ENV_FILE.with_suffix(".env.tmp")
    temporary.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")
    temporary.replace(ENV_FILE)


def complete_installation(payload: InstallRequest) -> dict:
    with INSTALL_MUTEX:
        state = get_installation_state()
        if state.installed:
            raise InstallerError("Проектът вече е инсталиран. Installer-ът е заключен.")

        failed_checks = [item["name"] for item in system_checks() if not item["ok"]]
        if failed_checks:
            raise InstallerError("Не са изпълнени системните изисквания: " + ", ".join(failed_checks))

        owner_email = _validate_email(payload.owner_email)
        _validate_password(payload.owner_password, payload.owner_password_confirm)
        app_name = payload.app_name.strip() or "MMI2 Schedule System"
        if len(app_name) > 120:
            raise InstallerError("Името на приложението е твърде дълго.")

        database_url = build_database_url(payload.database).render_as_string(hide_password=False)
        test_database_connection(payload.database)
        _run_migrations(database_url)

        connect_args = {"check_same_thread": False} if payload.database.driver == "sqlite" else {}
        engine = create_engine(database_url, connect_args=connect_args, pool_pre_ping=True)
        jwt_secret = token_urlsafe(64)
        try:
            with Session(engine) as db:
                existing_accounts = int(db.scalar(select(func.count(AdminUser.id))) or 0)
                if existing_accounts:
                    raise InstallerError(
                        "Избраната база вече съдържа административни акаунти. "
                        "Installer-ът няма да ги презапише."
                    )

                owner = AdminUser(
                    email=owner_email,
                    password_hash=hash_password(payload.owner_password),
                    role="owner",
                    is_active=True,
                )
                db.add(owner)
                db.flush()

                _write_environment(
                    {
                        "APP_NAME": app_name,
                        "DATABASE_URL": database_url,
                        "JWT_SECRET": jwt_secret,
                        "ACCESS_TOKEN_MINUTES": "43200",
                        "ADMIN_BOOTSTRAP_ENABLED": "false",
                        "ADMIN_EMAIL": owner_email,
                        "ADMIN_TOKEN_MINUTES": "480",
                    },
                    remove_keys={"ADMIN_PASSWORD", "ADMIN_USERNAME"},
                )
                db.commit()
        finally:
            engine.dispose()

        lock_payload = {
            "installed_at": datetime.now(timezone.utc).isoformat(),
            "database_driver": payload.database.driver,
            "owner_email": owner_email,
            "installer_version": 1,
        }
        _write_json_atomic(LOCK_FILE, lock_payload)
        _write_json_atomic(
            RESTART_FILE,
            {
                "database_url_sha256": _digest(database_url),
                "jwt_secret_sha256": _digest(jwt_secret),
            },
        )

        return {
            "status": "installed",
            "owner_email": owner_email,
            "database_driver": payload.database.driver,
            "restart_required": True,
            "message": "Инсталацията е завършена. Рестартирай Python/ASGI приложението, за да зареди новата конфигурация.",
        }
