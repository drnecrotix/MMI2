from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sqlite3
import stat
import subprocess
import sys
import tempfile
from threading import Lock
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zipfile import BadZipFile, ZipFile

from sqlalchemy.engine import make_url

from app.config import settings
from app.db import engine as runtime_engine
from app.version import APP_VERSION, CURRENT_PR, GITHUB_REPOSITORY


PROJECT_ROOT = Path(__file__).resolve().parents[2]
UPDATE_DIR = PROJECT_ROOT / ".update"
BACKUP_DIR = UPDATE_DIR / "backups"
HISTORY_DIR = UPDATE_DIR / "history"
IN_PROGRESS_FILE = UPDATE_DIR / "update.in_progress"
RESTART_FILE = UPDATE_DIR / "restart.required"
UPDATE_MUTEX = Lock()
MAX_ARCHIVE_BYTES = 50 * 1024 * 1024
MAX_REQUIREMENTS_BYTES = 1024 * 1024

MANAGED_DIRS = (
    "app",
    "install",
    "migrations",
    "docs",
    "tests",
    ".github",
)
MANAGED_FILES = (
    ".env.example",
    ".gitignore",
    "alembic.ini",
    "docker-compose.yml",
    "Dockerfile",
    "README.md",
    "requirements.txt",
    "run.py",
    "passenger_wsgi.py",
    "rollback_update.py",
    "update_mmi2.py",
)
PRESERVED_RUNTIME_FILES = (
    "install/install.lock",
    "install/restart.required",
)


class SelfUpdateError(RuntimeError):
    pass


@dataclass(frozen=True)
class UpdateTarget:
    pr_number: int
    title: str
    html_url: str
    merge_commit_sha: str
    merged_at: str

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class UpdateCapability:
    target: UpdateTarget
    automatic_apply: bool
    requirements_changed: bool
    backup_mode: str
    reasons: list[str]

    def as_dict(self) -> dict:
        data = asdict(self)
        data["target"] = self.target.as_dict()
        data["current_version"] = APP_VERSION
        data["current_pr"] = CURRENT_PR
        return data


