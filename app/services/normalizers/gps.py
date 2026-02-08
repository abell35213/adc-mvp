"""GPS data normalizer."""


def normalize_gps_record(raw: dict) -> dict:
    """Normalize a raw GPS record into a standard format."""
    return {
        "latitude": raw.get("latitude"),
        "longitude": raw.get("longitude"),
        "heading": raw.get("heading"),
        "speed": raw.get("speed"),
        "timestamp": raw.get("time"),
        "vehicle_id": raw.get("vehicleId"),
    }
