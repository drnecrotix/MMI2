from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from time import monotonic
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.version import APP_VERSION, CURRENT_PR, GITHUB_REPOSITORY


CACHE_SECONDS = 600
_cache: tuple[float, dict] | None = None


class UpdateCheckError(RuntimeError):
    pass


@dataclass(frozen=True)
class UpdateInfo:
    current_version: str
    current_pr: int
    update_available: bool
    latest_pr: int
    latest_title: str | None
    latest_url: str | None
    merged_updates: list[dict]

    def as_dict(self) -> dict:
        return asdict(self)


def _parse_merged_prs(rows: list[dict]) -> UpdateInfo:
    merged = []
    for row in rows:
        if not row.get("merged_at"):
            continue
        base = row.get("base") or {}
        if base.get("ref") != "main":
            continue
        number = int(row.get("number") or 0)
        if number <= CURRENT_PR:
            continue
        merged.append(
            {
                "number": number,
                "title": str(row.get("title") or ""),
                "url": str(row.get("html_url") or ""),
                "merged_at": row.get("merged_at"),
            }
        )

    merged.sort(key=lambda item: item["number"], reverse=True)
    latest = merged[0] if merged else None
    return UpdateInfo(
        current_version=APP_VERSION,
        current_pr=CURRENT_PR,
        update_available=latest is not None,
        latest_pr=latest["number"] if latest else CURRENT_PR,
        latest_title=latest["title"] if latest else None,
        latest_url=latest["url"] if latest else None,
        merged_updates=merged[:10],
    )


def check_for_updates(force: bool = False) -> dict:
    global _cache
    now = monotonic()
    if not force and _cache is not None and now - _cache[0] < CACHE_SECONDS:
        return _cache[1]

    url = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/pulls?state=closed&sort=updated&direction=desc&per_page=50"
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "MMI2-Update-Checker",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )

    try:
        with urlopen(request, timeout=6) as response:  # noqa: S310 - fixed GitHub API host
            rows = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise UpdateCheckError("GitHub update check временно не е достъпен.") from exc

    if not isinstance(rows, list):
        raise UpdateCheckError("GitHub върна неочакван отговор при проверката за update.")

    result = _parse_merged_prs(rows).as_dict()
    _cache = (now, result)
    return result