def _github_headers() -> dict[str, str]:
    return {
        "Accept": "application/vnd.github+json",
        "User-Agent": "MMI2-Self-Updater",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _read_url(url: str, max_bytes: int, *, github_headers: bool = False) -> bytes:
    request = Request(url, headers=_github_headers() if github_headers else {"User-Agent": "MMI2-Self-Updater"})
    try:
        with urlopen(request, timeout=15) as response:  # noqa: S310 - callers use fixed GitHub hosts
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > max_bytes:
                raise SelfUpdateError("GitHub update файлът е по-голям от разрешения лимит.")
            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = response.read(min(1024 * 1024, max_bytes + 1 - total))
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise SelfUpdateError("GitHub update файлът е по-голям от разрешения лимит.")
                chunks.append(chunk)
            return b"".join(chunks)
    except SelfUpdateError:
        raise
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise SelfUpdateError("GitHub update ресурсът временно не е достъпен.") from exc


def resolve_update_target(pr_number: int) -> UpdateTarget:
    if pr_number <= CURRENT_PR:
        raise SelfUpdateError("Избраният PR не е по-нов от текущия build.")
    if pr_number > 1_000_000:
        raise SelfUpdateError("Невалиден PR номер.")

    url = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/pulls/{pr_number}"
    try:
        row = json.loads(_read_url(url, 2 * 1024 * 1024, github_headers=True).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SelfUpdateError("GitHub върна невалидни metadata за update PR-а.") from exc

    if not isinstance(row, dict):
        raise SelfUpdateError("GitHub върна неочакван отговор за update PR-а.")
    if not row.get("merged_at"):
        raise SelfUpdateError("Update може да се инсталира само от merge-нат PR.")
    if (row.get("base") or {}).get("ref") != "main":
        raise SelfUpdateError("Update PR-ът трябва да е merge-нат към main.")

    merge_sha = str(row.get("merge_commit_sha") or "").lower()
    if not re.fullmatch(r"[0-9a-f]{40}", merge_sha):
        raise SelfUpdateError("GitHub не предостави валиден merge commit за update-а.")

    return UpdateTarget(
        pr_number=int(row.get("number") or pr_number),
        title=str(row.get("title") or ""),
        html_url=str(row.get("html_url") or ""),
        merge_commit_sha=merge_sha,
        merged_at=str(row.get("merged_at") or ""),
    )


def _target_requirements(merge_sha: str) -> bytes:
    url = f"https://raw.githubusercontent.com/{GITHUB_REPOSITORY}/{merge_sha}/requirements.txt"
    return _read_url(url, MAX_REQUIREMENTS_BYTES)


def _database_backup_capability() -> tuple[bool, str, str | None]:
    try:
        url = make_url(settings.database_url)
    except Exception:
        return False, "unknown", "DATABASE_URL не може да бъде анализиран."

    if url.drivername.startswith("sqlite"):
        if not url.database or url.database == ":memory:":
            return False, "sqlite", "In-memory SQLite не поддържа безопасен self-update backup."
        return True, "sqlite", None

    if url.drivername.startswith("postgresql"):
        if not shutil.which("pg_dump") or not shutil.which("pg_restore"):
            return (
                False,
                "postgresql",
                "За автоматичен PostgreSQL update са необходими pg_dump и pg_restore на сървъра.",
            )
        return True, "postgresql", None

    return False, url.drivername, f"Database driver {url.drivername} още не се поддържа от self-updater-а."


def preflight_update(pr_number: int) -> dict:
    target = resolve_update_target(pr_number)
    reasons: list[str] = []

    current_requirements = (PROJECT_ROOT / "requirements.txt").read_bytes()
    target_requirements = _target_requirements(target.merge_commit_sha)
    requirements_changed = current_requirements != target_requirements
    if requirements_changed:
        reasons.append(
            "requirements.txt е променен. Обнови Python dependencies ръчно през virtualenv/SSH преди code update."
        )

    backup_ok, backup_mode, backup_reason = _database_backup_capability()
    if not backup_ok and backup_reason:
        reasons.append(backup_reason)

    update_target = UPDATE_DIR if UPDATE_DIR.exists() else UPDATE_DIR.parent
    if not os.access(update_target, os.W_OK):
        reasons.append("Проектът няма права за запис на .update backup/staging директорията.")

    return UpdateCapability(
        target=target,
        automatic_apply=not reasons,
        requirements_changed=requirements_changed,
        backup_mode=backup_mode,
        reasons=reasons,
    ).as_dict()


def _safe_extract_archive(archive_path: Path, destination: Path) -> Path:
    try:
        with ZipFile(archive_path) as archive:
            infos = archive.infolist()
            if not infos:
                raise SelfUpdateError("Изтегленият update архив е празен.")

            roots: set[str] = set()
            destination_resolved = destination.resolve()
            for info in infos:
                pure = PurePosixPath(info.filename)
                if pure.is_absolute() or ".." in pure.parts:
                    raise SelfUpdateError("Update архивът съдържа опасен path traversal запис.")
                if not pure.parts:
                    continue
                roots.add(pure.parts[0])
                unix_mode = info.external_attr >> 16
                if unix_mode and stat.S_ISLNK(unix_mode):
                    raise SelfUpdateError("Update архивът съдържа символна връзка и е отхвърлен.")

                target = destination.joinpath(*pure.parts)
                resolved = target.resolve()
                if destination_resolved not in (resolved, *resolved.parents):
                    raise SelfUpdateError("Update архивът опитва да записва извън staging директорията.")
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)
    except BadZipFile as exc:
        raise SelfUpdateError("GitHub update архивът не е валиден ZIP файл.") from exc

    roots.discard("")
    if len(roots) != 1:
        raise SelfUpdateError("Update архивът няма очакваната GitHub root структура.")
    root = destination / next(iter(roots))
    if not root.is_dir():
        raise SelfUpdateError("Не може да бъде открита root папката на update архива.")
    return root


def _read_staged_version(staged_root: Path, minimum_pr: int) -> tuple[str, int]:
    path = staged_root / "app" / "version.py"
    if not path.is_file():
        raise SelfUpdateError("Update архивът няма app/version.py build metadata.")
    text = path.read_text(encoding="utf-8")
    version_match = re.search(r'^APP_VERSION\s*=\s*["\']([^"\']+)["\']', text, re.MULTILINE)
    pr_match = re.search(r"^CURRENT_PR\s*=\s*(\d+)", text, re.MULTILINE)
    if not version_match or not pr_match:
        raise SelfUpdateError("Update архивът съдържа невалидни build metadata.")
    staged_pr = int(pr_match.group(1))
    if staged_pr < minimum_pr:
        raise SelfUpdateError("Merge commit-ът не е отбелязан с очаквания update build PR.")
    return version_match.group(1), staged_pr


def _run_command(args: list[str], *, cwd: Path, timeout: int = 120, env: dict[str, str] | None = None) -> str:
    try:
        completed = subprocess.run(
            args,
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise SelfUpdateError(f"Не може да бъде стартирана update проверка: {args[0]}.") from exc
    if completed.returncode != 0:
        tail = (completed.stdout or "")[-3000:]
        raise SelfUpdateError(f"Команда за update завърши с грешка.\n{tail}")
    return completed.stdout or ""


def _worker_env() -> dict[str, str]:
    env = os.environ.copy()
    env["MMI2_UPDATE_WORKER"] = "1"
    return env


def _compile_staged_code(staged_root: Path) -> None:
    targets = [str(staged_root / name) for name in ("app", "install", "migrations") if (staged_root / name).exists()]
    _run_command([sys.executable, "-m", "compileall", "-q", *targets], cwd=staged_root, timeout=90)


def _sqlite_database_path() -> Path:
    url = make_url(settings.database_url)
    if not url.drivername.startswith("sqlite") or not url.database or url.database == ":memory:":
        raise SelfUpdateError("SQLite database path не е подходящ за backup.")
    path = Path(url.database).expanduser()
    return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()


def _postgres_environment() -> tuple[dict[str, str], str]:
    url = make_url(settings.database_url)
    env = os.environ.copy()
    if url.host:
        env["PGHOST"] = url.host
    if url.port:
        env["PGPORT"] = str(url.port)
    if url.username:
        env["PGUSER"] = url.username
    if url.password:
        env["PGPASSWORD"] = url.password
    if not url.database:
        raise SelfUpdateError("PostgreSQL DATABASE_URL няма database име.")
    env["PGDATABASE"] = url.database
    sslmode = dict(url.query).get("sslmode")
    if sslmode:
        env["PGSSLMODE"] = str(sslmode)
    return env, url.database


def _backup_database(backup_dir: Path) -> dict:
    url = make_url(settings.database_url)
    runtime_engine.dispose()
    if url.drivername.startswith("sqlite"):
        source_path = _sqlite_database_path()
        if not source_path.exists():
            raise SelfUpdateError("SQLite database файлът не съществува и не може да бъде backup-нат.")
        destination = backup_dir / "database.sqlite"
        with sqlite3.connect(source_path) as source, sqlite3.connect(destination) as target:
            source.backup(target)
        return {"kind": "sqlite", "source": str(source_path), "backup": destination.name}

    if url.drivername.startswith("postgresql"):
        dump_tool = shutil.which("pg_dump")
        restore_tool = shutil.which("pg_restore")
        if not dump_tool or not restore_tool:
            raise SelfUpdateError("pg_dump/pg_restore не са налични за PostgreSQL backup.")
        env, database = _postgres_environment()
        destination = backup_dir / "database.dump"
        _run_command([dump_tool, "--format=custom", "--file", str(destination)], cwd=PROJECT_ROOT, timeout=180, env=env)
        return {
            "kind": "postgresql",
            "database": database,
            "backup": destination.name,
            "pg_restore": restore_tool,
        }

    raise SelfUpdateError(f"Database driver {url.drivername} не поддържа automatic backup.")


def _backup_files(backup_dir: Path) -> None:
    files_root = backup_dir / "files"
    files_root.mkdir(parents=True, exist_ok=True)
    for name in MANAGED_DIRS:
        source = PROJECT_ROOT / name
        if source.exists():
            shutil.copytree(source, files_root / name, dirs_exist_ok=True)
    for name in MANAGED_FILES:
        source = PROJECT_ROOT / name
        if source.is_file():
            destination = files_root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)


def _runtime_file_snapshot() -> dict[str, bytes]:
    snapshot: dict[str, bytes] = {}
    for relative in PRESERVED_RUNTIME_FILES:
        path = PROJECT_ROOT / relative
        if path.is_file():
            snapshot[relative] = path.read_bytes()
    return snapshot


def _replace_managed_files(staged_root: Path) -> None:
    runtime_snapshot = _runtime_file_snapshot()
    for name in MANAGED_DIRS:
        source = staged_root / name
        destination = PROJECT_ROOT / name
        if destination.exists():
            shutil.rmtree(destination)
        if source.exists():
            shutil.copytree(source, destination)

    for name in MANAGED_FILES:
        source = staged_root / name
        destination = PROJECT_ROOT / name
        if destination.exists() and destination.is_file():
            destination.unlink()
        if source.is_file():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)

    for relative, content in runtime_snapshot.items():
        path = PROJECT_ROOT / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)


