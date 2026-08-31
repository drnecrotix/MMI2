#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys

from app.services.self_update import (
    SelfUpdateError,
    apply_update,
    get_update_runtime_state,
    preflight_update,
)
from app.services.update_checker import UpdateCheckError, check_for_updates


def print_json(value: dict) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def command_check(force: bool) -> int:
    try:
        result = check_for_updates(force=force)
    except UpdateCheckError as exc:
        print(f"Update check error: {exc}", file=sys.stderr)
        return 1
    print_json(result)
    return 0


def command_preflight(pr_number: int) -> int:
    try:
        result = preflight_update(pr_number)
    except SelfUpdateError as exc:
        print(f"Preflight error: {exc}", file=sys.stderr)
        return 1
    print_json(result)
    return 0 if result.get("automatic_apply") else 2


def command_apply(pr_number: int, confirmed: bool) -> int:
    if not confirmed:
        print(
            "Update не е стартиран. Направи backup извън сървъра и повтори с --yes, "
            "след като preflight е успешен.",
            file=sys.stderr,
        )
        return 2
    try:
        result = apply_update(pr_number)
    except SelfUpdateError as exc:
        print(f"Update error: {exc}", file=sys.stderr)
        return 1
    print_json(result)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="MMI2 safe self-update utility")
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="Check GitHub for newer merged PRs")
    check.add_argument("--force", action="store_true", help="Ignore the 10 minute update cache")

    preflight = sub.add_parser("preflight", help="Validate a merged PR before applying it")
    preflight.add_argument("pr_number", type=int)

    apply = sub.add_parser("apply", help="Backup and apply a merged PR")
    apply.add_argument("pr_number", type=int)
    apply.add_argument("--yes", action="store_true", help="Required confirmation")

    sub.add_parser("status", help="Show self-update runtime state")

    args = parser.parse_args()
    if args.command == "check":
        return command_check(args.force)
    if args.command == "preflight":
        return command_preflight(args.pr_number)
    if args.command == "apply":
        return command_apply(args.pr_number, args.yes)
    if args.command == "status":
        print_json(get_update_runtime_state())
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
