from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path

from app.version import APP_VERSION, CURRENT_PR


PROJECT_ROOT = Path(__file__).resolve().parent.parent
UPDATE_DIR = PROJECT_ROOT / ".update"
IN_PROGRESS_FILE = UPDATE_DIR / "update.in_progress"
RESTART_FILE = UPDATE_DIR / "restart.required"
HISTORY_DIR = UPDATE_DIR / "history"


def _read_marker(path: Path) -> dict | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _handle_update_startup() -> None:
    # Alembic/smoke-test subprocesses are intentionally launched while the
    # updater owns the in-progress marker.
    if os.environ.get("MMI2_UPDATE_WORKER") == "1":
        return

    if IN_PROGRESS_FILE.exists():
        marker = _read_marker(IN_PROGRESS_FILE) or {}
        backup_id = marker.get("backup_id") or "unknown"
        raise RuntimeError(
            "MMI2 detected an interrupted self-update. "
            f"Stop the app and run: python rollback_update.py {backup_id} --yes"
        )

    marker = _read_marker(RESTART_FILE)
    if not marker:
        return

    target_pr = int(marker.get("target_pr") or 0)
    if not target_pr or CURRENT_PR < target_pr:
        return

    completed = {
        **marker,
        "status": "completed",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "running_version": APP_VERSION,
        "running_pr": CURRENT_PR,
    }
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    history_name = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-pr{target_pr}.json"
    _write_json_atomic(HISTORY_DIR / history_name, completed)
    RESTART_FILE.unlink(missing_ok=True)


_handle_update_startup()
