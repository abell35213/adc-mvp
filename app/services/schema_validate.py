"""Schema validation service."""

import json
from pathlib import Path

import jsonschema

SCHEMAS_DIR = Path(__file__).resolve().parent.parent.parent / "contracts" / "schemas"


def _resolve_schema_path(schema_name: str) -> Path:
    """Resolve a schema name to its file path.

    Tries ``<name>.json`` first, then ``<name>.schema.json``
    (the convention used by the shipped contract schemas).
    """
    for suffix in (f"{schema_name}.json", f"{schema_name}.schema.json"):
        candidate = SCHEMAS_DIR / suffix
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        f"Schema '{schema_name}' not found in {SCHEMAS_DIR}"
    )


def validate_payload(payload: dict, schema_name: str) -> bool:
    """Validate a payload against a named JSON schema.

    Returns True if valid. Raises ValueError on validation failure.
    """
    schema_path = _resolve_schema_path(schema_name)

    with open(schema_path) as f:
        schema = json.load(f)

    try:
        jsonschema.validate(instance=payload, schema=schema)
    except jsonschema.ValidationError as exc:
        raise ValueError(
            f"Schema validation failed for '{schema_name}': {exc.message}"
        ) from exc

    return True
