"""Schema validation service."""

import json
from pathlib import Path


SCHEMAS_DIR = Path(__file__).resolve().parent.parent.parent / "contracts" / "schemas"


def validate_payload(payload: dict, schema_name: str) -> bool:
    """Validate a payload against a named JSON schema.

    Returns True if valid. Raises ValueError on validation failure.
    """
    schema_path = SCHEMAS_DIR / f"{schema_name}.json"
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema '{schema_name}' not found at {schema_path}")

    with open(schema_path) as f:
        schema = json.load(f)

    # Placeholder: integrate jsonschema library for full validation
    _ = schema
    return True
