#!/usr/bin/env python3
"""Bootstrap script to create the initial admin user.

Usage:
    python scripts/create_admin.py

Environment variables (or .env file):
    DATABASE_URL   – Postgres connection string
    ADMIN_EMAIL    – Admin email (default: admin@adc.local)
    ADMIN_PASSWORD – Admin password (default: changeme)
    ADMIN_ORG      – Organization name (default: ADC)
"""

import os
import sys

# Ensure the backend package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.db.repo.users import get_user_by_email, create_user, create_org, link_user_org
from app.security.permissions import Role


def main():
    email = os.environ.get("ADMIN_EMAIL", "admin@adc.local")
    password = os.environ.get("ADMIN_PASSWORD", "changeme")
    org_name = os.environ.get("ADMIN_ORG", "ADC")

    db = SessionLocal()
    try:
        existing = get_user_by_email(db, email)
        if existing:
            print(f"Admin user '{email}' already exists (id={existing.id}). Skipping.")
            return

        pw_hash = hash_password(password)
        user = create_user(
            db,
            email=email,
            password_hash=pw_hash,
            role=Role.ADMIN.value,
        )
        org = create_org(db, name=org_name)
        link_user_org(db, user_id=user.id, org_id=org.id)

        print(f"Created admin user:")
        print(f"  email   : {email}")
        print(f"  role    : {Role.ADMIN.value}")
        print(f"  user_id : {user.id}")
        print(f"  org_id  : {org.id}")
        print(f"  org_name: {org_name}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
