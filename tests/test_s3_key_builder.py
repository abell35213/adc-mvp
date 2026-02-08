"""Tests for the deterministic S3 key builder."""

import uuid

from app.services.s3_key_builder import dashcam_key, export_key, telematics_key


class TestTelematicsKey:
    def test_json_extension(self):
        key = telematics_key("inc-1", "eld_log", "art-1", "json")
        assert key == "incidents/inc-1/telematics/eld_log/art-1.json"

    def test_csv_extension(self):
        key = telematics_key("inc-1", "gps_trail", "art-2", "csv")
        assert key == "incidents/inc-1/telematics/gps_trail/art-2.csv"

    def test_pdf_extension(self):
        key = telematics_key("inc-1", "safety_event", "art-3", "pdf")
        assert key == "incidents/inc-1/telematics/safety_event/art-3.pdf"

    def test_strips_leading_dot_from_extension(self):
        key = telematics_key("inc-1", "eld_log", "art-1", ".json")
        assert key == "incidents/inc-1/telematics/eld_log/art-1.json"

    def test_with_real_uuids(self):
        inc = str(uuid.uuid4())
        art = str(uuid.uuid4())
        key = telematics_key(inc, "vehicle_state", art, "json")
        assert key == f"incidents/{inc}/telematics/vehicle_state/{art}.json"


class TestDashcamKey:
    def test_road_facing(self):
        key = dashcam_key("inc-1", "road_facing", "art-1")
        assert key == "incidents/inc-1/dashcam/road_facing/art-1.mp4"

    def test_driver_facing(self):
        key = dashcam_key("inc-1", "driver_facing", "art-2")
        assert key == "incidents/inc-1/dashcam/driver_facing/art-2.mp4"

    def test_with_real_uuids(self):
        inc = str(uuid.uuid4())
        art = str(uuid.uuid4())
        key = dashcam_key(inc, "road_facing", art)
        assert key == f"incidents/{inc}/dashcam/road_facing/{art}.mp4"


class TestExportKey:
    def test_basic(self):
        key = export_key("inc-1", "exp-1")
        assert key == "incidents/inc-1/exports/exp-1/ADC_Court_Package.zip"

    def test_with_real_uuids(self):
        inc = str(uuid.uuid4())
        exp = str(uuid.uuid4())
        key = export_key(inc, exp)
        assert key == f"incidents/{inc}/exports/{exp}/ADC_Court_Package.zip"

    def test_key_is_deterministic(self):
        """Same inputs always produce the same key."""
        k1 = export_key("inc-1", "exp-1")
        k2 = export_key("inc-1", "exp-1")
        assert k1 == k2
