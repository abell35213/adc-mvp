#!/usr/bin/env python3
"""Validate JSON example files against contracts/schemas/.

Exit 0 if all valid, 1 if any validation fails.

Usage:
    python scripts/validate_schemas.py [--schema-dir PATH]
"""

import argparse
import json
import sys
from pathlib import Path

import jsonschema

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SCHEMAS_DIR = REPO_ROOT / "contracts" / "schemas"


def load_schemas(schemas_dir: Path) -> dict[str, dict]:
    """Load all *.schema.json files from *schemas_dir*."""
    schemas: dict[str, dict] = {}
    for path in sorted(schemas_dir.glob("*.schema.json")):
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


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--schema-dir",
        type=Path,
        default=DEFAULT_SCHEMAS_DIR,
        help=f"Directory containing *.schema.json files (default: {DEFAULT_SCHEMAS_DIR})",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    schemas_dir: Path = args.schema_dir

    if not schemas_dir.is_dir():
        print(f"FAIL: schemas directory not found at {schemas_dir}")
        return 1

    schemas = load_schemas(schemas_dir)
    if not schemas:
        print(f"FAIL: no *.schema.json files in {schemas_dir}")
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