def _restore_database(backup_dir: Path, metadata: dict) -> None:
    runtime_engine.dispose()
    kind = metadata.get("kind")
    backup = backup_dir / str(metadata.get("backup") or "")
    if kind == "sqlite":
        destination = Path(str(metadata.get("source") or ""))
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(backup, destination)
        return
    if kind == "postgresql":
        restore_tool = shutil.which("pg_restore") or metadata.get("pg_restore")
        if not restore_tool:
            raise SelfUpdateError("PostgreSQL rollback изисква pg_restore.")
        env, database = _postgres_environment()
        _run_command(
            [str(restore_tool), "--clean", "--if-exists", "--no-owner", "--no-privileges", "--dbname", database, str(backup)],
            cwd=PROJECT_ROOT,
            timeout=240,
            env=env,
        )
        return
    raise SelfUpdateError("Backup metadata съдържа непознат database type.")


def _restore_files(backup_dir: Path) -> None:
    files_root = backup_dir / "files"
    if not files_root.is_dir():
        raise SelfUpdateError("Backup-ът няма file snapshot.")
    for name in MANAGED_DIRS:
        destination = PROJECT_ROOT / name
        if destination.exists():
            shutil.rmtree(destination)
        source = files_root / name
        if source.exists():
            shutil.copytree(source, destination)
    for name in MANAGED_FILES:
        destination = PROJECT_ROOT / name
        if destination.exists() and destination.is_file():
            destination.unlink()
        source = files_root / name
        if source.is_file():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)


