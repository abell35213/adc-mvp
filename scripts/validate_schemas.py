#!/usr/bin/env python3
"""Validate JSON example files against contracts/schemas/.

Exit 0 if all valid, 1 if any validation fails.
Usage:
    python scripts/validate_schemas.py
"""

import json
import sys
from pathlib import Path

import jsonschema

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMAS_DIR = REPO_ROOT / "contracts" / "schemas"


def load_schemas() -> dict[str, dict]:
    """Load all *.schema.json files from contracts/schemas/."""
    schemas: dict[str, dict] = {}
    for path in sorted(SCHEMAS_DIR.glob("*.schema.json")):
        with open(path) as f:
            schemas[path.stem.replace(".schema", "")] = json.load(f)
    return schemas


def validate_schemas_are_valid_json_schema(schemas: dict[str, dict]) -> list[str]:
    """Verify each schema file is itself a valid JSON Schema draft."""
    errors: list[str] = []
    for name, schema in schemas.items():
        try:
            jsonschema.Draft7Validator.check_schema(schema)
        except jsonschema.SchemaError as exc:
            errors.append(f"  {name}: {exc.message}")
    return errors


def main() -> int:
    if not SCHEMAS_DIR.is_dir():
        print(f"FAIL: schemas directory not found at {SCHEMAS_DIR}")
        return 1

    schemas = load_schemas()
    if not schemas:
        print(f"FAIL: no *.schema.json files in {SCHEMAS_DIR}")
        return 1

    print(f"Found {len(schemas)} schema(s): {', '.join(schemas)}")

    # 1. Check schemas are valid JSON Schema
    errors = validate_schemas_are_valid_json_schema(schemas)
    if errors:
        print("FAIL: invalid JSON Schema files:")
        for e in errors:
            print(e)
        return 1

    print("OK: all schemas are valid JSON Schema documents")
    return 0


if __name__ == "__main__":
    sys.exit(main())
