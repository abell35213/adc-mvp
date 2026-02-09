"""ELD data normalizer."""


def normalize_eld_record(raw: dict) -> dict:
    """Normalize a raw ELD record into a standard format."""
    return {
        "driver_id": raw.get("driverId"),
        "status": raw.get("eldStatus"),
        "timestamp": raw.get("time"),
        "vehicle_id": raw.get("vehicleId"),
    }