def _write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _read_json(path: Path) -> dict | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _run_migrations() -> None:
    _run_command(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=PROJECT_ROOT,
        timeout=180,
        env=_worker_env(),
    )


def _smoke_test_new_runtime() -> None:
    _run_command(
        [sys.executable, "-c", "import app.main; print(app.main.app.version)"],
        cwd=PROJECT_ROOT,
        timeout=60,
        env=_worker_env(),
    )


def _request_passenger_restart() -> bool:
    try:
        restart_file = PROJECT_ROOT / "tmp" / "restart.txt"
        restart_file.parent.mkdir(parents=True, exist_ok=True)
        restart_file.touch()
        return True
    except OSError:
        return False


def _create_backup(target: UpdateTarget) -> tuple[str, Path, dict]:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_id = f"{timestamp}-pr{CURRENT_PR}-to-pr{target.pr_number}"
    backup_dir = BACKUP_DIR / backup_id
    backup_dir.mkdir(parents=True, exist_ok=False)
    _backup_files(backup_dir)
    database = _backup_database(backup_dir)
    manifest = {
        "backup_id": backup_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "current_version": APP_VERSION,
        "current_pr": CURRENT_PR,
        "target_pr": target.pr_number,
        "target_sha": target.merge_commit_sha,
        "database": database,
        "managed_dirs": list(MANAGED_DIRS),
        "managed_files": list(MANAGED_FILES),
    }
    _write_json_atomic(backup_dir / "manifest.json", manifest)
    return backup_id, backup_dir, manifest


def rollback_backup(backup_id: str) -> dict:
    if not re.fullmatch(r"[A-Za-z0-9._-]+", backup_id):
        raise SelfUpdateError("Невалиден backup id.")
    backup_dir = BACKUP_DIR / backup_id
    manifest = _read_json(backup_dir / "manifest.json")
    if not manifest:
        raise SelfUpdateError("Update backup-ът не е намерен или е повреден.")
    _restore_files(backup_dir)
    _restore_database(backup_dir, manifest.get("database") or {})
    IN_PROGRESS_FILE.unlink(missing_ok=True)
    RESTART_FILE.unlink(missing_ok=True)
    return {"status": "rolled_back", "backup_id": backup_id, "restart_required": True}


