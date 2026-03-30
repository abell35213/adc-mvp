#!/usr/bin/env python3
"""Fail when critical backend module trees are duplicated in both app/ and backend/app/."""

from __future__ import annotations

from pathlib import Path
import sys

CRITICAL_PACKAGES = ("api", "db", "services", "tasks")


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    legacy_root = repo_root / "app"
    canonical_root = repo_root / "backend" / "app"

    duplicates: list[str] = []
    for package in CRITICAL_PACKAGES:
        legacy_path = legacy_root / package
        canonical_path = canonical_root / package
        if legacy_path.exists() and canonical_path.exists():
            duplicates.append(package)

    if duplicates:
        print("Duplicate critical module paths detected.", file=sys.stderr)
        for package in duplicates:
            print(
                f" - {legacy_root / package} duplicates {canonical_root / package}",
                file=sys.stderr,
            )
        print(
            "Use backend/app as the canonical runtime package and remove stale app/* duplicates.",
            file=sys.stderr,
        )
        return 1

    print("No duplicate critical module paths found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
