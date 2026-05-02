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
        dispatch_instructions_json=[
            {
                "dispatch_instruction_id": "88888888-8888-8888-8888-888888888888",
                "dispatch_id": "DSP-7700",
                "load_number": "LD-9001",
                "dispatched_by": "Jane Dispatcher",
                "dispatched_at_utc": "2026-04-30T18:00:00+00:00",
                "pickup_appointment_at_utc": "2026-04-30T22:00:00+00:00",
                "delivery_appointment_at_utc": "2026-05-01T18:00:00+00:00",
                "eta_at_utc": "2026-05-01T17:30:00+00:00",
                "origin_address": "123 Origin St",
                "destination_address": "456 Destination Ave",
                "hos_remaining_drive_minutes": 120,
                "hos_remaining_duty_minutes": 240,
                "forced_dispatch_flag": True,
                "notes": "Reefer set to 34F",
                "adc_driver_id": "33333333-3333-3333-3333-333333333333",
                "adc_vehicle_id": "T-100",
                "adc_trailer_id": "TR-555",
                "source": "manual",
                "external_id": None,
            }
        ],
        weigh_station_reports_json=[
            {
                "weigh_station_report_id": "99999999-9999-9999-9999-999999999999",
                "weighed_at_utc": "2026-04-30T23:30:00+00:00",
                "station_name": "Acme Scale",
                "station_location": "I-90 mile 215",
                "ticket_number": "WS-12345",
                "gross_weight_lb": 82500,
                "steer_axle_weight_lb": 12000,
                "drive_axle_weight_lb": 35000,
                "trailer_axle_weight_lb": 35500,
                "legal_limit_lb": 80000,
                "is_over_legal_limit": True,
                "result": "cited",
                "citation_text": "Overweight on drive axle",
                "inspector_name": "Officer Smith",
                "doc_artifact_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                "adc_vehicle_id": "T-100",
                "adc_trailer_id": "TR-555",
                "source": "tms",
                "external_id": "ws-ext-1",
            }
        ],
        loading_dock_reports_json=[
            {
                "loading_dock_report_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                "loaded_at_utc": "2026-04-30T20:00:00+00:00",
                "facility_name": "Acme Loading Dock",
                "facility_address": "789 Dock Rd",
                "commodity": "Refrigerated produce",
                "pieces": 24,
                "gross_weight_lb": 41000,
                "net_weight_lb": 38000,
                "seal_number": "SEAL-77",
                "securement_method": "load bars + straps",
                "weight_distribution_notes": "Heavy on rear",
                "is_overloaded": False,
                "is_improperly_loaded": True,
                "loaded_by": "Dock Worker A",
                "dock_supervisor": "Sue Supervisor",
                "signature_artifact_id": None,
                "adc_trailer_id": "TR-555",
                "adc_vehicle_id": "T-100",
                "source": "manual",
                "external_id": None,
                "photos": [
                    {
                        "artifact_id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
                        "artifact_type": "loading_dock_photo",
                        "status": "captured",
                    },
                    {
                        "artifact_id": "dddddddd-dddd-dddd-dddd-dddddddddddd",
                        "artifact_type": "loading_dock_photo",
                        "status": "captured",
                    },
                ],
            }
        ],
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
        assert "No dispatch instructions on file" in packet.html_body
        assert "No weigh station reports on file" in packet.html_body
        assert "No loading dock reports on file" in packet.html_body
        assert packet.samsara_deep_links == []

    def test_phase3_dispatch_section_renders_with_callout(self):
        packet = build_crash_packet(_example_row())
        html = packet.html_body
        assert "Dispatch Instructions" in html
        assert "DSP-7700" in html
        assert "LD-9001" in html
        # Forced-dispatch callout
        assert "Forced dispatch flagged" in html

    def test_phase3_weigh_station_section_renders_with_callouts(self):
        packet = build_crash_packet(_example_row())
        html = packet.html_body
        assert "Weigh Station Reports" in html
        assert "Acme Scale" in html
        assert "WS-12345" in html
        assert "82500" in html
        # Over-limit callout
        assert "over the legal weight limit" in html
        # Cited callout
        assert "Inspection result: cited" in html

    def test_phase3_loading_dock_section_renders_with_photos(self):
        packet = build_crash_packet(_example_row())
        html = packet.html_body
        assert "Loading Dock Reports" in html
        assert "Acme Loading Dock" in html
        assert "Refrigerated produce" in html
        assert "improperly loaded" in html
        # Two linked photos surfaced
        assert "Loading dock photos (2)" in html

    def test_payload_hash_changes_when_dispatch_added(self):
        # Catches a forgotten field in the payload-hash dict.
        from app.services.crash_packet_query import CrashPacketRow

        base = CrashPacketRow(
            incident_json={
                "incident_id": "11111111-1111-1111-1111-111111111111",
                "org_id": "22222222-2222-2222-2222-222222222222",
                "status": "accident_occurred",
                "case_status": "new",
                "severity": "minor",
                "adc_vehicle_id": None,
                "samsara_vehicle_id": None,
                "adc_driver_id": None,
                "created_at_utc": "2026-05-01T01:00:00+00:00",
                "updated_at_utc": None,
            },
            driver_json=None,
        )
        with_dispatch = CrashPacketRow(
            incident_json=dict(base.incident_json),
            driver_json=None,
            dispatch_instructions_json=[
                {"dispatch_instruction_id": "x", "dispatch_id": "DSP-1"}
            ],
        )
        a = build_crash_packet(base)
        b = build_crash_packet(with_dispatch)
        assert a.payload_hash != b.payload_hash

    def test_payload_hash_changes_when_weigh_added(self):
        from app.services.crash_packet_query import CrashPacketRow

        base = CrashPacketRow(
            incident_json={
                "incident_id": "11111111-1111-1111-1111-111111111111",
                "org_id": None,
                "status": "open",
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
        with_weigh = CrashPacketRow(
            incident_json=dict(base.incident_json),
            driver_json=None,
            weigh_station_reports_json=[
                {"weigh_station_report_id": "x", "ticket_number": "T-1"}
            ],
        )
        with_dock = CrashPacketRow(
            incident_json=dict(base.incident_json),
            driver_json=None,
            loading_dock_reports_json=[
                {"loading_dock_report_id": "x", "facility_name": "F"}
            ],
        )
        h_base = build_crash_packet(base).payload_hash
        h_weigh = build_crash_packet(with_weigh).payload_hash
        h_dock = build_crash_packet(with_dock).payload_hash
        assert h_base != h_weigh
        assert h_base != h_dock
        assert h_weigh != h_dock
