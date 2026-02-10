"""Schema validation service."""

import json
from pathlib import Path

from jsonschema import Draft202012Validator

SCHEMAS_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent / "contracts" / "schemas"
)
MAX_ERRORS_TO_DISPLAY = 10


def _error_sort_key(error):
    """Return a sortable key for validation error paths.

    Args:
        error: ValidationError instance with a JSON path.

    Returns:
        Tuple used to order errors consistently by path.
    """
    return tuple(
        (0, part) if isinstance(part, int) else (1, str(part)) for part in error.path
    )


def _format_error_path(path):
    """Format a validation error path using JSONPath-style notation.

    Args:
        path: ValidationError path iterable.

    Returns:
        JSONPath-like string starting at "$".
    """
    parts = [f"[{part}]" if isinstance(part, int) else f".{part}" for part in path]
    return "$" + "".join(parts)


def _resolve_schema_path(schema_name: str) -> Path:
    """Resolve a schema name to its file path.

    Tries ``<name>.json`` first, then ``<name>.schema.json``
    (the convention used by the shipped contract schemas).
    """
    for suffix in (f"{schema_name}.json", f"{schema_name}.schema.json"):
        candidate = SCHEMAS_DIR / suffix
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Schema '{schema_name}' not found in {SCHEMAS_DIR}")


def validate_payload(payload: dict, schema_name: str) -> bool:
    """Validate a payload against a named JSON schema.

    Returns True if valid. Raises ValueError on validation failure.
    """
    schema_path = _resolve_schema_path(schema_name)

    with open(schema_path) as f:
        schema = json.load(f)

    validator = Draft202012Validator(schema)
    errors = sorted(
        validator.iter_errors(payload),
        key=_error_sort_key,
    )

    if errors:
        formatted_errors = []
        for error in errors[:MAX_ERRORS_TO_DISPLAY]:
            location = _format_error_path(error.path)
            formatted_errors.append(f"{location}: {error.message}")

        error_list = "\n- ".join(formatted_errors)
        raise ValueError(
            f"Schema validation failed for '{schema_name}':\n- {error_list}"
        )

    return True
