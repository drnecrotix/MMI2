#!/usr/bin/env python3
"""Offline recovery utility for MMI2 self-updates.

Stop/restart the Python application before using this script. It intentionally
uses only the Python standard library so it can still run if application
imports are broken after an update.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from urllib.parse import unquote, urlparse


PROJECT_ROOT = Path(__file__).resolve().parent
UPDATE_DIR = PROJECT_ROOT / ".update"
BACKUP_DIR = UPDATE_DIR / "backups"
RESTART_FILE = UPDATE_DIR / "restart.required"
IN_PROGRESS_FILE = UPDATE_DIR / "update.in_progress"


def read_json(path: Path) -> dict | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def env_value(key: str) -> str | None:
    if os.environ.get(key):
        return os.environ[key]
    env_file = PROJECT_ROOT / ".env"
    if not env_file.is_file():
        return None
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        if name.strip() != key:
            continue
        value = value.strip()
        if value.startswith(('"', "'")):
            try:
                parsed = ast.literal_eval(value)
                return str(parsed)
            except (ValueError, SyntaxError):
                return value.strip('"\'')
        return value
    return None


def pick_backup(explicit: str | None) -> str:
    if explicit:
        return explicit
    for marker_path in (RESTART_FILE, IN_PROGRESS_FILE):
        marker = read_json(marker_path)
        if marker and marker.get("backup_id"):
            return str(marker["backup_id"])
    if not BACKUP_DIR.is_dir():
        raise RuntimeError("Няма налични .update/backups директории.")
    candidates = sorted((path for path in BACKUP_DIR.iterdir() if path.is_dir()), reverse=True)
    if not candidates:
        raise RuntimeError("Няма наличен update backup.")
    return candidates[0].name


def restore_files(backup_dir: Path, manifest: dict) -> None:
    files_root = backup_dir / "files"
    if not files_root.is_dir():
        raise RuntimeError("Backup-ът няма file snapshot.")

    for name in manifest.get("managed_dirs") or []:
        destination = PROJECT_ROOT / str(name)
        if destination.exists():
            shutil.rmtree(destination)
        source = files_root / str(name)
        if source.exists():
            shutil.copytree(source, destination)

    for name in manifest.get("managed_files") or []:
        destination = PROJECT_ROOT / str(name)
        if destination.exists() and destination.is_file():
            destination.unlink()
        source = files_root / str(name)
        if source.is_file():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)


def postgres_environment(database_url: str) -> tuple[dict[str, str], str]:
    normalized = database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    parsed = urlparse(normalized)
    database = unquote(parsed.path.lstrip("/"))
    if not database:
        raise RuntimeError("DATABASE_URL няма PostgreSQL database име.")
    env = os.environ.copy()
    if parsed.hostname:
        env["PGHOST"] = parsed.hostname
    if parsed.port:
        env["PGPORT"] = str(parsed.port)
    if parsed.username:
        env["PGUSER"] = unquote(parsed.username)
    if parsed.password:
        env["PGPASSWORD"] = unquote(parsed.password)
    env["PGDATABASE"] = database
    return env, database


def restore_database(backup_dir: Path, metadata: dict) -> None:
    kind = metadata.get("kind")
    backup = backup_dir / str(metadata.get("backup") or "")
    if not backup.is_file():
        raise RuntimeError("Database backup файлът липсва.")

    if kind == "sqlite":
        destination = Path(str(metadata.get("source") or ""))
        if not destination.is_absolute():
            destination = (PROJECT_ROOT / destination).resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(backup, destination)
        return

    if kind == "postgresql":
        restore_tool = shutil.which("pg_restore")
        if not restore_tool:
            raise RuntimeError("PostgreSQL rollback изисква pg_restore в PATH.")
        database_url = env_value("DATABASE_URL")
        if not database_url:
            raise RuntimeError("DATABASE_URL не е наличен за PostgreSQL rollback.")
        env, database = postgres_environment(database_url)
        result = subprocess.run(
            [
                restore_tool,
                "--clean",
                "--if-exists",
                "--no-owner",
                "--no-privileges",
                "--dbname",
                database,
                str(backup),
            ],
            cwd=PROJECT_ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError("pg_restore не завърши успешно:\n" + (result.stdout or "")[-3000:])
        return

    raise RuntimeError(f"Неподдържан database backup type: {kind}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Restore an MMI2 self-update backup.")
    parser.add_argument("backup_id", nargs="?", help="Backup directory id. Defaults to update marker/latest backup.")
    parser.add_argument("--yes", action="store_true", help="Required confirmation flag.")
    args = parser.parse_args()

    if not args.yes:
        print("Rollback не е изпълнен. Спри Python приложението и повтори командата с --yes.")
        return 2

    try:
        backup_id = pick_backup(args.backup_id)
        backup_dir = BACKUP_DIR / backup_id
        manifest = read_json(backup_dir / "manifest.json")
        if not manifest:
            raise RuntimeError(f"Невалиден backup: {backup_id}")
        restore_files(backup_dir, manifest)
        restore_database(backup_dir, manifest.get("database") or {})
        RESTART_FILE.unlink(missing_ok=True)
        IN_PROGRESS_FILE.unlink(missing_ok=True)
        print(f"Rollback към {backup_id} е завършен. Рестартирай Python приложението.")
        return 0
    except Exception as exc:
        print(f"Rollback error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
