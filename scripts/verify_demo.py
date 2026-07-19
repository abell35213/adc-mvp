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
import time
import traceback
import urllib.error
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any

# Make ``app`` importable when running from the repo root.
_BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(_BACKEND_DIR))


SCENARIO_KEY = "crash_with_full_packet"
DEFAULT_DEMO_EMAIL = "demo-admin@adc.local"
DEFAULT_DEMO_PASSWORD = "DemoAdmin!2345"
DEFAULT_DEMO_ORG = "ADC Demo Org"
BODY_PREVIEW_LIMIT = 500
JSON_CONTENT_TYPES = {"application/json", "application/problem+json"}
REQUEST_ID_HEADERS = ("x-request-id", "x-correlation-id", "traceparent")


def _is_json_content_type(content_type: str) -> bool:
    media_type = content_type.partition(";")[0].strip().lower()
    return media_type in JSON_CONTENT_TYPES or media_type.endswith("+json")


def _parse_response_body(body: str, content_type: str) -> Any:
    """Parse JSON without allowing a misleading content type to mask HTTP errors."""
    if not body:
        return None
    stripped = body.lstrip()
    looks_like_json = stripped.startswith(("{", "["))
    if _is_json_content_type(content_type) or looks_like_json:
        try:
            return json.loads(body)
        except (json.JSONDecodeError, TypeError):
            pass
    return body


def _safe_body_preview(body: str, limit: int = BODY_PREVIEW_LIMIT) -> str:
    if not body:
        return ""
    out: list[str] = []
    in_ws = False
    truncated = False
    for ch in body:
        if ch.isspace():
            if not in_ws:
                out.append(" ")
                in_ws = True
        else:
            out.append(ch)
            in_ws = False
        if len(out) >= limit:
            truncated = True
            break
    normalized = "".join(out).strip()
    return f"{normalized}… [truncated]" if truncated else normalized


def _request_id(headers: Any) -> str | None:
    for name in REQUEST_ID_HEADERS:
        value = headers.get(name)
        if value:
            return str(value)[:200]
    return None


def _unexpected_response_message(
    method: str, path: str, status: int, content_type: str, body: str, headers: Any
) -> str:
    lines = [
        f"{method} {path} returned {status}",
        f"Content-Type: {content_type or '(not provided)'}",
        f"Body: {_safe_body_preview(body) or '(empty)'}",
    ]
    request_id = _request_id(headers)
    if request_id:
        lines.append(f"Request ID: {request_id}")
    return "\n".join(lines)


class ApiClient:
    """Small stdlib HTTP client that preserves auth cookies between calls."""

    def __init__(self, base_url: str, *, timeout: int = 10) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(CookieJar())
        )

    def request(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        expected: tuple[int, ...] = (200,),
    ) -> tuple[int, Any]:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {"Accept": "application/json"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            self.base_url + path, data=data, headers=headers, method=method
        )
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8", errors="replace")
                content_type = response.headers.get("Content-Type", "")
                parsed = _parse_response_body(body, content_type)
                if response.status not in expected:
                    raise RuntimeError(_unexpected_response_message(
                        method, path, response.status, content_type, body, response.headers
                    ))
                return response.status, parsed
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            content_type = exc.headers.get("Content-Type", "")
            detail = _parse_response_body(body, content_type)
            if exc.code in expected:
                return exc.code, detail
            raise RuntimeError(_unexpected_response_message(
                method, path, exc.code, content_type, body, exc.headers
            )) from exc


def _check_api_login(api_base_url: str, email: str, password: str) -> bool:
    """Return True when the running API accepts the seeded demo login."""
    try:
        client = ApiClient(api_base_url)
        _status, data = client.request(
            "POST", "/auth/login", payload={"email": email, "password": password}
        )
        if isinstance(data, dict) and data.get("access_token"):
            return True
        _status, me = client.request("GET", "/auth/me")
        return isinstance(me, dict) and me.get("email") == email
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, RuntimeError):
        return False


def _first_incident_id(rows: Any) -> str | None:
    if not isinstance(rows, list) or not rows:
        return None
    first = rows[0]
    if not isinstance(first, dict):
        return None
    incident_id = first.get("incident_id")
    return str(incident_id) if incident_id else None


