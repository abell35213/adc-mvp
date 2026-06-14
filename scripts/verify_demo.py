#!/usr/bin/env python3
"""Verify the ``crash_with_full_packet`` Phase 4 demo scenario end-to-end.

Spins up an in-memory SQLite database with the production ORM, seeds the
scenario, and asserts that every record the guided tour calls out is
actually present and well-formed.

Runs offline — no Postgres, Celery, SES, or S3 required — so it can be
wired into CI as a deterministic smoke test that the cross-phase wiring
hasn't regressed.

Exit codes:
* ``0`` — every check passed.
* ``1`` — at least one assertion failed (details printed to stderr).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
import urllib.error
import urllib.request
from pathlib import Path

# Make ``app`` importable when running from the repo root.
_BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(_BACKEND_DIR))


SCENARIO_KEY = "crash_with_full_packet"
DEFAULT_DEMO_EMAIL = "demo-admin@adc.local"
DEFAULT_DEMO_PASSWORD = "DemoAdmin!2345"
DEFAULT_DEMO_ORG = "ADC Demo Org"


def _check_api_login(api_base_url: str, email: str, password: str) -> bool:
    """Return True when the running API accepts the seeded demo login."""
    url = api_base_url.rstrip("/") + "/auth/login"
    payload = json.dumps({"email": email, "password": password}).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
            return response.status == 200 and bool(data.get("access_token"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return False


def run_local_db() -> int:
    """Verify demo data in the configured local Postgres database."""
    email = os.environ.get("DEMO_ADMIN_EMAIL", DEFAULT_DEMO_EMAIL)
    password = os.environ.get("DEMO_ADMIN_PASSWORD", DEFAULT_DEMO_PASSWORD)
    org_name = os.environ.get("DEMO_ORG", DEFAULT_DEMO_ORG)
    api_base_url = os.environ.get("DEMO_API_BASE_URL", "http://localhost:8000")

    print("Verifying local demo database and API login")
    print(f"  org={org_name}")
    print(f"  admin={email}")
    print(f"  api={api_base_url}")

    from app.core.security import verify_password
    from app.db.models import Incident, Org, User, UserOrg
    from app.db.session import SessionLocal
    from app.security.permissions import Role

    errors: list[str] = []
    db = SessionLocal()
    try:
        org = db.query(Org).filter(Org.name == org_name).one_or_none()
        _check("demo organization exists", org is not None, errors=errors)

        user = db.query(User).filter(User.email == email).one_or_none()
        _check("demo admin user exists", user is not None, errors=errors)
        if user is not None:
            _check("demo admin is active", bool(user.is_active), errors=errors)
            _check(
                "demo admin role is org_admin",
                user.role == Role.ORG_ADMIN.value,
                errors=errors,
            )
            _check(
                "demo admin password matches documented credential",
                verify_password(password, user.password_hash),
                errors=errors,
            )

        membership_exists = False
        incident_count = 0
        if org is not None and user is not None:
            membership_exists = (
                db.query(UserOrg)
                .filter(UserOrg.org_id == org.id, UserOrg.user_id == user.id)
                .first()
                is not None
            )
            incident_count = (
                db.query(Incident).filter(Incident.org_id == org.id).count()
            )
        _check(
            "demo admin belongs to demo organization", membership_exists, errors=errors
        )
        _check("at least one demo incident exists", incident_count >= 1, errors=errors)
        _check(
            "demo API login returns an access token",
            _check_api_login(api_base_url, email, password),
            errors=errors,
        )

        if errors:
            print(
                f"\nlocal verify-demo FAILED with {len(errors)} check(s) failing.",
                file=sys.stderr,
            )
            return 1

        print("\nlocal verify-demo OK — seeded demo tenant is usable.")
        return 0
    except Exception:
        traceback.print_exc()
        return 1
    finally:
        db.close()


def _build_session():
    """Create an in-memory SQLite session with all ORM tables."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    # Make Postgres-only column types compile against SQLite.
    from sqlalchemy.dialects.postgresql import JSONB, UUID
    from sqlalchemy.ext.compiler import compiles

    @compiles(JSONB, "sqlite")
    def _jsonb(_e, _c, **_k):  # noqa: D401, ANN001 - sqla compiler signature
        return "TEXT"

    @compiles(UUID, "sqlite")
    def _uuid(_e, _c, **_k):  # noqa: D401, ANN001
        return "CHAR(32)"

    # WeasyPrint isn't installed in many CI environments; fake it the same
    # way ``backend/tests/conftest.py`` does so PDF render returns bytes.
    import hashlib
    from types import SimpleNamespace

    class _FakeHTML:
        def __init__(self, string, base_url=None):
            self.string = string

        def write_pdf(self):
            digest = hashlib.sha256(self.string.encode("utf-8")).hexdigest()[:16]
            return b"%PDF-1.4\nverify-demo:" + digest.encode("ascii")

    sys.modules.setdefault("weasyprint", SimpleNamespace(HTML=_FakeHTML))

    from app.db.models import Base

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    return Session()


def _seed_identity(db):
    """Create the minimal Org + ORG_ADMIN actor needed by the seeder."""
    from app.core.security import hash_password
    from app.db.models import Org, User, UserOrg
    from app.security.permissions import Role

    org = Org(name="ADC Verify-Demo Org")
    db.add(org)
    db.commit()
    db.refresh(org)

    actor = User(
        email="verify-demo@adc.local",
        password_hash=hash_password("verify-demo"),
        role=Role.ORG_ADMIN.value,
    )
    db.add(actor)
    db.commit()
    db.refresh(actor)
    db.add(UserOrg(user_id=actor.id, org_id=org.id))
    db.commit()
    return org, actor