def apply_update(pr_number: int) -> dict:
    with UPDATE_MUTEX:
        if IN_PROGRESS_FILE.exists():
            raise SelfUpdateError("Вече има започнал или прекъснат update. Използвай rollback преди нов опит.")
        if RESTART_FILE.exists():
            raise SelfUpdateError("Предишният update очаква restart на приложението.")

        capability = preflight_update(pr_number)
        if not capability["automatic_apply"]:
            raise SelfUpdateError("Automatic update е блокиран: " + " ".join(capability["reasons"]))
        target = UpdateTarget(**capability["target"])

        UPDATE_DIR.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="mmi2-update-", dir=UPDATE_DIR) as temporary:
            temp_dir = Path(temporary)
            archive_path = temp_dir / "update.zip"
            archive_url = f"https://codeload.github.com/{GITHUB_REPOSITORY}/zip/{target.merge_commit_sha}"
            archive_path.write_bytes(_read_url(archive_url, MAX_ARCHIVE_BYTES))
            staged_root = _safe_extract_archive(archive_path, temp_dir / "extracted")
            target_version, staged_pr = _read_staged_version(staged_root, target.pr_number)

            if (staged_root / "requirements.txt").read_bytes() != (PROJECT_ROOT / "requirements.txt").read_bytes():
                raise SelfUpdateError("requirements.txt се различава от текущия environment. Automatic update е спрян.")
            _compile_staged_code(staged_root)

            backup_id, backup_dir, backup_manifest = _create_backup(target)
            in_progress = {
                "status": "in_progress",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "target_pr": target.pr_number,
                "target_version": target_version,
                "target_sha": target.merge_commit_sha,
                "backup_id": backup_id,
            }
            _write_json_atomic(IN_PROGRESS_FILE, in_progress)

            try:
                _replace_managed_files(staged_root)
                _run_migrations()
                _smoke_test_new_runtime()
            except Exception as exc:
                rollback_error: str | None = None
                try:
                    _restore_files(backup_dir)
                    _restore_database(backup_dir, backup_manifest["database"])
                except Exception as rollback_exc:  # pragma: no cover - emergency path
                    rollback_error = str(rollback_exc)
                IN_PROGRESS_FILE.unlink(missing_ok=True)
                if rollback_error:
                    raise SelfUpdateError(
                        f"Update-ът се провали и автоматичният rollback също не завърши: {rollback_error}"
                    ) from exc
                raise SelfUpdateError(f"Update-ът се провали и беше върнат към backup {backup_id}: {exc}") from exc

            restart_marker = {
                "status": "restart_required",
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "target_pr": staged_pr,
                "target_version": target_version,
                "target_sha": target.merge_commit_sha,
                "backup_id": backup_id,
            }
            _write_json_atomic(RESTART_FILE, restart_marker)
            IN_PROGRESS_FILE.unlink(missing_ok=True)
            restart_requested = _request_passenger_restart()
            return {
                "status": "updated",
                "target_pr": staged_pr,
                "target_version": target_version,
                "backup_id": backup_id,
                "restart_required": True,
                "passenger_restart_requested": restart_requested,
                "message": (
                    "Update-ът е приложен и проверен. Passenger restart е заявен; ако панелът не го рестартира "
                    "автоматично, използвай Restart Python App / Reload application."
                ),
            }


def get_update_runtime_state() -> dict:
    if IN_PROGRESS_FILE.exists():
        marker = _read_json(IN_PROGRESS_FILE) or {}
        return {"status": "interrupted_or_in_progress", **marker}

    if RESTART_FILE.exists():
        marker = _read_json(RESTART_FILE) or {}
        target_pr = int(marker.get("target_pr") or 0)
        if target_pr and CURRENT_PR >= target_pr:
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
            return {"status": "ready", "last_update": completed}
        return {"status": "restart_required", **marker}

    return {"status": "ready", "running_version": APP_VERSION, "running_pr": CURRENT_PR}
