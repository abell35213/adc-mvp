#!/usr/bin/env python3
"""Generate runtime API contract snapshots from backend Pydantic schemas.

Usage:
  python scripts/generate_runtime_api_contract.py          # writes snapshot
  python scripts/generate_runtime_api_contract.py --check  # fails on drift
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

CONTRACT_PATH = REPO_ROOT / "contracts" / "schemas" / "runtime_api_contracts.json"

def _load_contract_models() -> dict[str, type]:
    from app.api import schemas as api_schemas  # noqa: E402

    return {
        # Auth
        "LoginRequest": api_schemas.LoginRequest,
        "RegisterRequest": api_schemas.RegisterRequest,
        "MeResponse": api_schemas.MeResponse,
        # Incidents / exports used by frontend/lib/api.ts
        "CreateIncidentRequest": api_schemas.CreateIncidentRequest,
        "CreateIncidentResponse": api_schemas.CreateIncidentResponse,
        "IncidentListItem": api_schemas.IncidentListItem,
        "IncidentDetailResponse": api_schemas.IncidentDetailResponse,
        "CreateExportResponse": api_schemas.CreateExportResponse,
        "DownloadExportResponse": api_schemas.DownloadExportResponse,
        # Admin + driver protocol
        "DriverProtocolSettingsResponse": api_schemas.DriverProtocolSettingsResponse,
        "DriverInstructionSetResponse": api_schemas.DriverInstructionSetResponse,
        # Admin vehicles / qr
        "AdminVehicleSummary": api_schemas.AdminVehicleSummary,
        "RotateQrResponse": api_schemas.RotateQrResponse,
        "QrPayloadResponse": api_schemas.QrPayloadResponse,
    }


def build_snapshot(contract_models: dict[str, type] | None = None) -> dict[str, object]:
    models = contract_models or _load_contract_models()
    return {
        "meta": {
            "source": "backend/app/api/schemas.py",
            "models": list(models.keys()),
        },
        "schemas": {
            name: model.model_json_schema(mode="validation")
            for name, model in models.items()
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    try:
        contract_models = _load_contract_models()
    except ModuleNotFoundError as exc:
        if args.check:
            print(
                "WARN: backend schema dependencies are unavailable in this environment; "
                f"skipping runtime contract drift check ({exc})."
            )
            return 0
        raise

    snapshot = build_snapshot(contract_models)
    rendered = json.dumps(snapshot, indent=2, sort_keys=True) + "\n"

    if args.check:
        if not CONTRACT_PATH.exists():
            print(f"FAIL: missing contract snapshot at {CONTRACT_PATH}")
            return 1
        existing = CONTRACT_PATH.read_text()
        if existing != rendered:
            print("FAIL: runtime API contract drift detected.")
            print(
                "Run: python scripts/generate_runtime_api_contract.py "
                "and commit updated contracts/schemas/runtime_api_contracts.json"
            )
            return 1
        print("OK: runtime API contract snapshot is up to date")
        return 0

    CONTRACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONTRACT_PATH.write_text(rendered)
    print(f"Wrote runtime API contracts to {CONTRACT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
