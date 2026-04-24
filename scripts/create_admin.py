#!/usr/bin/env python3
"""Bootstrap script to create the initial admin user.

Usage:
    ADMIN_PASSWORD='...' python scripts/create_admin.py

Environment variables (or .env file):
    DATABASE_URL   – Postgres connection string
    ADMIN_EMAIL    – Admin email (default: admin@adc.local)
    ADMIN_PASSWORD – Admin password (REQUIRED, no default; must be at least 12 chars)
    ADMIN_ORG      – Organization name (default: ADC)

The admin password is intentionally required and is never echoed back. Setting a
weak default would make it trivial to forget to change before exposing the
service to the network.
"""

import os
import sys
from pathlib import Path

# Ensure the backend package is importable (use pathlib so this works on Windows too).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.db.repo.users import get_user_by_email, create_user, create_org, link_user_org
from app.security.permissions import Role


MIN_PASSWORD_LENGTH = 12


def _read_password() -> str:
    """Return the admin password from env, or prompt securely if running interactively."""
    password = os.environ.get("ADMIN_PASSWORD")
    if password:
        return password
    if not sys.stdin.isatty():
        print(
            "ERROR: ADMIN_PASSWORD must be set when running non-interactively.",
            file=sys.stderr,
        )
        sys.exit(2)
    import getpass

    password = getpass.getpass("Admin password: ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("ERROR: passwords did not match.", file=sys.stderr)
        sys.exit(2)
    return password


def main() -> int:
    email = os.environ.get("ADMIN_EMAIL", "admin@adc.local")
    org_name = os.environ.get("ADMIN_ORG", "ADC")
    password = _read_password()

    if len(password) < MIN_PASSWORD_LENGTH:
        print(
            f"ERROR: ADMIN_PASSWORD must be at least {MIN_PASSWORD_LENGTH} characters.",
            file=sys.stderr,
        )
        return 2

    try:
        db = SessionLocal()
    except Exception as exc:  # pragma: no cover - depends on DB availability
        print(f"ERROR: failed to open database session: {exc}", file=sys.stderr)
        return 1

    try:
        existing = get_user_by_email(db, email)
        if existing:
            print(f"Admin user '{email}' already exists (id={existing.id}). Skipping.")
            return 0

        pw_hash = hash_password(password)
        user = create_user(
            db,
            email=email,
            password_hash=pw_hash,
            role=Role.ORG_ADMIN.value,
        )
        org = create_org(db, name=org_name)
        link_user_org(db, user_id=user.id, org_id=org.id)

        # Intentionally do NOT log the password value.
        print("Created admin user:")
        print(f"  email   : {email}")
        print(f"  role    : {Role.ORG_ADMIN.value}")
        print(f"  user_id : {user.id}")
        print(f"  org_id  : {org.id}")
        print(f"  org_name: {org_name}")
        return 0
    except Exception as exc:
        print(f"ERROR: failed to create admin user: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
