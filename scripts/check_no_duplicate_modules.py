#!/usr/bin/env python3
"""Fail when critical backend module trees are duplicated in both app/ and backend/app/.

Also fails when the historically-stale top-level ``migrations/`` directory or
``alembic.ini`` file are reintroduced. The canonical Alembic tree lives at
``backend/app/db/migrations`` and is configured via ``backend/alembic.ini``;
keeping a duplicate at the repository root creates ambiguity about which set
of revisions is authoritative.
"""

from __future__ import annotations

from pathlib import Path
import sys

CRITICAL_PACKAGES = ("api", "db", "services", "tasks")
STALE_MIGRATION_PATHS = (
    "migrations",
    "backend/migrations",
    "alembic.ini",
)


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

    stale_migration_violations: list[Path] = []
    for relative in STALE_MIGRATION_PATHS:
        candidate = repo_root / relative
        if candidate.exists():
            stale_migration_violations.append(candidate)

    if stale_migration_violations:
        print(
            "Stale Alembic paths detected. The canonical migration tree is "
            "backend/app/db/migrations and the canonical config is backend/alembic.ini.",
            file=sys.stderr,
        )
        for violation in stale_migration_violations:
            print(f" - {violation}", file=sys.stderr)
        return 1

    print("No duplicate critical module paths or stale Alembic trees found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
