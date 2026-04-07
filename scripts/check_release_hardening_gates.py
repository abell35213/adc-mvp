#!/usr/bin/env python3
"""Fail CI for production release tags when Priority-1 hardening gates are incomplete."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

PRIORITY_1_GATES = {
    "identity_authz",
    "audit_logging",
    "observability",
    "backups",
    "release_flow",
}
COMPLETE_STATUSES = {"complete", "completed", "done", "verified"}
PRODUCTION_TAG_PATTERN = r"(?i)(^prod[-_/]|^production[-_/]|[-_/]prod[-_/]|[-_/]production[-_/]|^v\d+\.\d+\.\d+-prod$)"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--checklist",
        default="docs/production-hardening/checklist.yaml",
        help="Path to the hardening checklist file (JSON-compatible YAML).",
    )
    parser.add_argument(
        "--tag",
        default="",
        help="Release tag to evaluate. Defaults to CI env (GITHUB_REF_NAME/CI_COMMIT_TAG).",
    )
    return parser.parse_args()


def detect_tag(explicit_tag: str) -> str:
    if explicit_tag:
        return explicit_tag

    for var in ("GITHUB_REF_NAME", "CI_COMMIT_TAG", "GIT_TAG"):
        value = os.getenv(var, "").strip()
        if value:
            return value

    github_ref = os.getenv("GITHUB_REF", "")
    prefix = "refs/tags/"
    if github_ref.startswith(prefix):
        return github_ref[len(prefix) :]

    return ""


def is_production_tag(tag: str) -> bool:
    return bool(tag) and re.search(PRODUCTION_TAG_PATTERN, tag) is not None


def load_checklist(path: Path) -> list[dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"Checklist file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Checklist must be JSON-compatible YAML: {exc}") from exc

    if not isinstance(data, list):
        raise SystemExit("Checklist root must be a list of requirement entries.")

    for index, entry in enumerate(data, start=1):
        if not isinstance(entry, dict):
            raise SystemExit(f"Checklist entry #{index} is not an object.")

    return data


def find_incomplete_priority_1(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for entry in entries:
        gate = str(entry.get("gate", "")).strip()
        priority = int(entry.get("priority", 0))
        status = str(entry.get("status", "")).strip().lower()
        if priority == 1 and gate in PRIORITY_1_GATES and status not in COMPLETE_STATUSES:
            failures.append(entry)
    return failures


def main() -> int:
    args = parse_args()
    tag = detect_tag(args.tag)

    if not is_production_tag(tag):
        print(f"Skipping hardening gate enforcement for non-production tag: {tag or '<none>'}")
        return 0

    checklist_path = Path(args.checklist)
    entries = load_checklist(checklist_path)
    failures = find_incomplete_priority_1(entries)

    if not failures:
        print(f"All Priority-1 gates are complete for production tag '{tag}'.")
        return 0

    print(f"Production tag '{tag}' blocked: incomplete Priority-1 gates detected:")
    for entry in failures:
        print(
            " - section {section} [{gate}] status={status} owner={owner} target={target}".format(
                section=entry.get("section", "?"),
                gate=entry.get("gate", "unknown"),
                status=entry.get("status", "unknown"),
                owner=entry.get("owner", "unknown"),
                target=entry.get("target_sprint", "unknown"),
            )
        )
    return 1


if __name__ == "__main__":
    sys.exit(main())
