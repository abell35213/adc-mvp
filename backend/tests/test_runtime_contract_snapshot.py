"""Ensure committed runtime contract snapshot matches backend schemas."""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.generate_runtime_api_contract import build_snapshot  # noqa: E402


def test_runtime_contract_snapshot_has_no_drift():
    contract_path = REPO_ROOT / "contracts" / "schemas" / "runtime_api_contracts.json"

    expected = build_snapshot()
    rendered = json.dumps(expected, indent=2, sort_keys=True) + "\n"

    assert contract_path.exists(), "runtime_api_contracts.json missing"
    assert contract_path.read_text() == rendered