def _check(label, condition, *, errors):
    """Print a per-check line; record any failure for the final summary."""
    if condition:
        print(f"  ✓ {label}")
    else:
        print(f"  ✗ {label}", file=sys.stderr)
        errors.append(label)


def run() -> int:
    """Run all verifications. Returns process exit code."""
    print(f"Verifying demo scenario: {SCENARIO_KEY}")
    db = _build_session()
    try:
        org, actor = _seed_identity(db)

        from app.commercial.demo import seed_demo_tenant
        from app.db.models import (
            Artifact,
            CrashPacketDelivery,
            Driver,
            Incident,
            InsuranceFormFilling,
            InsuranceFormTemplate,
            MaintenanceRecord,
            OrgNotificationRecipient,
            Trailer,
        )

        result = seed_demo_tenant(
            db, org_id=org.id, actor=actor, scenario_key=SCENARIO_KEY
        )

        errors: list[str] = []

        # Seeder return surface.
        for key in (
            "incident_id",
            "driver_id",
            "trailer_id",
            "recipient_id",
            "crash_packet_delivery_id",
            "insurance_form_template_id",
            "insurance_form_filling_id",
            "insurance_form_artifact_id",
        ):
            _check(
                f"seed result contains {key!r}",
                bool(result.get(key)),
                errors=errors,
            )

        # Phase 1 — incident moved to accident_occurred + delivery row sent.
        incident = db.query(Incident).filter(Incident.org_id == org.id).one()
        _check(
            "incident.status == 'accident_occurred'",
            incident.status == "accident_occurred",
            errors=errors,
        )
        delivery = (
            db.query(CrashPacketDelivery)
            .filter(CrashPacketDelivery.org_id == org.id)
            .one_or_none()
        )
        _check(
            "exactly one CrashPacketDelivery seeded",
            delivery is not None,
            errors=errors,
        )
        if delivery is not None:
            _check(
                "delivery.status == 'sent'",
                delivery.status == "sent",
                errors=errors,
            )
        recipients = (
            db.query(OrgNotificationRecipient)
            .filter(OrgNotificationRecipient.org_id == org.id)
            .all()
        )
        _check(
            "exactly one active OrgNotificationRecipient seeded",
            len(recipients) == 1 and recipients[0].active,
            errors=errors,
        )

        # Phase 2 — trailer + maintenance + assigned driver.
        trailers = db.query(Trailer).filter(Trailer.org_id == org.id).all()
        _check("exactly one Trailer seeded", len(trailers) == 1, errors=errors)
        maint = (
            db.query(MaintenanceRecord).filter(MaintenanceRecord.org_id == org.id).all()
        )
        _check(
            "three MaintenanceRecord rows seeded (mixed tractor + trailer)",
            len(maint) == 3 and {m.asset_kind for m in maint} == {"tractor", "trailer"},
            errors=errors,
        )
        drivers = (
            db.query(Driver)
            .filter(Driver.org_id == org.id, Driver.display_name == "Pat Demo-Driver")
            .all()
        )
        _check(
            "Driver 'Pat Demo-Driver' seeded",
            len(drivers) == 1,
            errors=errors,
        )

        # Phase 3 — finalized template + filled artifact.
        template = (
            db.query(InsuranceFormTemplate)
            .filter(InsuranceFormTemplate.org_id == org.id)
            .one_or_none()
        )
        _check(
            "InsuranceFormTemplate seeded and finalized",
            template is not None and template.status == "finalized",
            errors=errors,
        )
        filling = (
            db.query(InsuranceFormFilling)
            .filter(InsuranceFormFilling.incident_id == incident.incident_id)
            .one_or_none()
        )
        _check(
            "InsuranceFormFilling seeded with status='filled'",
            filling is not None and filling.status == "filled",
            errors=errors,
        )
        if filling is not None:
            _check(
                "filling.missing_required_fields is empty",
                filling.missing_required_fields == [],
                errors=errors,
            )
            _check(
                "filling has output_artifact_id",
                filling.output_artifact_id is not None,
                errors=errors,
            )
            artifact = (
                db.query(Artifact)
                .filter(Artifact.artifact_id == filling.output_artifact_id)
                .one_or_none()
            )
            _check(
                "Artifact for filling has type 'insurance_form_filled' and bytes",
                (
                    artifact is not None
                    and artifact.artifact_type == "insurance_form_filled"
                    and artifact.byte_size
                    and artifact.byte_size > 0
                ),
                errors=errors,
            )
            # The fill must have used the canonical row, not the placeholder
            # ``incident.adc_driver_id`` text id. The DriverName field is
            # required + ``upper`` transform.
            by_name = {
                f["name"]: f for f in (filling.payload_json or {}).get("fields", [])
            }
            _check(
                "fill resolved DriverName from canonical row (Driver join + upper)",
                by_name.get("DriverName", {}).get("value") == "PAT DEMO-DRIVER",
                errors=errors,
            )
            _check(
                "fill resolved TrailerVIN from Phase 2 trailer table",
                by_name.get("TrailerVIN", {}).get("value") == "TRDEMO00000000001",
                errors=errors,
            )

        if errors:
            print(
                f"\nverify-demo FAILED with {len(errors)} check(s) failing.",
                file=sys.stderr,
            )
            return 1

        print(f"\nverify-demo OK — {SCENARIO_KEY} scenario validated.")
        return 0
    except Exception:
        traceback.print_exc()
        return 1
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--local-db",
        action="store_true",
        help="verify seeded demo data in DATABASE_URL and API login",
    )
    args = parser.parse_args()
    if args.local_db:
        return run_local_db()
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
