"""Tests for the FakeSamsaraAdapter."""

from app.services.fake_samsara_adapter import FakeSamsaraAdapter, SAMSARA_FIXTURES_DIR


class TestFakeSamsaraAdapter:
    """Validate that the fake adapter loads fixture JSON correctly."""

    def test_fixtures_dir_exists(self):
        assert SAMSARA_FIXTURES_DIR.is_dir(), (
            f"provider_fixtures/samsara directory missing at {SAMSARA_FIXTURES_DIR}"
        )

    def test_get_vehicle_locations_returns_list(self):
        adapter = FakeSamsaraAdapter()
        data = adapter.get_vehicle_locations()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_get_vehicle_locations_has_expected_keys(self):
        adapter = FakeSamsaraAdapter()
        record = adapter.get_vehicle_locations()[0]
        assert "vehicleId" in record
        assert "latitude" in record
        assert "longitude" in record

    def test_get_safety_events_returns_list(self):
        adapter = FakeSamsaraAdapter()
        data = adapter.get_safety_events()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_get_safety_events_has_expected_keys(self):
        adapter = FakeSamsaraAdapter()
        record = adapter.get_safety_events()[0]
        assert "safetyEventType" in record
        assert "severity" in record

    def test_get_eld_logs_returns_list(self):
        adapter = FakeSamsaraAdapter()
        data = adapter.get_eld_logs()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_get_eld_logs_has_expected_keys(self):
        adapter = FakeSamsaraAdapter()
        record = adapter.get_eld_logs()[0]
        assert "driverId" in record
        assert "eldStatus" in record

    def test_get_vehicle_state_returns_list(self):
        adapter = FakeSamsaraAdapter()
        data = adapter.get_vehicle_state()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_get_vehicle_state_has_expected_keys(self):
        adapter = FakeSamsaraAdapter()
        record = adapter.get_vehicle_state()[0]
        assert "vehicleId" in record
        assert "speed" in record

    def test_fetch_dashcam_stream_returns_bytes(self):
        adapter = FakeSamsaraAdapter()
        data = adapter.fetch_dashcam_stream()
        assert isinstance(data, bytes)
        assert len(data) > 0

    def test_fetch_dashcam_stream_accepts_stream_param(self):
        adapter = FakeSamsaraAdapter()
        data = adapter.fetch_dashcam_stream(stream="driver_facing")
        assert isinstance(data, bytes)

    def test_missing_fixtures_dir_returns_empty(self, tmp_path):
        adapter = FakeSamsaraAdapter(fixtures_dir=tmp_path / "nonexistent")
        data = adapter.get_vehicle_locations()
        assert data == []

    def test_missing_dashcam_file_returns_none(self, tmp_path):
        adapter = FakeSamsaraAdapter(fixtures_dir=tmp_path)
        data = adapter.fetch_dashcam_stream()
        assert data is None


class TestHelloWorldTask:
    """Validate that the hello_world Celery task is registered and works."""

    def test_hello_world_returns_expected(self):
        from app.tasks.celery_app import hello_world

        result = hello_world()
        assert result == {"message": "hello world", "status": "ok"}

    def test_hello_world_is_registered(self):
        from app.tasks.celery_app import celery_app

        task_names = list(celery_app.tasks.keys())
        assert "app.tasks.celery_app.hello_world" in task_names
