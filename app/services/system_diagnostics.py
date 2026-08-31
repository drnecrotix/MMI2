from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import platform
import shutil
import sys

from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.models import AdminUser, Employee, ImportHistory
from app.services.self_update import get_update_runtime_state
from app.version import APP_VERSION, CURRENT_PR
from install.hosting import detect_hosting_runtime


PROJECT_ROOT = Path(__file__).resolve().parents[2]
UPDATE_DIR = PROJECT_ROOT / ".update"
INSTALL_LOCK = PROJECT_ROOT / "install" / "install.lock"
MIN_WARNING_FREE_BYTES = 512 * 1024 * 1024
MIN_ERROR_FREE_BYTES = 128 * 1024 * 1024


def _human_bytes(value: int) -> str:
    units = ("B", "KB", "MB", "GB", "TB")
    amount = float(max(0, value))
    for unit in units:
        if amount < 1024 or unit == units[-1]:
            return f"{amount:.1f} {unit}" if unit != "B" else f"{int(amount)} B"
        amount /= 1024
    return f"{value} B"


def _check(check_id: str, label: str, status: str, detail: str) -> dict:
    return {"id": check_id, "label": label, "status": status, "detail": detail}


def _migration_state(db: Session) -> tuple[str | None, str | None, bool]:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "migrations"))
    head = ScriptDirectory.from_config(config).get_current_head()
    current = MigrationContext.configure(db.connection()).get_current_revision()
    return current, head, bool(current and head and current == head)


def _backup_state(db: Session) -> dict:
    engine = db.get_bind()
    driver = engine.url.get_backend_name()

    if driver == "sqlite":
        database = engine.url.database
        if not database or database == ":memory:":
            return {"ready": False, "mode": "sqlite", "detail": "In-memory SQLite няма production backup файл."}
        path = Path(database).expanduser()
        if not path.is_absolute():
            path = (PROJECT_ROOT / path).resolve()
        parent = path.parent
        ready = path.exists() and os.access(path, os.R_OK) and os.access(parent, os.W_OK)
        return {
            "ready": ready,
            "mode": "sqlite",
            "detail": "SQLite backup API е готов." if ready else "SQLite файлът/директорията не е готов за backup.",
        }

    if driver == "postgresql":
        dump = shutil.which("pg_dump")
        restore = shutil.which("pg_restore")
        ready = bool(dump and restore)
        return {
            "ready": ready,
            "mode": "postgresql",
            "detail": "pg_dump и pg_restore са налични." if ready else "Липсва pg_dump или pg_restore за автоматичен rollback.",
        }

    return {"ready": False, "mode": driver, "detail": f"Backup readiness за {driver} не е дефиниран."}


def _safe_update_state() -> dict:
    raw = get_update_runtime_state()
    return {
        key: raw.get(key)
        for key in (
            "status",
            "target_pr",
            "target_version",
            "running_pr",
            "running_version",
            "backup_id",
            "updated_at",
            "completed_at",
        )
        if raw.get(key) is not None
    }