def _poll_export_status(
    client: ApiClient, export_id: str, *, timeout_seconds: int
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_status: dict[str, Any] = {}
    while time.monotonic() < deadline:
        _status, payload = client.request("GET", f"/exports/{export_id}/status")
        if not isinstance(payload, dict):
            raise RuntimeError("export status response is not an object")
        last_status = payload
        if payload.get("status") in {"ready", "failed"}:
            return payload
        time.sleep(2)
    return last_status


def run_live_api() -> int:
    """Verify the seeded demo workflow against a running local API stack."""
    email = os.environ.get("DEMO_ADMIN_EMAIL", DEFAULT_DEMO_EMAIL)
    password = os.environ.get("DEMO_ADMIN_PASSWORD", DEFAULT_DEMO_PASSWORD)
    api_base_url = os.environ.get("DEMO_API_BASE_URL", "http://localhost:8000")
    export_timeout = int(os.environ.get("DEMO_EXPORT_TIMEOUT_SECONDS", "60"))

    print("Verifying live seeded demo workflow")
    print(f"  admin={email}")
    print(f"  api={api_base_url}")
    print("  note=export readiness requires the local worker from `make local-up`")

    errors: list[str] = []
    client = ApiClient(api_base_url)
    try:
        _status, health = client.request("GET", "/health")
        _check(
            "backend health endpoint responds", isinstance(health, dict), errors=errors
        )

        _status, login_payload = client.request(
            "POST", "/auth/login", payload={"email": email, "password": password}
        )
        login_ok = isinstance(login_payload, dict) and (
            bool(login_payload.get("access_token")) or bool(login_payload.get("user"))
        )
        _check("demo admin can authenticate", login_ok, errors=errors)

        _status, me = client.request("GET", "/auth/me")
        org_ids = me.get("org_ids") if isinstance(me, dict) else []
        _check(
            "demo org/tenant is visible to authenticated admin",
            bool(org_ids),
            errors=errors,
        )
        _check(
            "frontend auth contract exposes user_id/email/role/org_ids",
            isinstance(me, dict)
            and {"user_id", "email", "role", "org_ids"}.issubset(me),
            errors=errors,
        )

        _status, incidents = client.request("GET", "/incidents/")
        incident_id = _first_incident_id(incidents)
        _check(
            "at least one seeded incident exists",
            incident_id is not None,
            errors=errors,
        )
        if incident_id is None:
            raise RuntimeError("no incident available for live smoke workflow")

        _status, detail = client.request("GET", f"/incidents/{incident_id}")
        _check(
            "incident detail can be fetched", isinstance(detail, dict), errors=errors
        )
        evidence = (
            detail.get("evidence_inventory") if isinstance(detail, dict) else None
        )
        _check(
            "evidence/artifacts for the incident can be listed",
            isinstance(evidence, list) and len(evidence) > 0,
            errors=errors,
        )
        _check(
            "frontend incident detail contract exposes evidence_inventory/export_status/timeline",
            isinstance(detail, dict)
            and {"evidence_inventory", "export_status", "timeline"}.issubset(detail),
            errors=errors,
        )

        _status, export_payload = client.request(
            "POST", f"/incidents/{incident_id}/exports", expected=(201,)
        )
        export_id = (
            export_payload.get("export_id")
            if isinstance(export_payload, dict)
            else None
        )
        _check(
            "export generation endpoint can be called", bool(export_id), errors=errors
        )
        if not export_id:
            raise RuntimeError("export endpoint did not return export_id")

        export_status = _poll_export_status(
            client, str(export_id), timeout_seconds=export_timeout
        )
        _check(
            "export status can be checked",
            bool(export_status.get("status")),
            errors=errors,
        )
        _check(
            "export reached ready status",
            export_status.get("status") == "ready",
            errors=errors,
        )

        if export_status.get("status") == "ready":
            _status, contents = client.request("GET", f"/exports/{export_id}/contents")
            _check(
                "ready export exposes a contents manifest",
                isinstance(contents, dict)
                and isinstance(contents.get("file_manifest"), list),
                errors=errors,
            )
            _status, download = client.request("GET", f"/exports/{export_id}/download")
            _check(
                "ready export has a downloadable URL",
                isinstance(download, dict) and bool(download.get("url")),
                errors=errors,
            )

        if errors:
            print(
                f"\nlive smoke FAILED with {len(errors)} check(s) failing.",
                file=sys.stderr,
            )
            return 1
        print("\nlive smoke OK — seeded incident-to-export workflow validated.")
        return 0
    except Exception:
        traceback.print_exc()
        return 1


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
    from app.db.models import (
        Artifact,
        CaseNote,
        CaseTask,
        Event,
        Export,
        Driver,
        Incident,
        Org,
        OrgVehicleRegistry,
        User,
        UserOrg,
    )
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
        _check(
            "expanded demo has at least 24 incidents",
            incident_count >= 24,
            errors=errors,
        )
        _check(
            "expanded demo has at least 12 drivers",
            db.query(Driver).filter(Driver.org_id == org.id).count() >= 12,
            errors=errors,
        )
        _check(
            "expanded demo has at least 12 vehicles",
            db.query(OrgVehicleRegistry)
            .filter(OrgVehicleRegistry.org_id == org.id)
            .count()
            >= 12,
            errors=errors,
        )
        demo_incident_ids = [
            row.incident_id
            for row in db.query(Incident.incident_id)
            .filter(Incident.org_id == org.id)
            .all()
        ]
        _check(
            "expanded demo has evidence",
            db.query(Artifact)
            .filter(
                Artifact.org_id == org.id, Artifact.incident_id.in_(demo_incident_ids)
            )
            .count()
            >= 60,
            errors=errors,
        )
        _check(
            "expanded demo has tasks",
            db.query(CaseTask)
            .filter(
                CaseTask.org_id == org.id, CaseTask.incident_id.in_(demo_incident_ids)
            )
            .count()
            >= 40,
            errors=errors,
        )
        _check(
            "expanded demo has notes",
            db.query(CaseNote)
            .filter(
                CaseNote.org_id == org.id, CaseNote.incident_id.in_(demo_incident_ids)
            )
            .count()
            >= 30,
            errors=errors,
        )
        _check(
            "expanded demo has timeline events",
            db.query(Event)
            .filter(Event.org_id == org.id, Event.incident_id.in_(demo_incident_ids))
            .count()
            >= 120,
            errors=errors,
        )
        _check(
            "expanded demo has exports",
            db.query(Export)
            .filter(Export.org_id == org.id, Export.incident_id.in_(demo_incident_ids))
            .count()
            >= 18,
            errors=errors,
        )
        _check(
            "expanded demo has ready/failed/processing exports",
            all(
                db.query(Export)
                .filter(Export.org_id == org.id, Export.status == status)
                .count()
                > 0
                for status in ("ready", "failed", "processing")
            ),
            errors=errors,
        )
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
    parser.add_argument(
        "--live-api",
        action="store_true",
        help="run the live local API smoke test against DEMO_API_BASE_URL",
    )
    args = parser.parse_args()
    if args.live_api:
        return run_live_api()
    if args.local_db:
        db_code = run_local_db()
        if db_code != 0:
            return db_code
        return run_live_api()
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
