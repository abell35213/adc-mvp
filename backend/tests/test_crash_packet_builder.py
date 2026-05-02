"""Tests for the crash-packet builder (plan test #2)."""

from __future__ import annotations

from app.services.crash_packet_builder import build_crash_packet
from app.services.crash_packet_query import CrashPacketRow


def _example_row() -> CrashPacketRow:
    return CrashPacketRow(
        incident_json={
            "incident_id": "11111111-1111-1111-1111-111111111111",
            "org_id": "22222222-2222-2222-2222-222222222222",
            "status": "accident_occurred",
            "case_status": "new",
            "severity": "serious",
            "adc_vehicle_id": "T-100",
            "samsara_vehicle_id": "sams-9001",
            "adc_driver_id": "33333333-3333-3333-3333-333333333333",
            "created_at_utc": "2026-05-01T01:00:00+00:00",
            "updated_at_utc": "2026-05-01T01:00:00+00:00",
        },
        driver_json={
            "driver_id": "33333333-3333-3333-3333-333333333333",
            "display_name": "Pat Driver",
            "phone_e164": "+15551234567",
            "is_active": True,
        },
        driver_history_json=[
            {
                "incident_id": "44444444-4444-4444-4444-444444444444",
                "created_at_utc": "2025-12-01T00:00:00+00:00",
                "status": "closed",
                "severity": "minor",
            }
        ],
        vehicle_json={
            "vehicle_id": "55555555-5555-5555-5555-555555555555",
            "unit_number": "T-100",
            "vin": "1HGBH41JXMN109186",
            "provider": "samsara",
            "provider_vehicle_id": "sams-9001",
            "is_active": True,
        },
        eld_logs_json=[
            {
                "artifact_id": "66666666-6666-6666-6666-666666666666",
                "artifact_type": "eld_log_report",
                "status": "captured",
            }
        ],
        samsara_clip_links_json=[
            {
                "artifact_id": "77777777-7777-7777-7777-777777777777",
                "artifact_type": "dashcam_clip",
                "samsara_vehicle_id": "sams-9001",
                "deep_link": "https://cloud.samsara.com/o/fleet/vehicles/sams-9001/dashcam",
                "fallback_s3_bucket": "adc-mvp-artifacts",
                "fallback_s3_key": "incidents/x/dashcam.mp4",
            }
        ],
        related_event_count=3,
    )


class TestCrashPacketBuilder:
    def test_subject_includes_severity_and_short_id(self):
        packet = build_crash_packet(_example_row())
        assert "[ADC] Crash brief" in packet.subject
        assert "serious" in packet.subject
        assert "11111111" in packet.subject

    def test_html_body_contains_every_required_section(self):
        packet = build_crash_packet(_example_row())
        html = packet.html_body

        assert "Initial Crash Brief" in html
        assert "Pat Driver" in html
        assert "Driver Safety History" in html
        # prior incident id surfaced
        assert "44444444-4444-4444-4444-444444444444" in html
        assert "T-100" in html
        # Maintenance section advertises the 1-year lookback (per clarifying answer)
        assert "last 365 days" in html
        # ELD section
        assert "eld_log_report" in html
        # Samsara deep link
        assert "https://cloud.samsara.com/o/fleet/vehicles/sams-9001/dashcam" in html

    def test_pdf_bytes_returned(self):
        packet = build_crash_packet(_example_row())
        # The test conftest installs a fake WeasyPrint that prefixes all
        # outputs with a deterministic marker.
        assert packet.pdf_bytes.startswith(b"%PDF-1.4")

    def test_payload_hash_is_stable(self):
        a = build_crash_packet(_example_row())
        b = build_crash_packet(_example_row())
        assert a.payload_hash == b.payload_hash

    def test_payload_hash_changes_with_content(self):
        row1 = _example_row()
        row2 = _example_row()
        row2.incident_json["severity"] = "minor"
        a = build_crash_packet(row1)
        b = build_crash_packet(row2)
        assert a.payload_hash != b.payload_hash

    def test_samsara_deep_links_extracted(self):
        packet = build_crash_packet(_example_row())
        assert packet.samsara_deep_links == [
            "https://cloud.samsara.com/o/fleet/vehicles/sams-9001/dashcam"
        ]

    def test_handles_missing_optional_sections(self):
        row = CrashPacketRow(
            incident_json={
                "incident_id": "11111111-1111-1111-1111-111111111111",
                "org_id": "22222222-2222-2222-2222-222222222222",
                "status": "accident_occurred",
                "case_status": "new",
                "severity": None,
                "adc_vehicle_id": None,
                "samsara_vehicle_id": None,
                "adc_driver_id": None,
                "created_at_utc": "2026-05-01T01:00:00+00:00",
                "updated_at_utc": None,
            },
            driver_json=None,
        )
        packet = build_crash_packet(row)
        assert "Driver record not available" in packet.html_body
        assert "Vehicle record not available" in packet.html_body
        assert "No prior incidents on file" in packet.html_body
        assert "No dashcam clips captured" in packet.html_body
        assert packet.samsara_deep_links == []
