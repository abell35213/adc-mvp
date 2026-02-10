"""Tests for the schema validation service."""

import pytest

from app.services.schema_validate import SCHEMAS_DIR, _resolve_schema_path, validate_payload


# ── _resolve_schema_path ────────────────────────────────────────────


class TestResolveSchemaPath:
    def test_resolves_schema_json_suffix(self):
        """Files named <name>.schema.json are found."""
        path = _resolve_schema_path("vehicle_state")
        assert path.exists()
        assert path.name == "vehicle_state.schema.json"

    def test_resolves_all_shipped_schemas(self):
        for name in (
            "eld_duty_status",
            "gps_trace",
            "safety_events",
            "vehicle_state",
            "chain_of_custody",
            "evidence_inventory",
        ):
            path = _resolve_schema_path(name)
            assert path.exists(), f"Schema '{name}' not resolved"

    def test_missing_schema_raises(self):
        with pytest.raises(FileNotFoundError, match="nonexistent"):
            _resolve_schema_path("nonexistent")


# ── validate_payload ────────────────────────────────────────────────


class TestValidatePayload:
    """Validate that payloads are checked against contracts/schemas/."""

    @staticmethod
    def _make_vehicle_state_payload(**overrides):
        base = {
            "schema_version": "1.0",
            "generated_at_utc": "2024-01-01T00:00:00Z",
            "incident_id": "550e8400-e29b-41d4-a716-446655440000",
            "carrier_id": "carrier1",
            "vehicle": {
                "adc_vehicle_id": "v1",
                "samsara_vehicle_id": "s1",
            },
            "capture_window": {
                "start_utc": "2024-01-01T00:00:00Z",
                "end_utc": "2024-01-01T01:00:00Z",
                "request_reason": "incident_start_default_window",
            },
            "source_system": "samsara",
            "artifacts": {
                "artifact_id": "550e8400-e29b-41d4-a716-446655440001",
                "related_artifact_ids": [],
            },
            "data": {
                "snapshots": [],
                "summary": {
                    "snapshots_count": 0,
                    "first_snapshot_time_utc": None,
                    "last_snapshot_time_utc": None,
                },
            },
        }
        base.update(overrides)
        return base

    def test_valid_payload_returns_true(self):
        payload = self._make_vehicle_state_payload()
        assert validate_payload(payload, "vehicle_state") is True

    def test_invalid_payload_raises_value_error(self):
        with pytest.raises(ValueError) as excinfo:
            validate_payload({"bad": "data"}, "vehicle_state")
        message = str(excinfo.value)
        assert "Schema validation failed for 'vehicle_state':" in message
        error_lines = [line for line in message.splitlines()[1:] if line.strip()]
        assert error_lines
        assert len(error_lines) <= 10

    def test_missing_required_field_raises(self):
        payload = self._make_vehicle_state_payload()
        del payload["incident_id"]
        with pytest.raises(ValueError, match="Schema validation failed"):
            validate_payload(payload, "vehicle_state")

    def test_additional_properties_rejected(self):
        payload = self._make_vehicle_state_payload(extra_field="nope")
        with pytest.raises(ValueError, match="Schema validation failed"):
            validate_payload(payload, "vehicle_state")

    def test_missing_schema_raises_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            validate_payload({}, "does_not_exist")

    def test_schemas_dir_points_to_contracts(self):
        assert SCHEMAS_DIR.name == "schemas"
        assert SCHEMAS_DIR.parent.name == "contracts"
