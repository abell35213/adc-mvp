#!/usr/bin/env python3
"""Lint hardening-related PRs to require control matrix updates."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

MATRIX_PATH = "docs/production-hardening/control-matrix.md"
REQUIRED_SCOPE_ITEMS = {
    "auth/session",
    "authz/tenancy",
    "secrets",
    "audit",
    "observability",
    "queue reliability",
    "storage security",
    "api resilience",
    "ci/cd",
    "backups/dr",
    "env management",
    "support ops",
}
HARDENING_PATH_PREFIXES = (
    "backend/app/core/",
    "backend/app/api/routes_auth.py",
    "backend/app/api/routes_driver_auth.py",
    "backend/app/tasks/",
    "backend/app/services/vault_",
    "docs/production-hardening/",
    "infra/production/",
    "scripts/check_release_hardening_gates.py",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default=os.getenv("GITHUB_BASE_REF", ""), help="Diff base ref")
    parser.add_argument("--head", default=os.getenv("GITHUB_SHA", "HEAD"), help="Diff head ref")
    parser.add_argument(
        "--files",
        nargs="*",
        default=None,
        help="Optional explicit file list (useful for tests).",
    )
    return parser.parse_args()


def _git_changed_files(base: str, head: str) -> list[str]:
    candidates: list[list[str]] = []

    if base:
        candidates.append(["git", "diff", "--name-only", f"{base}...{head}"])
        candidates.append(["git", "diff", "--name-only", f"origin/{base}...{head}"])

    candidates.extend(
        [
            ["git", "diff", "--name-only", "--cached"],
            ["git", "diff", "--name-only"],
            ["git", "diff", "--name-only", "HEAD~1...HEAD"],
        ]
    )

    for cmd in candidates:
        try:
            output = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue

        files = [line.strip() for line in output.splitlines() if line.strip()]
        if files:
            return files

    return []


def _is_hardening_path(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in HARDENING_PATH_PREFIXES)


def _validate_scope_rows() -> list[str]:
    matrix = Path(MATRIX_PATH)
    if not matrix.exists():
        return [f"Missing matrix file: {MATRIX_PATH}"]

    matrix_text = matrix.read_text(encoding="utf-8").lower()
    missing = [item for item in sorted(REQUIRED_SCOPE_ITEMS) if f"| {item} |" not in matrix_text]
    return [f"Matrix is missing required scope row: {item}" for item in missing]


def main() -> int:
    args = parse_args()
    changed_files = args.files if args.files is not None else _git_changed_files(args.base, args.head)

    matrix_errors = _validate_scope_rows()
    if matrix_errors:
        for error in matrix_errors:
            print(error)
        return 1

    if not changed_files:
        print("No changed files detected; skipping hardening-matrix diff enforcement.")
        return 0

    hardening_changes = [path for path in changed_files if path != MATRIX_PATH and _is_hardening_path(path)]
    matrix_touched = MATRIX_PATH in changed_files

    if hardening_changes and not matrix_touched:
        print("Hardening-related files changed without matrix update:")
        for path in hardening_changes:
            print(f" - {path}")
        print(f"Please update {MATRIX_PATH} in this PR.")
        return 1

    print("Hardening matrix lint check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