def collect_system_diagnostics(db: Session) -> dict:
    checks: list[dict] = []
    hosting = detect_hosting_runtime().as_dict()

    db_connected = False
    db_error: str | None = None
    try:
        db.execute(text("SELECT 1"))
        db_connected = True
        checks.append(_check("database", "Database connection", "ok", "Връзката с базата е успешна."))
    except Exception as exc:  # pragma: no cover - depends on deployment failure
        db_error = exc.__class__.__name__
        checks.append(_check("database", "Database connection", "error", f"Database connection failed: {db_error}."))

    migration_current: str | None = None
    migration_head: str | None = None
    migrations_current = False
    if db_connected:
        try:
            migration_current, migration_head, migrations_current = _migration_state(db)
            if migrations_current:
                checks.append(_check("migrations", "Alembic schema", "ok", f"Schema е на {migration_current}."))
            else:
                checks.append(
                    _check(
                        "migrations",
                        "Alembic schema",
                        "error",
                        f"Current={migration_current or 'none'}, head={migration_head or 'none'}. Изпълни alembic upgrade head.",
                    )
                )
        except Exception as exc:  # pragma: no cover - deployment-specific malformed config
            checks.append(_check("migrations", "Alembic schema", "error", f"Migration status failed: {exc.__class__.__name__}."))

    python_ok = sys.version_info >= (3, 11)
    checks.append(
        _check(
            "python",
            "Python runtime",
            "ok" if python_ok else "error",
            f"Python {platform.python_version()} ({platform.python_implementation()}).",
        )
    )

    disk = shutil.disk_usage(PROJECT_ROOT)
    if disk.free < MIN_ERROR_FREE_BYTES:
        disk_status = "error"
    elif disk.free < MIN_WARNING_FREE_BYTES:
        disk_status = "warning"
    else:
        disk_status = "ok"
    checks.append(_check("disk", "Свободно дисково място", disk_status, f"Свободни: {_human_bytes(disk.free)}."))

    project_writable = os.access(PROJECT_ROOT, os.W_OK)
    update_write_target = UPDATE_DIR if UPDATE_DIR.exists() else PROJECT_ROOT
    update_writable = os.access(update_write_target, os.W_OK)
    checks.append(
        _check(
            "filesystem",
            "Filesystem permissions",
            "ok" if project_writable and update_writable else "warning",
            "Project и update директориите са writable."
            if project_writable and update_writable
            else "Липсват write permissions за project или .update; self-update може да е блокиран.",
        )
    )

    backup = _backup_state(db) if db_connected else {"ready": False, "mode": "unknown", "detail": "Database не е достъпна."}
    checks.append(
        _check(
            "backup",
            "Update backup readiness",
            "ok" if backup["ready"] else "warning",
            backup["detail"],
        )
    )

    lock_present = INSTALL_LOCK.is_file()
    checks.append(
        _check(
            "installer_lock",
            "Installer lock",
            "ok" if lock_present else "warning",
            "Web installer е заключен." if lock_present else "install.lock липсва; съществуваща DB инсталация може да е adopted deployment.",
        )
    )

    update_state = _safe_update_state()
    update_status = update_state.get("status", "ready")
    if update_status == "interrupted_or_in_progress":
        checks.append(_check("update_state", "Self-update state", "error", "Има прекъснат update. Използвай rollback_update.py."))
    elif update_status == "restart_required":
        checks.append(_check("update_state", "Self-update state", "warning", "Update е приложен и очаква restart."))
    else:
        checks.append(_check("update_state", "Self-update state", "ok", "Няма прекъснат update."))

    employee_count = db.scalar(select(func.count(Employee.id))) if db_connected else None
    admin_count = db.scalar(select(func.count(AdminUser.id))) if db_connected else None
    latest_import = (
        db.scalar(select(ImportHistory).order_by(ImportHistory.imported_at.desc(), ImportHistory.id.desc()).limit(1))
        if db_connected
        else None
    )

    if any(item["status"] == "error" for item in checks):
        overall = "error"
    elif any(item["status"] == "warning" for item in checks):
        overall = "warning"
    else:
        overall = "healthy"

    return {
        "status": overall,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "version": {"app": APP_VERSION, "current_pr": CURRENT_PR},
        "hosting": hosting,
        "python": {
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
        },
        "database": {
            "driver": db.get_bind().url.get_backend_name(),
            "connected": db_connected,
            "error_type": db_error,
            "migration_current": migration_current,
            "migration_head": migration_head,
            "schema_current": migrations_current,
            "employees": employee_count,
            "admin_accounts": admin_count,
            "latest_import": (
                {
                    "id": latest_import.id,
                    "period": f"{latest_import.month:02d}.{latest_import.year}",
                    "imported_at": latest_import.imported_at.isoformat(),
                }
                if latest_import
                else None
            ),
        },
        "storage": {
            "free_bytes": disk.free,
            "free_human": _human_bytes(disk.free),
            "project_writable": project_writable,
            "update_writable": update_writable,
        },
        "backup": backup,
        "installer": {"lock_present": lock_present},
        "update": update_state,
        "checks": checks,
    }
