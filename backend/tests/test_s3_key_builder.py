"""Tests for the deterministic S3 key builder."""

import uuid

import pytest

from app.services.s3_key_builder import dashcam_key, export_key, telematics_key


class TestTelematicsKey:
    def test_json_extension(self):
        key = telematics_key("org-1", "inc-1", "eld_log", "art-1", "json")
        assert key == "orgs/org-1/incidents/inc-1/artifacts/art-1.json"

    def test_csv_extension(self):
        key = telematics_key("org-1", "inc-1", "gps_trail", "art-2", "csv")
        assert key == "orgs/org-1/incidents/inc-1/artifacts/art-2.csv"

    def test_pdf_extension(self):
        key = telematics_key("org-1", "inc-1", "safety_event", "art-3", "pdf")
        assert key == "orgs/org-1/incidents/inc-1/artifacts/art-3.pdf"

    def test_strips_leading_dot_from_extension(self):
        key = telematics_key("org-1", "inc-1", "eld_log", "art-1", ".json")
        assert key == "orgs/org-1/incidents/inc-1/artifacts/art-1.json"

    def test_with_real_uuids(self):
        org = str(uuid.uuid4())
        inc = str(uuid.uuid4())
        art = str(uuid.uuid4())
        key = telematics_key(org, inc, "vehicle_state", art, "json")
        assert key == f"orgs/{org}/incidents/{inc}/artifacts/{art}.json"


class TestDashcamKey:
    def test_road_facing(self):
        key = dashcam_key("org-1", "inc-1", "road_facing", "art-1")
        assert key == "orgs/org-1/incidents/inc-1/artifacts/art-1.mp4"

    def test_driver_facing(self):
        key = dashcam_key("org-1", "inc-1", "driver_facing", "art-2")
        assert key == "orgs/org-1/incidents/inc-1/artifacts/art-2.mp4"

    def test_with_real_uuids(self):
        org = str(uuid.uuid4())
        inc = str(uuid.uuid4())
        art = str(uuid.uuid4())
        key = dashcam_key(org, inc, "road_facing", art)
        assert key == f"orgs/{org}/incidents/{inc}/artifacts/{art}.mp4"


class TestExportKey:
    def test_basic(self):
        key = export_key("org-1", "inc-1", "exp-1")
        assert key == "orgs/org-1/incidents/inc-1/artifacts/exp-1.zip"

    def test_with_real_uuids(self):
        org = str(uuid.uuid4())
        inc = str(uuid.uuid4())
        exp = str(uuid.uuid4())
        key = export_key(org, inc, exp)
        assert key == f"orgs/{org}/incidents/{inc}/artifacts/{exp}.zip"

    def test_key_is_deterministic(self):
        """Same inputs always produce the same key."""
        k1 = export_key("org-1", "inc-1", "exp-1")
        k2 = export_key("org-1", "inc-1", "exp-1")
        assert k1 == k2


def test_rejects_unsafe_key_segments():
    with pytest.raises(ValueError):
        telematics_key("org-1", "inc-1", "eld_log", "../../secret", "json")
